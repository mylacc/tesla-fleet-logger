import json
import os
from datetime import datetime

def generate_dashboard_html(vehicle_info, odometer_history, sessions, stats, output_path="dashboard.html"):
    """
    Generates a standalone, responsive dashboard HTML file styled with shadcn/ui tokens.
    SECURITY GUARANTEE: Contains ZERO API client secrets, tokens, or private keys.
    """
    
    # 1. Prepare Odometer Timeline Data for Chart.js
    raw_points = []
    baseline_points = []
    current_point = None
    all_dates = []
    
    # Sort odometer keys chronologically
    parsed_odo = []
    for k, v in odometer_history.items():
        try:
            val = float(v)
            is_baseline = "Baseline" in k
            is_current = "Current" in k
            
            # Extract date string
            date_str = k.split(' (')[0].strip()
            parsed_odo.append({
                'full_key': k,
                'date_str': date_str,
                'val': val,
                'is_baseline': is_baseline,
                'is_current': is_current
            })
        except ValueError:
            continue
            
    parsed_odo.sort(key=lambda x: x['date_str'])
    
    for item in parsed_odo:
        entry = {'x': item['date_str'], 'y': item['val'], 'label': item['full_key']}
        all_dates.append(item['date_str'])
        if item['is_current']:
            current_point = entry
            raw_points.append(entry)
        elif item['is_baseline']:
            baseline_points.append(entry)
        else:
            raw_points.append(entry)

    # 2. Process Monthly Supercharging & Savings Data
    monthly_charging = {}
    parsed_sessions = []
    
    for sess in sessions:
        start_time = sess.get('chargeStartDateTime')
        if not start_time:
            continue
        try:
            dt = datetime.fromisoformat(start_time)
            month_key = dt.strftime("%Y-%m")
            month_label = dt.strftime("%b %Y")
        except Exception:
            month_key = "Unknown"
            month_label = "Unknown"
            
        fee_obj = None
        for fee in sess.get('fees', []):
            if fee.get('feeType') == 'CHARGING':
                fee_obj = fee
                break
                
        energy = float(fee_obj.get('usageBase', 0.0)) if fee_obj else 0.0
        rate = float(fee_obj.get('rateBase', 0.0)) if fee_obj else 0.0
        pricing_type = fee_obj.get('pricingType', 'PAID') if fee_obj else 'UNKNOWN'
        
        savings = energy * rate if pricing_type == 'NO_CHARGE' else 0.0
        
        parsed_sessions.append({
            'start_time': start_time,
            'date_formatted': dt.strftime("%Y-%m-%d %H:%M") if 'dt' in locals() else start_time,
            'site': sess.get('siteName', 'Supercharger'),
            'energy_kwh': round(energy, 2),
            'rate_usd': round(rate, 3),
            'savings_usd': round(savings, 2),
            'pricing_type': pricing_type
        })
        
        if month_key not in monthly_charging:
            monthly_charging[month_key] = {'label': month_label, 'kwh': 0.0, 'savings': 0.0, 'count': 0}
        monthly_charging[month_key]['kwh'] += energy
        monthly_charging[month_key]['savings'] += savings
        monthly_charging[month_key]['count'] += 1

    sorted_months = sorted(monthly_charging.keys())
    month_chart_labels = [monthly_charging[m]['label'] for m in sorted_months if m != "Unknown"]
    month_kwh_data = [round(monthly_charging[m]['kwh'], 1) for m in sorted_months if m != "Unknown"]
    month_savings_data = [round(monthly_charging[m]['savings'], 2) for m in sorted_months if m != "Unknown"]

    # 3. Monthly Distance Driven Chart Data
    monthly_distance = stats.get('monthly_distance_map', {})
    dist_months_sorted = sorted(monthly_distance.keys())
    dist_labels = [datetime.strptime(m, "%Y-%m").strftime("%b %Y") if len(m)==7 else m for m in dist_months_sorted]
    dist_values = [round(monthly_distance[m], 1) for m in dist_months_sorted]

    # Convert Python data objects to JSON for JavaScript embedding
    json_parsed_odo = json.dumps(parsed_odo)
    json_parsed_sessions = json.dumps(parsed_sessions)
    json_raw_points = json.dumps(raw_points)
    json_baseline_points = json.dumps(baseline_points)
    json_month_labels = json.dumps(month_chart_labels)
    json_month_kwh = json.dumps(month_kwh_data)
    json_month_savings = json.dumps(month_savings_data)
    json_dist_labels = json.dumps(dist_labels)
    json_dist_values = json.dumps(dist_values)

    # 4. Monthly Efficiency vs Temperature
    efficiency_rows = stats.get('monthly_efficiency', [])
    efficiency_meta = stats.get('efficiency_meta', {})
    json_efficiency = json.dumps(efficiency_rows)

    current_odo = float(odometer_history.get(current_point['label'], 0) if current_point else 0)
    state_label = str(vehicle_info.get('state', 'online')).capitalize()

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{vehicle_info.get('name', 'Vehicle')} Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js"></script>
    <style>
        /* shadcn/ui "zinc" theme tokens */
        :root {{
            --background: #ffffff;
            --foreground: #09090b;
            --card: #ffffff;
            --card-foreground: #09090b;
            --popover: #ffffff;
            --primary: #18181b;
            --primary-foreground: #fafafa;
            --secondary: #f4f4f5;
            --secondary-foreground: #18181b;
            --muted: #f4f4f5;
            --muted-foreground: #71717a;
            --border: #e4e4e7;
            --input: #e4e4e7;
            --ring: #a1a1aa;
            --radius: 0.625rem;
            /* Chart series, validated for colour-blind separation on both surfaces */
            --chart-1: #2563eb;
            --chart-2: #0d9488;
            --chart-3: #d97706;
            --chart-flagged: #a1a1aa;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --background: #09090b;
                --foreground: #fafafa;
                --card: #09090b;
                --card-foreground: #fafafa;
                --popover: #18181b;
                --primary: #fafafa;
                --primary-foreground: #18181b;
                --secondary: #27272a;
                --secondary-foreground: #fafafa;
                --muted: #27272a;
                --muted-foreground: #a1a1aa;
                --border: #27272a;
                --input: #27272a;
                --ring: #52525b;
                --chart-1: #3b82f6;
                --chart-flagged: #52525b;
            }}
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: var(--background);
            color: var(--foreground);
            font-family: 'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif;
            font-size: 14px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }}

        .container {{ max-width: 1280px; margin: 0 auto; padding: 32px 16px 24px; }}
        @media (min-width: 768px) {{ .container {{ padding: 40px 32px 24px; }} }}

        .tabular {{ font-variant-numeric: tabular-nums; }}

        /* Header */
        header {{
            display: flex; justify-content: space-between; align-items: flex-start;
            gap: 16px; flex-wrap: wrap; margin-bottom: 24px;
        }}
        header h1 {{ font-size: 30px; font-weight: 700; letter-spacing: -0.025em; line-height: 1.2; }}
        header p {{ color: var(--muted-foreground); margin-top: 4px; }}

        /* Badge */
        .badge {{
            display: inline-flex; align-items: center; gap: 6px;
            border-radius: calc(var(--radius) - 2px);
            border: 1px solid transparent;
            padding: 2px 8px; font-size: 12px; font-weight: 500; white-space: nowrap;
        }}
        .badge-outline {{ border-color: var(--border); color: var(--foreground); }}
        .badge-secondary {{ background: var(--secondary); color: var(--secondary-foreground); }}
        .dot {{ width: 6px; height: 6px; border-radius: 50%; background: var(--chart-2); }}

        /* Card */
        .card {{
            background: var(--card); color: var(--card-foreground);
            border: 1px solid var(--border); border-radius: calc(var(--radius) + 4px);
            box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        }}
        .card-header {{ padding: 24px 24px 0; }}
        .card-title {{ font-size: 16px; font-weight: 600; line-height: 1.2; letter-spacing: -0.01em; }}
        .card-description {{ color: var(--muted-foreground); font-size: 14px; margin-top: 4px; }}
        .card-content {{ padding: 24px; }}

        .grid {{ display: grid; gap: 16px; margin-bottom: 16px; }}
        .grid-kpi {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
        .grid-charts {{ grid-template-columns: 1fr; }}
        @media (min-width: 1024px) {{ .grid-charts {{ grid-template-columns: 3fr 2fr; }} }}

        /* KPI card */
        .kpi {{ padding: 24px; }}
        .kpi-head {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
        .kpi-title {{ font-size: 14px; font-weight: 500; }}
        .kpi-head svg {{ width: 16px; height: 16px; color: var(--muted-foreground); }}
        .kpi-value {{ font-size: 24px; font-weight: 700; letter-spacing: -0.02em; }}
        .kpi-value small {{ font-size: 14px; font-weight: 500; color: var(--muted-foreground); }}
        .kpi-sub {{ font-size: 12px; color: var(--muted-foreground); margin-top: 2px; }}

        .chart-box {{ position: relative; width: 100%; height: 300px; }}
        .chart-box.short {{ height: 160px; }}
        .chart-label {{ font-size: 12px; font-weight: 500; color: var(--muted-foreground); margin: 0 0 8px; }}
        .chart-label + .chart-box {{ margin-bottom: 16px; }}

        /* Legend */
        .legend {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 12px; color: var(--muted-foreground); margin-top: 12px; }}
        .legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
        .swatch {{ width: 10px; height: 10px; border-radius: 2px; }}
        .swatch.dashed {{ height: 0; border-top: 2px dashed var(--chart-2); border-radius: 0; }}

        /* Tabs */
        .toolbar {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 16px; }}
        .tabs-list {{
            display: inline-flex; align-items: center; height: 36px; padding: 3px;
            background: var(--muted); color: var(--muted-foreground); border-radius: var(--radius);
            max-width: 100%; overflow-x: auto;
        }}
        .tabs-trigger {{
            height: 100%; padding: 0 12px; border: 1px solid transparent; background: transparent;
            border-radius: calc(var(--radius) - 2px); font: inherit; font-size: 14px; font-weight: 500;
            color: inherit; cursor: pointer; white-space: nowrap;
        }}
        .tabs-trigger[aria-selected="true"] {{
            background: var(--background); color: var(--foreground);
            box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        }}
        @media (prefers-color-scheme: dark) {{
            .tabs-trigger[aria-selected="true"] {{ background: var(--input); border-color: var(--input); }}
        }}
        .tabs-trigger:focus-visible, .input:focus-visible {{ outline: none; box-shadow: 0 0 0 3px color-mix(in srgb, var(--ring) 50%, transparent); }}

        /* Input */
        .input {{
            height: 36px; width: 100%; max-width: 280px; padding: 4px 12px;
            border: 1px solid var(--input); border-radius: calc(var(--radius) - 2px);
            background: transparent; color: var(--foreground); font: inherit; font-size: 14px;
            box-shadow: 0 1px 2px 0 rgb(0 0 0 / 0.05);
        }}
        .input::placeholder {{ color: var(--muted-foreground); }}

        /* Table */
        .table-wrap {{ overflow-x: auto; border: 1px solid var(--border); border-radius: var(--radius); }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; text-align: left; }}
        th {{ height: 40px; padding: 0 12px; font-weight: 500; color: var(--muted-foreground); white-space: nowrap; border-bottom: 1px solid var(--border); }}
        td {{ padding: 10px 12px; border-bottom: 1px solid var(--border); white-space: nowrap; }}
        tbody tr:last-child td {{ border-bottom: 0; }}
        tbody tr:hover td {{ background: color-mix(in srgb, var(--muted) 50%, transparent); }}
        .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
        .strong {{ font-weight: 500; }}

        footer {{ color: var(--muted-foreground); font-size: 12px; text-align: center; padding: 24px 0 8px; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>{vehicle_info.get('name', 'Tesla Vehicle')}</h1>
                <p>VIN {vehicle_info.get('vin', 'N/A')} &middot; Last synced {vehicle_info.get('last_synced', 'just now')}</p>
            </div>
            <span class="badge badge-outline"><span class="dot"></span>{state_label}</span>
        </header>

        <div class="grid grid-kpi">
            <div class="card kpi">
                <div class="kpi-head">
                    <span class="kpi-title">Free Supercharging savings</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                </div>
                <div class="kpi-value tabular">${stats.get('total_savings_usd', 0.0):,.2f}</div>
                <div class="kpi-sub">Across {stats.get('total_supercharging_kwh', 0.0):,.1f} kWh of free energy</div>
            </div>
            <div class="card kpi">
                <div class="kpi-head">
                    <span class="kpi-title">Odometer</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 14 4-4"/><path d="M3.34 19a10 10 0 1 1 17.32 0"/></svg>
                </div>
                <div class="kpi-value tabular">{current_odo:,.0f} <small>mi</small></div>
                <div class="kpi-sub">Lifetime average {stats.get('lifetime_avg_monthly', 0.0):,.0f} mi/mo ({stats.get('lifetime_avg_yearly', 0.0):,.0f} mi/yr)</div>
            </div>
            <div class="card kpi">
                <div class="kpi-head">
                    <span class="kpi-title">3-month pace</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>
                </div>
                <div class="kpi-value tabular">{stats.get('avg_monthly_3m', 0.0):,.0f} <small>mi/mo</small></div>
                <div class="kpi-sub">Rolling average, last 90 days</div>
            </div>
            <div class="card kpi">
                <div class="kpi-head">
                    <span class="kpi-title">6-month pace</span>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M16 2v4"/><path d="M8 2v4"/><path d="M3 10h18"/></svg>
                </div>
                <div class="kpi-value tabular">{stats.get('avg_monthly_6m', 0.0):,.0f} <small>mi/mo</small></div>
                <div class="kpi-sub">Rolling average, last 180 days</div>
            </div>
        </div>

        <div class="grid grid-charts">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Odometer</div>
                    <div class="card-description">Recorded readings and 1st-of-month baselines, in miles</div>
                </div>
                <div class="card-content">
                    <div class="chart-box"><canvas id="odoChart"></canvas></div>
                    <div class="legend">
                        <span><i class="swatch" style="background:var(--chart-1)"></i>Readings</span>
                        <span><i class="swatch dashed"></i>Monthly baselines</span>
                    </div>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Miles driven</div>
                    <div class="card-description">Per month</div>
                </div>
                <div class="card-content">
                    <div class="chart-box"><canvas id="distChart"></canvas></div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Free Supercharging</div>
                    <div class="card-description">Energy added per month, in kWh. Hover a month for its savings.</div>
                </div>
                <div class="card-content">
                    <div class="chart-box" style="height:260px;"><canvas id="chargingChart"></canvas></div>
                </div>
            </div>
        </div>

        <div class="grid">
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Efficiency vs temperature</div>
                    <div class="card-description">Energy: {efficiency_meta.get('energy_source', 'Supercharger kWh only')} &middot; Temperature: {efficiency_meta.get('temp_source', 'not configured')}</div>
                </div>
                <div class="card-content">
                    <div class="chart-label">Efficiency (mi/kWh). Grey months are flagged as incomplete; hover for details.</div>
                    <div class="chart-box" style="height:220px;"><canvas id="efficiencyChart"></canvas></div>
                    <div class="chart-label">Average driving-hours temperature (°F)</div>
                    <div class="chart-box short"><canvas id="tempChart"></canvas></div>
                </div>
            </div>
        </div>

        <div class="card">
            <div class="card-content">
                <div class="toolbar">
                    <div class="tabs-list" role="tablist">
                        <button class="tabs-trigger" role="tab" aria-selected="true" data-tab="sessionsTab">Supercharging sessions ({len(parsed_sessions)})</button>
                        <button class="tabs-trigger" role="tab" aria-selected="false" data-tab="odometerTab">Odometer log ({len(parsed_odo)})</button>
                    </div>
                    <input class="input" type="search" id="searchInput" placeholder="Search sessions or dates..." oninput="filterTables()">
                </div>

                <div id="sessionsTab" class="table-wrap">
                    <table id="sessionsTable">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Station</th>
                                <th class="num">Energy</th>
                                <th class="num">Rate</th>
                                <th class="num">Saved</th>
                                <th>Pricing</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f'''<tr>
                                <td class="strong tabular">{s['date_formatted']}</td>
                                <td>{s['site']}</td>
                                <td class="num">{s['energy_kwh']} kWh</td>
                                <td class="num">${s['rate_usd']:.3f}/kWh</td>
                                <td class="num strong">${s['savings_usd']:.2f}</td>
                                <td><span class="badge badge-secondary">Free</span></td>
                            </tr>''' for s in parsed_sessions[:100]])}
                        </tbody>
                    </table>
                </div>

                <div id="odometerTab" class="table-wrap" hidden>
                    <table id="odometerTable">
                        <thead>
                            <tr>
                                <th>Date / label</th>
                                <th class="num">Reading</th>
                                <th>Type</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f'''<tr>
                                <td class="strong">{o['full_key']}</td>
                                <td class="num">{o['val']:,.1f} mi</td>
                                <td><span class="badge {'badge-outline' if o['is_baseline'] else 'badge-secondary'}">{'Monthly baseline' if o['is_baseline'] else ('Current' if o['is_current'] else 'Reading')}</span></td>
                            </tr>''' for o in parsed_odo])}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <footer>Tesla Fleet Logger &middot; Generated without credentials or secret keys.</footer>
    </div>

    <script>
        const rawOdoData = {json_raw_points};
        const baselineOdoData = {json_baseline_points};
        const monthLabels = {json_month_labels};
        const monthKwh = {json_month_kwh};
        const monthSavings = {json_month_savings};
        const distLabels = {json_dist_labels};
        const distValues = {json_dist_values};
        const efficiencyRows = {json_efficiency};

        // Pull shadcn theme tokens so charts follow light/dark mode.
        const css = getComputedStyle(document.documentElement);
        const token = name => css.getPropertyValue(name).trim();
        const C = {{
            fg: token('--foreground'), muted: token('--muted-foreground'), border: token('--border'),
            popover: token('--popover'), c1: token('--chart-1'), c2: token('--chart-2'),
            c3: token('--chart-3'), flagged: token('--chart-flagged'),
        }};
        matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => location.reload());

        Chart.defaults.font.family = "'Geist', ui-sans-serif, system-ui, sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.color = C.muted;
        Chart.defaults.borderColor = C.border;
        Chart.defaults.plugins.legend.display = false;
        Object.assign(Chart.defaults.plugins.tooltip, {{
            backgroundColor: C.popover, titleColor: C.fg, bodyColor: C.fg, footerColor: C.muted,
            borderColor: C.border, borderWidth: 1, cornerRadius: 8, padding: 10,
            boxPadding: 4, usePointStyle: true, titleFont: {{ weight: '600' }},
        }});
        Chart.defaults.interaction = {{ mode: 'index', intersect: false }};

        const xAxis = {{ grid: {{ display: false }}, border: {{ display: false }}, ticks: {{ maxRotation: 0, autoSkipPadding: 16 }} }};
        const yAxis = extra => Object.assign({{ border: {{ display: false }}, grid: {{ color: C.border }}, ticks: {{ maxTicksLimit: 5 }} }}, extra || {{}});
        const barStyle = color => ({{ backgroundColor: color, borderRadius: 4, borderSkipped: 'start', maxBarThickness: 40 }});
        const fmt = n => n == null ? '—' : n.toLocaleString(undefined, {{ maximumFractionDigits: 1 }});

        new Chart(document.getElementById('odoChart'), {{
            type: 'line',
            data: {{ datasets: [
                {{ label: 'Reading', data: rawOdoData, borderColor: C.c1, backgroundColor: C.c1,
                   borderWidth: 2, pointRadius: 0, pointHoverRadius: 5, tension: 0.2 }},
                {{ label: 'Monthly baseline', data: baselineOdoData, borderColor: C.c2, backgroundColor: C.c2,
                   borderWidth: 2, borderDash: [5, 4], pointRadius: 0, pointHoverRadius: 5, tension: 0.2 }},
            ] }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ tooltip: {{ callbacks: {{ label: c => ` ${{c.dataset.label}}: ${{fmt(c.parsed.y)}} mi` }} }} }},
                scales: {{
                    x: Object.assign({{ type: 'category', labels: {json.dumps(all_dates)} }}, xAxis, {{ ticks: {{ maxTicksLimit: 6, maxRotation: 0, callback: function(v) {{ return String(this.getLabelForValue(v)).slice(0, 10); }} }} }}),
                    y: yAxis({{ ticks: {{ maxTicksLimit: 5, callback: v => v.toLocaleString() }} }}),
                }},
            }},
        }});

        new Chart(document.getElementById('distChart'), {{
            type: 'bar',
            data: {{ labels: distLabels, datasets: [Object.assign({{ label: 'Miles', data: distValues }}, barStyle(C.c1))] }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ tooltip: {{ callbacks: {{ label: c => ` ${{fmt(c.parsed.y)}} mi` }} }} }},
                scales: {{ x: xAxis, y: yAxis() }},
            }},
        }});

        new Chart(document.getElementById('chargingChart'), {{
            type: 'bar',
            data: {{ labels: monthLabels, datasets: [Object.assign({{ label: 'Energy', data: monthKwh }}, barStyle(C.c1))] }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ tooltip: {{ callbacks: {{
                    label: c => ` Energy: ${{fmt(c.parsed.y)}} kWh`,
                    footer: items => `Saved $${{monthSavings[items[0].dataIndex].toFixed(2)}}`,
                }} }} }},
                scales: {{ x: xAxis, y: yAxis() }},
            }},
        }});

        // Efficiency and temperature share the month axis but get separate y-scales (no dual axis).
        const effLabels = efficiencyRows.map(r => r.label);
        const effTooltip = {{ callbacks: {{
            afterBody: items => {{
                const r = efficiencyRows[items[0].dataIndex];
                const lines = [`Temperature: ${{r.temp_f == null ? '—' : r.temp_f + ' °F'}}`, `Miles: ${{fmt(r.miles)}}`, `Supercharger: ${{fmt(r.supercharger_kwh)}} kWh`];
                if (r.home_kwh !== null) lines.push(`Home: ${{fmt(r.home_kwh)}} kWh`);
                if (r.flag) lines.push(`Note: ${{r.flag}}`);
                return lines;
            }},
        }} }};
        new Chart(document.getElementById('efficiencyChart'), {{
            type: 'bar',
            data: {{ labels: effLabels, datasets: [Object.assign({{
                label: 'Efficiency', data: efficiencyRows.map(r => r.mi_per_kwh),
            }}, barStyle(efficiencyRows.map(r => r.flag ? C.flagged : C.c2)))] }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ tooltip: Object.assign({{}}, effTooltip, {{ callbacks: Object.assign({{}}, effTooltip.callbacks, {{ label: c => ` Efficiency: ${{fmt(c.parsed.y)}} mi/kWh` }}) }}) }},
                scales: {{ x: xAxis, y: yAxis({{ beginAtZero: true }}) }},
            }},
        }});
        new Chart(document.getElementById('tempChart'), {{
            type: 'line',
            data: {{ labels: effLabels, datasets: [{{
                label: 'Temperature', data: efficiencyRows.map(r => r.temp_f),
                borderColor: C.c3, backgroundColor: C.c3, borderWidth: 2,
                pointRadius: 0, pointHoverRadius: 5, tension: 0.3, spanGaps: true,
            }}] }},
            options: {{
                responsive: true, maintainAspectRatio: false,
                plugins: {{ tooltip: {{ callbacks: {{ label: c => ` ${{fmt(c.parsed.y)}} °F` }} }} }},
                scales: {{ x: xAxis, y: yAxis({{ ticks: {{ maxTicksLimit: 4 }} }}) }},
            }},
        }});

        document.querySelectorAll('.tabs-trigger').forEach(btn => btn.addEventListener('click', () => {{
            document.querySelectorAll('.tabs-trigger').forEach(b => {{
                const on = b === btn;
                b.setAttribute('aria-selected', on);
                document.getElementById(b.dataset.tab).hidden = !on;
            }});
        }}));

        function filterTables() {{
            const q = document.getElementById('searchInput').value.toLowerCase();
            ['sessionsTable', 'odometerTable'].forEach(id => {{
                for (const row of document.getElementById(id).tBodies[0].rows) {{
                    row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"DEBUG: Web Dashboard generated successfully at '{output_path}'")
