"""Web dashboard for WatchBot — Flask-based real-time monitoring UI."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from watchbot.core.config import load_config
from watchbot.tools.dashboard import get_dashboard_data

logger = logging.getLogger(__name__)


def create_app(cfg: Optional[Dict] = None) -> Any:
    """Create a Flask dashboard app."""
    from flask import Flask, jsonify, render_template_string

    app = Flask(__name__)
    config = cfg or load_config()

    @app.route("/")
    def index():
        return render_template_string(HTML_TEMPLATE)

    @app.route("/api/status")
    def api_status():
        data = get_dashboard_data(config)
        return jsonify(data)

    @app.route("/api/alerts")
    def api_alerts():
        from watchbot.core.state import get_active_alerts
        alerts = get_active_alerts()
        return jsonify({"count": len(alerts), "alerts": alerts})

    @app.route("/api/monitor/<name>")
    def api_monitor(name: str):
        from watchbot.tools.queries import query_monitor_tool
        data = query_monitor_tool(name)
        return jsonify(data)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})

    return app


def run_dashboard(cfg: Optional[Dict] = None,
                  host: str = "127.0.0.1", port: int = 9099) -> None:
    """Run the dashboard server."""
    app = create_app(cfg)
    print(f"\n  WatchBot Dashboard: http://{host}:{port}")
    print(f"  API: http://{host}:{port}/api/status\n")
    app.run(host=host, port=port, debug=False)


# Inline HTML template for the dashboard
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>WatchBot Dashboard</title>
  <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #0d1117; color: #c9d1d9; padding: 20px; }
    .header { display: flex; align-items: center; justify-content: space-between;
              margin-bottom: 24px; }
    .header h1 { font-size: 24px; font-weight: 600; }
    .health-badge { padding: 6px 16px; border-radius: 20px; font-weight: 600;
                    font-size: 14px; text-transform: uppercase; }
    .health-ok { background: #1b4a1b; color: #3fb950; }
    .health-warning { background: #4a3b1b; color: #d29922; }
    .health-critical { background: #4a1b1b; color: #f85149; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 16px; margin-top: 16px; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            padding: 16px; }
    .card h3 { font-size: 14px; color: #8b949e; text-transform: uppercase;
               letter-spacing: 0.5px; margin-bottom: 12px; }
    .card .value { font-size: 32px; font-weight: 700; }
    .card .sub { font-size: 13px; color: #8b949e; margin-top: 4px; }
    .bar { height: 8px; background: #21262d; border-radius: 4px; margin-top: 8px;
           overflow: hidden; }
    .bar-fill { height: 100%; border-radius: 4px; transition: width 0.5s; }
    .alerts-list { margin-top: 8px; }
    .alert-item { padding: 8px 0; border-bottom: 1px solid #21262d;
                  display: flex; gap: 8px; align-items: start; }
    .alert-sev-critical { color: #f85149; }
    .alert-sev-warning { color: #d29922; }
    .alert-sev-info { color: #58a6ff; }
    .refresh { color: #58a6ff; text-decoration: none; font-size: 13px;
               cursor: pointer; }
    .refresh:hover { text-decoration: underline; }
    #timestamp { font-size: 12px; color: #484f58; margin-top: 16px; text-align: center; }
  </style>
</head>
<body>
<div class="header">
  <h1>👁️ WatchBot</h1>
  <span id="healthBadge" class="health-badge">Loading...</span>
  <a class="refresh" onclick="fetchData()">↻ Refresh</a>
</div>
<div class="grid" id="grid"></div>
<div id="alertsSection"></div>
<div id="timestamp"></div>

<script>
async function fetchData() {
  const resp = await fetch('/api/status');
  const data = await resp.json();

  // Health badge
  const badge = document.getElementById('healthBadge');
  badge.textContent = data.health || 'unknown';
  badge.className = 'health-badge health-' + (data.health || 'unknown');

  // Grid
  const grid = document.getElementById('grid');
  grid.innerHTML = '';

  const monitors = data.monitors || {};
  for (const [name, mon] of Object.entries(monitors)) {
    if (typeof mon === 'string') {
      grid.innerHTML += `<div class="card"><h3>${name}</h3><div class="value" style="color:#f85149">Error</div><div class="sub">${mon}</div></div>`;
      continue;
    }
    let content = '';
    switch(name) {
      case 'system':
        const disk = mon.disk?.used_pct || 0;
        const mem = mon.memory?.used_pct || 0;
        const cpu = mon.cpu?.used_pct || 0;
        content = `
          <div class="value">${disk.toFixed(1)}%</div>
          <div class="sub">Disk</div>
          <div class="bar"><div class="bar-fill" style="width:${disk}%;background:${disk>85?'#f85149':disk>70?'#d29922':'#3fb950'}"></div></div>
          <div style="margin-top:12px;">
            <div style="display:flex;justify-content:space-between;font-size:13px;">
              <span>CPU ${cpu.toFixed(1)}%</span>
              <span>MEM ${mem.toFixed(1)}%</span>
            </div>
            <div class="bar"><div class="bar-fill" style="width:${cpu}%;background:${cpu>90?'#f85149':cpu>80?'#d29922':'#3fb950'};width:${cpu}%"></div></div>
            <div class="bar" style="margin-top:4px;"><div class="bar-fill" style="width:${mem}%;background:${mem>90?'#f85149':mem>80?'#d29922':'#3fb950'};width:${mem}%"></div></div>
          </div>
          ${mon.temperature ? `<div class="sub">Temp: ${mon.temperature}°C</div>` : ''}`;
        break;
      case 'homelab':
        const run = mon.running || 0;
        const total = mon.total || 0;
        const pct = total ? (run/total*100) : 0;
        content = `<div class="value">${run}/${total}</div>
          <div class="sub">Containers running</div>
          <div class="bar"><div class="bar-fill" style="width:${pct}%;background:${mon.health==='critical'?'#f85149':mon.health==='warning'?'#d29922':'#3fb950'}"></div></div>`;
        break;
      case 'docker':
        const drun = mon.running || 0;
        const dtotal = mon.total || 0;
        const dpct = dtotal ? (drun/dtotal*100) : 0;
        content = `<div class="value">${drun}/${dtotal}</div>
          <div class="sub">Containers running</div>
          <div class="bar"><div class="bar-fill" style="width:${dpct}%;background:#3fb950"></div></div>`;
        break;
      case 'home_assistant':
        const sensors = Object.entries(mon.sensors || {}).slice(0, 3);
        content = `<div class="value">${mon.count || 0}</div><div class="sub">Sensors</div>`;
        sensors.forEach(([k,v]) => {
          content += `<div style="font-size:13px;margin-top:4px;"><span style="color:#8b949e">${k}:</span> ${v}</div>`;
        });
        break;
      case 'blogs':
        content = `<div class="value">${mon.new_posts || 0}</div>
          <div class="sub">New posts</div>
          ${(mon.latest_posts||[]).slice(0,3).map(p => `<div style="font-size:12px;margin-top:4px;">📰 ${p.title}</div>`).join('')}`;
        break;
      case 'twitter':
        content = `<div class="value">${mon.keyword_matches || 0}</div>
          <div class="sub">Keyword matches</div>
          <div class="sub">Timeline: ${mon.timeline_tweets || 0} tweets</div>`;
        break;
      default:
        content = `<div class="value">${mon.health || '?'}</div>`;
    }
    grid.innerHTML += `<div class="card"><h3>${name.replace('_',' ')}</h3>${content}</div>`;
  }

  // Alerts
  const alertsResp = await fetch('/api/alerts');
  const alertsData = await alertsResp.json();
  const alertsDiv = document.getElementById('alertsSection');
  if (alertsData.alerts?.length) {
    alertsDiv.innerHTML = `<div class="card" style="margin-top:16px;"><h3>🚨 Active Alerts (${alertsData.count})</h3>
      <div class="alerts-list">${alertsData.alerts.slice(0,10).map(a =>
        `<div class="alert-item"><span class="alert-sev-${a.severity}">●</span>
         <strong>${a.title}</strong></div>`).join('')}</div></div>`;
  } else {
    alertsDiv.innerHTML = `<div class="card" style="margin-top:16px;"><h3>✅ No Active Alerts</h3></div>`;
  }

  document.getElementById('timestamp').textContent =
    'Last updated: ' + (data.timestamp || '').slice(0,19).replace('T',' ');
}

fetchData();
setInterval(fetchData, 30000);
</script>
</body>
</html>"""
