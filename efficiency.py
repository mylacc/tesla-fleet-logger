import json
import os
import calendar
from datetime import datetime, date, timedelta

import requests

OPEN_METEO_ARCHIVE_URL = 'https://archive-api.open-meteo.com/v1/archive'

# Best real-world Teslas manage roughly 4.5-5 mi/kWh at the wall. A month above this
# ceiling almost certainly had charging energy we never logged (e.g. home charging),
# so it is flagged as incomplete instead of being plotted as a fake efficiency spike.
MAX_PLAUSIBLE_MI_PER_KWH = 6.0


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def supercharger_kwh_by_month(sessions):
    """Sums Supercharger CHARGING fee usage (kWh) per YYYY-MM of chargeStartDateTime."""
    monthly = {}
    for sess in sessions:
        start = sess.get('chargeStartDateTime')
        if not start:
            continue
        try:
            month_key = datetime.fromisoformat(start).strftime("%Y-%m")
        except Exception:
            continue
        for fee in sess.get('fees', []):
            if fee.get('feeType') == 'CHARGING':
                monthly[month_key] = monthly.get(month_key, 0.0) + float(fee.get('usageBase', 0.0))
                break
    return monthly


def counter_deltas_by_month(readings):
    """
    Turns a cumulative counter (list of (datetime, value)) into per-month deltas by
    linearly interpolating the counter at each 1st-of-month, the same way the odometer
    baselines are built. Only months bracketed by readings on both ends are returned.
    """
    readings = sorted(readings, key=lambda x: x[0])
    if len(readings) < 2:
        return {}

    def value_at(target):
        before = after = None
        for dt_val, v in readings:
            if dt_val <= target:
                before = (dt_val, v)
            elif after is None:
                after = (dt_val, v)
                break
        if before is None or after is None:
            return before[1] if before and before[0] == target else None
        span = (after[0] - before[0]).total_seconds()
        frac = (target - before[0]).total_seconds() / span if span else 0.0
        return before[1] + (after[1] - before[1]) * frac

    first, last = readings[0][0], readings[-1][0]
    y, m = first.year, first.month
    starts = []
    while True:
        m += 1
        if m > 12:
            m, y = 1, y + 1
        target = datetime(y, m, 1)
        if target > last:
            break
        starts.append(target)

    monthly = {}
    for a, b in zip(starts, starts[1:]):
        va, vb = value_at(a), value_at(b)
        if va is not None and vb is not None:
            monthly[a.strftime("%Y-%m")] = max(0.0, vb - va)
    return monthly


def wall_connector_kwh_by_month(history_path):
    """Monthly home kWh from logged Wall Connector lifetime energy_wh readings."""
    history = _load_json(history_path, {})
    readings = []
    for k, v in history.items():
        try:
            readings.append((datetime.fromisoformat(k), float(v) / 1000.0))
        except Exception:
            continue
    return counter_deltas_by_month(readings)


def log_wall_connector(host, history_path):
    """Records the Wall Connector's cumulative lifetime energy (Wh), if one is configured."""
    try:
        resp = requests.get(f'http://{host}/api/1/lifetime', timeout=5)
        resp.raise_for_status()
        energy_wh = resp.json().get('energy_wh')
        if energy_wh is None:
            print("DEBUG: Wall Connector lifetime response had no energy_wh field.")
            return
        history = _load_json(history_path, {})
        history[datetime.now().replace(microsecond=0).isoformat()] = energy_wh
        with open(history_path, 'w') as f:
            json.dump(history, f, indent=4, sort_keys=True)
        print(f"DEBUG: Logged Wall Connector lifetime energy: {energy_wh / 1000.0:,.1f} kWh")
    except Exception as e:
        print(f"DEBUG: Failed to read Wall Connector at '{host}': {e}")


def monthly_driving_temps(month_keys, lat, lon, cache_path, drive_hours=(7, 21)):
    """
    Average outdoor temperature (°F) per month at (lat, lon), using only hourly readings
    whose local hour falls inside drive_hours (inclusive). Uses the free Open-Meteo
    historical archive; finished months are cached so each is fetched only once.
    """
    cache = _load_json(cache_path, {})
    cache_key_prefix = f"{lat:.3f},{lon:.3f},{drive_hours[0]}-{drive_hours[1]}|"
    # The archive trails real time by several days, so stop short of today.
    latest_available = date.today() - timedelta(days=6)
    temps = {}
    changed = False

    for month_key in month_keys:
        cache_key = cache_key_prefix + month_key
        cached = cache.get(cache_key)
        if cached and cached.get('complete'):
            temps[month_key] = cached['avg_f']
            continue

        y, m = int(month_key[:4]), int(month_key[5:7])
        start = date(y, m, 1)
        end = min(date(y, m, calendar.monthrange(y, m)[1]), latest_available)
        if end < start:
            continue
        try:
            resp = requests.get(OPEN_METEO_ARCHIVE_URL, params={
                'latitude': lat,
                'longitude': lon,
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'hourly': 'temperature_2m',
                'temperature_unit': 'fahrenheit',
                'timezone': 'auto',
            }, timeout=20)
            resp.raise_for_status()
            hourly = resp.json().get('hourly', {})
        except Exception as e:
            print(f"DEBUG: Failed to fetch historical weather for {month_key}: {e}")
            if cached:
                temps[month_key] = cached['avg_f']
            continue

        values = [
            t for ts, t in zip(hourly.get('time', []), hourly.get('temperature_2m', []))
            if t is not None and drive_hours[0] <= int(ts[11:13]) <= drive_hours[1]
        ]
        if not values:
            continue
        avg_f = round(sum(values) / len(values), 1)
        temps[month_key] = avg_f
        cache[cache_key] = {
            'avg_f': avg_f,
            'complete': end == date(y, m, calendar.monthrange(y, m)[1]),
        }
        changed = True

    if changed:
        try:
            with open(cache_path, 'w') as f:
                json.dump(cache, f, indent=4, sort_keys=True)
        except Exception as e:
            print(f"DEBUG: Failed to save weather cache: {e}")
    return temps


def build_monthly_efficiency(monthly_miles, supercharger_kwh, home_kwh, temps_f, home_kwh_logged):
    """
    One row per month that has miles driven. mi_per_kwh is None when there is no energy
    for the month or the result is implausibly high (charging we didn't capture).
    """
    rows = []
    for month_key in sorted(monthly_miles.keys()):
        miles = monthly_miles[month_key]
        sc = supercharger_kwh.get(month_key, 0.0)
        home = home_kwh.get(month_key)
        # Before Wall Connector logging started, a month's home energy is unknown, not zero.
        energy_complete = (not home_kwh_logged) or home is not None
        kwh = sc + (home or 0.0)
        mi_per_kwh = miles / kwh if kwh > 0 else None
        flag = None
        if mi_per_kwh is None:
            flag = 'no charging energy logged'
        elif mi_per_kwh > MAX_PLAUSIBLE_MI_PER_KWH:
            flag = 'charging energy incomplete'
            mi_per_kwh = None
        elif not energy_complete:
            flag = 'home charging not yet logged'
        rows.append({
            'month': month_key,
            'label': datetime.strptime(month_key, "%Y-%m").strftime("%b %Y"),
            'miles': round(miles, 1),
            'supercharger_kwh': round(sc, 1),
            'home_kwh': round(home, 1) if home is not None else None,
            'mi_per_kwh': round(mi_per_kwh, 2) if mi_per_kwh is not None else None,
            'temp_f': temps_f.get(month_key),
            'flag': flag,
        })
    return rows
