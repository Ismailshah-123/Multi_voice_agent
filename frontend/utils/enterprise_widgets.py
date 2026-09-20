"""
utils/enterprise_widgets.py

WHAT THIS FILE DOES:
This is the "extra level" visual layer — real JavaScript-driven widgets
(not just static HTML/CSS like theme.py) rendered via
st.components.v1.html: numbers that count up from zero on load, mini
sparkline trend charts inside each KPI card, and radial progress gauges
for things like plan usage. Uses Chart.js from CDN for the charts and
vanilla JS for the count-up animation — no extra Python dependencies.

These are visually a step above Plotly's default styling because every
pixel (colors, glow, animation easing) is hand-specified to match the
platform's dark purple/pink enterprise theme, rather than using a
general-purpose charting library's default look.
"""

import streamlit.components.v1 as components
import json


def render_animated_kpi_row(kpis: list[dict], height: int = 170):
    """
    kpis: list of {"label": str, "value": number, "prefix": str, "suffix": str,
                    "sparkline": list[number] (optional), "color": str (optional hex)}

    Renders a row of KPI cards where the number animates counting up from
    0 to its final value on load, with an optional mini sparkline trend
    line underneath. This is the "wow" moment for a client demo.
    """
    cards_html = ""
    for i, kpi in enumerate(kpis):
        color = kpi.get("color", "#1D4ED8")
        has_sparkline = bool(kpi.get("sparkline"))
        sparkline_canvas = f'<canvas id="spark-{i}" height="30"></canvas>' if has_sparkline else ""

        cards_html += f"""
        <div class="ent-kpi-card" style="border-top-color: {color};">
            <div class="ent-kpi-label">{kpi['label']}</div>
            <div class="ent-kpi-value" id="kpi-value-{i}" style="color: {color};">0</div>
            <div class="ent-kpi-sub">{kpi.get('sub', '')}</div>
            {sparkline_canvas}
        </div>
        """

    widget_html = f"""
    <style>
        .ent-kpi-row {{ display: flex; gap: 14px; flex-wrap: wrap; font-family: 'Manrope', sans-serif; }}
        .ent-kpi-card {{
            flex: 1; min-width: 160px;
            background: #FFFFFF;
            border: 1px solid rgba(11, 37, 69, 0.2);
            border-top: 3px solid #1D4ED8;
            border-radius: 16px; padding: 18px 16px;
            transition: transform 0.25s ease, box-shadow 0.25s ease;
        }}
        .ent-kpi-card:hover {{ transform: translateY(-5px); box-shadow: 0 14px 36px rgba(11, 37, 69,0.35); }}
        .ent-kpi-label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1.5px; color: #5A6B85; font-weight: 600; margin-bottom: 6px; }}
        .ent-kpi-value {{ font-size: 30px; font-weight: 700; font-family: 'Manrope', sans-serif; }}
        .ent-kpi-sub {{ font-size: 11px; color: #5A6B85; margin-top: 4px; margin-bottom: 8px; }}
    </style>

    <div class="ent-kpi-row">{cards_html}</div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
        const kpiData = {json.dumps(kpis)};

        kpiData.forEach((kpi, i) => {{
            const el = document.getElementById('kpi-value-' + i);
            const target = kpi.value;
            const prefix = kpi.prefix || '';
            const suffix = kpi.suffix || '';
            const duration = 1200;
            const startTime = performance.now();

            function animate(now) {{
                const elapsed = now - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const current = target * eased;
                const display = Number.isInteger(target) ? Math.round(current) : current.toFixed(1);
                el.innerText = prefix + display.toLocaleString() + suffix;
                if (progress < 1) requestAnimationFrame(animate);
            }}
            requestAnimationFrame(animate);

            if (kpi.sparkline && kpi.sparkline.length > 1) {{
                const canvas = document.getElementById('spark-' + i);
                if (canvas) {{
                    new Chart(canvas, {{
                        type: 'line',
                        data: {{
                            labels: kpi.sparkline.map((_, idx) => idx),
                            datasets: [{{
                                data: kpi.sparkline,
                                borderColor: kpi.color || '#1D4ED8',
                                backgroundColor: (kpi.color || '#1D4ED8') + '22',
                                fill: true, tension: 0.4, pointRadius: 0, borderWidth: 2,
                            }}]
                        }},
                        options: {{
                            responsive: true, maintainAspectRatio: false,
                            plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }},
                            scales: {{ x: {{ display: false }}, y: {{ display: false }} }},
                            animation: {{ duration: 1000 }}
                        }}
                    }});
                }}
            }}
        }});
    </script>
    """
    components.html(widget_html, height=height)


def render_radial_gauge(label: str, percent: float, color: str = "#1D4ED8", height: int = 200):
    """
    Renders a single animated radial/donut gauge (e.g. "62% of plan minutes used")
    using Chart.js doughnut chart with a center label overlay.
    """
    widget_html = f"""
    <style>
        .gauge-wrap {{ text-align: center; font-family: 'Manrope', sans-serif; position: relative; width: 160px; margin: 0 auto; }}
        .gauge-label {{ font-size: 12px; color: #5A6B85; text-transform: uppercase; letter-spacing: 1px; margin-top: 8px; }}
        .gauge-center {{ position: absolute; top: 42%; left: 50%; transform: translate(-50%, -50%); font-size: 24px; font-weight: 700; color: {color}; font-family: 'Manrope', sans-serif; }}
    </style>
    <div class="gauge-wrap">
        <div style="position: relative;">
            <canvas id="gauge-canvas" width="160" height="160"></canvas>
            <div class="gauge-center" id="gauge-center-label">0%</div>
        </div>
        <div class="gauge-label">{label}</div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <script>
        const ctx = document.getElementById('gauge-canvas');
        const targetPercent = {percent};
        new Chart(ctx, {{
            type: 'doughnut',
            data: {{
                datasets: [{{
                    data: [targetPercent, 100 - targetPercent],
                    backgroundColor: ['{color}', 'rgba(11,37,69,0.08)'],
                    borderWidth: 0,
                }}]
            }},
            options: {{
                cutout: '75%',
                plugins: {{ legend: {{ display: false }}, tooltip: {{ enabled: false }} }},
                animation: {{ animateRotate: true, duration: 1200 }}
            }}
        }});

        let current = 0;
        const label = document.getElementById('gauge-center-label');
        const step = () => {{
            if (current < targetPercent) {{
                current += Math.max(1, targetPercent / 30);
                label.innerText = Math.min(Math.round(current), targetPercent) + '%';
                requestAnimationFrame(step);
            }} else {{
                label.innerText = targetPercent + '%';
            }}
        }};
        requestAnimationFrame(step);
    </script>
    """
    components.html(widget_html, height=height)
