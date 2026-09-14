import json
import os
from datetime import datetime

def generate_dashboard_html(vehicle_info, odometer_history, sessions, stats, output_path="dashboard.html"):
    """
    Generates a standalone, ultra-premium, responsive Web Dashboard HTML file.
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

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tesla Fleet Logger Dashboard - {vehicle_info.get('name', 'Vehicle')}</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-dark: #090A0F;
            --bg-card: rgba(22, 25, 35, 0.75);
            --border-card: rgba(255, 255, 255, 0.08);
            --border-card-hover: rgba(232, 33, 39, 0.3);
            --accent-red: #E82127;
            --accent-red-glow: rgba(232, 33, 39, 0.25);
            --accent-cyan: #00F0FF;
            --accent-cyan-glow: rgba(0, 240, 255, 0.2);
            --accent-green: #00E676;
            --accent-amber: #FFB300;
            --text-primary: #F3F4F6;
            --text-secondary: #9CA3AF;
            --text-muted: #6B7280;
            --radius-lg: 16px;
            --radius-md: 12px;
            --font-main: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --font-display: 'Outfit', sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(232, 33, 39, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(0, 240, 255, 0.06) 0%, transparent 40%);
            color: var(--text-primary);
            font-family: var(--font-main);
            min-height: 100vh;
            padding: 24px;
            line-height: 1.5;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        /* --- HEADER & HERO --- */
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 24px 32px;
            margin-bottom: 28px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }}

        .brand {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}

        .tesla-logo {{
            width: 42px;
            height: 42px;
            background: linear-gradient(135deg, #E82127 0%, #B71C1C 100%);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 20px var(--accent-red-glow);
        }}

        .tesla-logo svg {{
            width: 24px;
            height: 24px;
            fill: #FFFFFF;
        }}

        .brand-title h1 {{
            font-family: var(--font-display);
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.5px;
            color: #FFFFFF;
        }}

        .brand-title p {{
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .status-badge {{
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(0, 230, 118, 0.1);
            border: 1px solid rgba(0, 230, 118, 0.25);
            color: var(--accent-green);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .status-dot {{
            width: 8px;
            height: 8px;
            background-color: var(--accent-green);
            border-radius: 50%;
            box-shadow: 0 0 10px var(--accent-green);
            animation: pulse 2s infinite;
        }}

        @keyframes pulse {{
            0% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(1.2); }}
            100% {{ opacity: 1; transform: scale(1); }}
        }}

        /* --- KPI GRID --- */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 28px;
        }}

        .kpi-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 24px;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }}

        .kpi-card:hover {{
            border-color: var(--border-card-hover);
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(232, 33, 39, 0.12);
        }}

        .kpi-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-red), transparent);
        }}

        .kpi-card.cyan::before {{
            background: linear-gradient(90deg, var(--accent-cyan), transparent);
        }}

        .kpi-card.green::before {{
            background: linear-gradient(90deg, var(--accent-green), transparent);
        }}

        .kpi-card.amber::before {{
            background: linear-gradient(90deg, var(--accent-amber), transparent);
        }}

        .kpi-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}

        .kpi-title {{
            font-size: 13px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .kpi-icon {{
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.05);
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .kpi-icon svg {{
            width: 20px;
            height: 20px;
            fill: var(--text-primary);
        }}

        .kpi-value {{
            font-family: var(--font-display);
            font-size: 34px;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 4px;
            letter-spacing: -0.5px;
        }}

        .kpi-subtext {{
            font-size: 13px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .highlight-green {{
            color: var(--accent-green);
            font-weight: 600;
        }}

        .highlight-cyan {{
            color: var(--accent-cyan);
            font-weight: 600;
        }}

        /* --- CHARTS SECTION --- */
        .charts-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 24px;
            margin-bottom: 28px;
        }}

        @media (max-width: 1024px) {{
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .chart-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 24px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }}

        .chart-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }}

        .chart-title {{
            font-family: var(--font-display);
            font-size: 18px;
            font-weight: 600;
            color: #FFFFFF;
        }}

        .chart-container {{
            position: relative;
            width: 100%;
            height: 320px;
        }}

        /* --- DATA TABLES --- */
        .section-card {{
            background: var(--bg-card);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid var(--border-card);
            border-radius: var(--radius-lg);
            padding: 24px;
            margin-bottom: 28px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
        }}

        .table-controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .tabs {{
            display: flex;
            background: rgba(0, 0, 0, 0.3);
            padding: 4px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .tab-btn {{
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 8px 18px;
            font-size: 13px;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .tab-btn.active {{
            background: var(--accent-red);
            color: #FFFFFF;
            box-shadow: 0 0 15px var(--accent-red-glow);
        }}

        .search-box {{
            position: relative;
            min-width: 260px;
        }}

        .search-box input {{
            width: 100%;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid var(--border-card);
            border-radius: 8px;
            padding: 8px 14px 8px 36px;
            color: var(--text-primary);
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s ease;
        }}

        .search-box input:focus {{
            border-color: var(--accent-red);
        }}

        .search-box svg {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            width: 16px;
            height: 16px;
            fill: var(--text-muted);
        }}

        .table-wrapper {{
            overflow-x: auto;
            border-radius: var(--radius-md);
            border: 1px solid rgba(255, 255, 255, 0.05);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 13px;
        }}

        th {{
            background: rgba(0, 0, 0, 0.4);
            color: var(--text-secondary);
            font-weight: 600;
            padding: 14px 18px;
            border-bottom: 1px solid var(--border-card);
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}

        td {{
            padding: 14px 18px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .badge {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
        }}

        .badge-free {{
            background: rgba(0, 230, 118, 0.15);
            color: var(--accent-green);
            border: 1px solid rgba(0, 230, 118, 0.3);
        }}

        .badge-raw {{
            background: rgba(232, 33, 39, 0.15);
            color: var(--accent-red);
            border: 1px solid rgba(232, 33, 39, 0.3);
        }}

        .badge-baseline {{
            background: rgba(0, 240, 255, 0.15);
            color: var(--accent-cyan);
            border: 1px solid rgba(0, 240, 255, 0.3);
        }}

        /* --- FOOTER --- */
        footer {{
            text-align: center;
            color: var(--text-muted);
            font-size: 12px;
            padding: 20px 0;
            border-top: 1px solid var(--border-card);
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- HEADER -->
        <header>
            <div class="brand">
                <div class="tesla-logo">
                    <svg viewBox="0 0 24 24">
                        <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8 0-1.82.62-3.49 1.66-4.83l12.17 12.17C16.49 20.38 14.32 21 12 21zm6.34-3.17L6.17 5.66C7.51 4.62 9.18 4 11 4c4.97 0 9 4.03 9 9 0 1.82-.62 3.49-1.66 4.83z"/>
                    </svg>
                </div>
                <div class="brand-title">
                    <h1>{vehicle_info.get('name', 'Tesla Vehicle')} Log Dashboard</h1>
                    <p>VIN: {vehicle_info.get('vin', 'N/A')} &bull; Last Synced: {vehicle_info.get('last_synced', 'Just now')}</p>
                </div>
            </div>
            <div class="status-badge">
                <div class="status-dot"></div>
                {vehicle_info.get('state', 'ONLINE')}
            </div>
        </header>

        <!-- KPI GRID -->
        <div class="kpi-grid">
            <div class="kpi-card green">
                <div class="kpi-header">
                    <span class="kpi-title">Free Supercharging Savings</span>
                    <div class="kpi-icon">
                        <svg viewBox="0 0 24 24"><path fill="#00E676" d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>
                    </div>
                </div>
                <div class="kpi-value">${stats.get('total_savings_usd', 0.0):,.2f}</div>
                <div class="kpi-subtext">Saved across <span class="highlight-green">{stats.get('total_supercharging_kwh', 0.0):,.1f} kWh</span> of free energy</div>
            </div>

            <div class="kpi-card red">
                <div class="kpi-header">
                    <span class="kpi-title">Current Odometer</span>
                    <div class="kpi-icon">
                        <svg viewBox="0 0 24 24"><path fill="#E82127" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>
                    </div>
                </div>
                <div class="kpi-value">{float(odometer_history.get(current_point['label'], 0) if current_point else 0):,.1f} <span style="font-size:18px;">mi</span></div>
                <div class="kpi-subtext">Lifetime average: <span class="highlight-green">{stats.get('lifetime_avg_monthly', 0.0):,.1f} mi/mo</span> ({stats.get('lifetime_avg_yearly', 0.0):,.0f} mi/yr)</div>
            </div>

            <div class="kpi-card cyan">
                <div class="kpi-header">
                    <span class="kpi-title">3-Month Driving Pace</span>
                    <div class="kpi-icon">
                        <svg viewBox="0 0 24 24"><path fill="#00F0FF" d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>
                    </div>
                </div>
                <div class="kpi-value">{stats.get('avg_monthly_3m', 0.0):,.1f} <span style="font-size:18px;">mi/mo</span></div>
                <div class="kpi-subtext">Last 90 days rolling monthly average</div>
            </div>

            <div class="kpi-card amber">
                <div class="kpi-header">
                    <span class="kpi-title">6-Month Driving Pace</span>
                    <div class="kpi-icon">
                        <svg viewBox="0 0 24 24"><path fill="#FFB300" d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10h-4v4h-2v-4H7v-2h4V7h2v4h4v2z"/></svg>
                    </div>
                </div>
                <div class="kpi-value">{stats.get('avg_monthly_6m', 0.0):,.1f} <span style="font-size:18px;">mi/mo</span></div>
                <div class="kpi-subtext">Last 180 days rolling monthly average</div>
            </div>
        </div>

        <!-- CHARTS GRID -->
        <div class="charts-grid">
            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">Odometer Mileage Progression</div>
                </div>
                <div class="chart-container">
                    <canvas id="odoChart"></canvas>
                </div>
            </div>

            <div class="chart-card">
                <div class="chart-header">
                    <div class="chart-title">Monthly Miles Driven</div>
                </div>
                <div class="chart-container">
                    <canvas id="distChart"></canvas>
                </div>
            </div>
        </div>

        <div class="section-card" style="margin-bottom:28px;">
            <div class="chart-header">
                <div class="chart-title">Monthly Free Supercharging & Savings</div>
            </div>
            <div class="chart-container" style="height:280px;">
                <canvas id="chargingChart"></canvas>
            </div>
        </div>

        <!-- DATA TABLES SECTION -->
        <div class="section-card">
            <div class="table-controls">
                <div class="tabs">
                    <button class="tab-btn active" onclick="switchTab('sessions')">Supercharging Sessions ({len(parsed_sessions)})</button>
                    <button class="tab-btn" onclick="switchTab('odometer')">Odometer Log ({len(parsed_odo)})</button>
                </div>
                <div class="search-box">
                    <svg viewBox="0 0 24 24"><path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/></svg>
                    <input type="text" id="searchInput" placeholder="Search sessions or dates..." onkeyup="filterTables()">
                </div>
            </div>

            <!-- SESSIONS TABLE -->
            <div id="sessionsTab" class="table-wrapper">
                <table id="sessionsTable">
                    <thead>
                        <tr>
                            <th>Date / Time</th>
                            <th>Location / Station</th>
                            <th>Energy Added</th>
                            <th>Session Rate</th>
                            <th>Monetary Savings</th>
                            <th>Pricing Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''<tr>
                            <td style="font-weight:500;">{s['date_formatted']}</td>
                            <td>{s['site']}</td>
                            <td><strong>{s['energy_kwh']}</strong> kWh</td>
                            <td>${s['rate_usd']:.3f} / kWh</td>
                            <td style="color:var(--accent-green); font-weight:600;">+${s['savings_usd']:.2f}</td>
                            <td><span class="badge badge-free">FREE (NO CHARGE)</span></td>
                        </tr>''' for s in parsed_sessions[:100]])}
                    </tbody>
                </table>
            </div>

            <!-- ODOMETER TABLE -->
            <div id="odometerTab" class="table-wrapper" style="display:none;">
                <table id="odometerTable">
                    <thead>
                        <tr>
                            <th>Date / Label</th>
                            <th>Odometer Reading</th>
                            <th>Entry Type</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f'''<tr>
                            <td style="font-weight:500;">{o['full_key']}</td>
                            <td><strong>{o['val']:,.2f}</strong> mi</td>
                            <td>
                                <span class="badge {'badge-raw' if not o['is_baseline'] else 'badge-baseline'}">
                                    {'ESTIMATED MONTHLY BASELINE' if o['is_baseline'] else ('CURRENT READING' if o['is_current'] else 'RAW READING')}
                                </span>
                            </td>
                        </tr>''' for o in parsed_odo])}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- FOOTER -->
        <footer>
            Tesla Fleet Logger Dashboard &bull; Generated cleanly without sensitive credentials or secret keys.
        </footer>
    </div>

    <!-- JAVASCRIPT FOR CHARTS & INTERACTIVITY -->
    <script>
        // Data Injection from Python Generator
        const rawOdoData = {json_raw_points};
        const baselineOdoData = {json_baseline_points};
        const monthLabels = {json_month_labels};
        const monthKwh = {json_month_kwh};
        const monthSavings = {json_month_savings};
        const distLabels = {json_dist_labels};
        const distValues = {json_dist_values};

        // 1. ODOMETER LINE CHART
        const ctxOdo = document.getElementById('odoChart').getContext('2d');
        new Chart(ctxOdo, {{
            type: 'line',
            data: {{
                datasets: [
                    {{
                        label: 'Raw & Current Readings',
                        data: rawOdoData,
                        borderColor: '#E82127',
                        backgroundColor: 'rgba(232, 33, 39, 0.1)',
                        pointBackgroundColor: '#E82127',
                        pointRadius: 5,
                        pointHoverRadius: 8,
                        tension: 0.2,
                        fill: true
                    }},
                    {{
                        label: '1st-of-Month Baselines',
                        data: baselineOdoData,
                        borderColor: '#00F0FF',
                        backgroundColor: 'transparent',
                        pointBackgroundColor: '#00F0FF',
                        pointRadius: 4,
                        borderDash: [5, 5],
                        tension: 0.2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ labels: {{ color: '#F3F4F6', font: {{ family: 'Inter' }} }} }}
                }},
                scales: {{
                    x: {{
                        type: 'category',
                        labels: {json.dumps(all_dates)},
                        ticks: {{ color: '#9CA3AF', maxTicksLimit: 8 }},
                        grid: {{ color: 'rgba(255,255,255,0.05)' }}
                    }},
                    y: {{
                        ticks: {{ color: '#9CA3AF' }},
                        grid: {{ color: 'rgba(255,255,255,0.05)' }}
                    }}
                }}
            }}
        }});

        // 2. MONTHLY DISTANCE BAR CHART
        const ctxDist = document.getElementById('distChart').getContext('2d');
        new Chart(ctxDist, {{
            type: 'bar',
            data: {{
                labels: distLabels,
                datasets: [{{
                    label: 'Miles Driven',
                    data: distValues,
                    backgroundColor: 'rgba(0, 240, 255, 0.4)',
                    borderColor: '#00F0FF',
                    borderWidth: 1,
                    borderRadius: 6
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#9CA3AF' }}, grid: {{ display: false }} }},
                    y: {{ ticks: {{ color: '#9CA3AF' }}, grid: {{ color: 'rgba(255,255,255,0.05)' }} }}
                }}
            }}
        }});

        // 3. MONTHLY CHARGING DUAL CHART
        const ctxCharge = document.getElementById('chargingChart').getContext('2d');
        new Chart(ctxCharge, {{
            type: 'bar',
            data: {{
                labels: monthLabels,
                datasets: [
                    {{
                        type: 'bar',
                        label: 'Energy Added (kWh)',
                        data: monthKwh,
                        backgroundColor: 'rgba(232, 33, 39, 0.5)',
                        borderColor: '#E82127',
                        borderWidth: 1,
                        borderRadius: 6,
                        yAxisID: 'y'
                    }},
                    {{
                        type: 'line',
                        label: 'Monetary Savings ($)',
                        data: monthSavings,
                        borderColor: '#00E676',
                        backgroundColor: '#00E676',
                        borderWidth: 2,
                        pointRadius: 4,
                        yAxisID: 'y1'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ labels: {{ color: '#F3F4F6' }} }} }},
                scales: {{
                    x: {{ ticks: {{ color: '#9CA3AF' }}, grid: {{ display: false }} }},
                    y: {{
                        type: 'linear',
                        position: 'left',
                        ticks: {{ color: '#9CA3AF' }},
                        grid: {{ color: 'rgba(255,255,255,0.05)' }}
                    }},
                    y1: {{
                        type: 'linear',
                        position: 'right',
                        ticks: {{ color: '#00E676' }},
                        grid: {{ display: false }}
                    }}
                }}
            }}
        }});

        // Tab Switching
        function switchTab(tabName) {{
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            if (tabName === 'sessions') {{
                document.getElementById('sessionsTab').style.display = 'block';
                document.getElementById('odometerTab').style.display = 'none';
                event.target.classList.add('active');
            }} else {{
                document.getElementById('sessionsTab').style.display = 'none';
                document.getElementById('odometerTab').style.display = 'block';
                event.target.classList.add('active');
            }}
        }}

        // Search Filter
        function filterTables() {{
            const input = document.getElementById('searchInput').value.toLowerCase();
            ['sessionsTable', 'odometerTable'].forEach(tableId => {{
                const table = document.getElementById(tableId);
                const rows = table.getElementsByTagName('tr');
                for (let i = 1; i < rows.length; i++) {{
                    const text = rows[i].innerText.toLowerCase();
                    rows[i].style.display = text.includes(input) ? '' : 'none';
                }}
            }});
        }}
    </script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"DEBUG: Web Dashboard generated successfully at '{output_path}'")
