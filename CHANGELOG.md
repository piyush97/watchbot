# Changelog

## 0.1.0 (2026-06-06)

Initial public release.

### Added
- **Proxmox LXC monitor** — SSH-based container health checks with auto-restart for critical containers
- **Home Assistant monitor** — Sensor state queries via REST API
- **X/Twitter monitor** — Timeline fetching and keyword search via xurl CLI
- **Blog/RSS monitor** — Feed monitoring with blogwatcher-cli + feedparser fallback
- **System health monitor** — Disk, CPU, memory, temperature via /proc
- **Docker container monitor** — Container health and stats via Unix socket
- **4 agent tools** — `watchbot_status`, `watchbot_query`, `watchbot_alert`, `watchbot_dashboard`
- **10 CLI commands** — status, health, lxc, ha, twitter, blogs, docker, alerts, setup, dashboard
- **Web dashboard** — Flask + Plotly with auto-refresh at http://127.0.0.1:9099
- **Alert system** — Rate-limited dispatch with severity classification, Telegram-ready templates
- **SQLite state** — Persistent alert history, monitor state, and data snapshots
- **Plugin hooks** — `on_session_end` status logging, `post_tool_call` CPU spike detection
- **Bundled skill** — Agent-facing docs via `skill_view("plugin:watchbot")`
- **Full test suite** — 11 unit tests covering config, state, alerts, and monitors
