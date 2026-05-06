# WatchBot 👁️

> A unified monitoring plugin for [Hermes Agent](https://hermes-agent.nousresearch.com) combining homelab infrastructure, smart home, social media, and web content monitoring into a single extensible plugin with agent tools, CLI commands, and a dashboard.

## Why WatchBot?

Running a homelab means keeping tabs on:
- **Proxmox LXCs** — are critical containers up? (SWAG, Pi-hole, Trilium, Hermes itself)
- **Home Assistant** — temperature, sensors, device status
- **X/Twitter** — timeline monitoring, keyword tracking, DMs
- **Blogs/RSS** — new posts from your favorite sources
- **System health** — disk, memory, CPU, Docker containers

WatchBot unifies all of these into a single Hermes plugin with zero-touch hooks, agent-accessible tools, CLI commands, and a real-time dashboard.

## Quick Start

```bash
# Install from source
pip install -e /path/to/watchbot

# Or install with extras
pip install -e ".[dashboard,twitter]"

# Register with Hermes
hermes plugin install watchbot

# Run initial setup
hermes watchbot setup

# Check status
hermes watchbot status
```

## Architecture

```
watchbot/
├── plugin.yaml           # Hermes plugin registration
├── __init__.py           # Plugin entry point, hooks, tool registration
├── SKILL.md              # Agent-facing documentation
│
├── core/
│   ├── config.py         # Configuration loading + validation
│   ├── state.py          # SQLite state management
│   └── alerts.py         # Alert routing, dedup, rate-limiting
│
├── monitors/
│   ├── homelab.py        # Proxmox LXC watchdog via SSH
│   ├── home_assistant.py # Home Assistant API sensor queries
│   ├── x_twitter.py      # X/Twitter v2 API (timeline, search, DMs)
│   ├── blogwatcher.py    # RSS/Atom feed monitoring
│   ├── system.py          # Local system health (disk, CPU, mem, net)
│   └── docker.py          # Docker container health via socket
│
├── tools/
│   ├── dashboard.py      # Aggregated status data for the agent
│   ├── alerts.py         # Alert management tools
│   └── queries.py        # Per-source query tools
│
├── cli/
│   └── commands.py       # `hermes watchbot` CLI commands
│
└── web/
    └── dashboard.py      # Flask dashboard (optional)
```

## Features

### 🔧 Agent Tools (available to Hermes via tool calls)

| Tool | Description |
|------|-------------|
| `watchbot_status` | Get overall system status (all monitors) |
| `watchbot_alert` | Acknowledge, mute, or escalate an alert |
| `watchbot_query` | Query a specific monitor for detailed data |
| `watchbot_dashboard` | Get dashboard-ready aggregated data |

### 🔌 Hooks (automatic, zero-agent-effort)

| Hook | Trigger | Action |
|------|---------|--------|
| `on_session_end` | Session ends | Logs any alert-worthy state changes |
| `post_tool_call` | After tool execution | Detects state-affecting changes |

### 🖥️ CLI Commands

```bash
hermes watchbot setup         # Initial setup wizard
hermes watchbot status        # Overall status
hermes watchbot health        # System health snapshot
hermes watchbot lxc           # Proxmox LXC status
hermes watchbot ha            # Home Assistant sensor values
hermes watchbot twitter       # X/Twitter timeline
hermes watchbot blogs         # RSS feed latest
hermes watchbot docker        # Docker container status
hermes watchbot alert         # Alert management
hermes watchbot dashboard     # Launch dashboard server
```

## Monitors

### Proxmox LXC
SSH-based health checks for Proxmox containers. Auto-detects critical vs optional LXCs. Supports auto-restart with Telegram escalation.

### Home Assistant
Reads sensor states, device status, and area summaries from your local HA instance. Supports templated queries.

### X/Twitter
Timeline monitoring, keyword search, DM polling. Uses OAuth 2.0 PKCE via Hermes auth flow.

### Blogwatcher
RSS/Atom feed polling with configurable update intervals. Dedup-aware.

### System Health
Disk usage, memory pressure, CPU load, network latency, temperature. Monitors the Hermes host itself.

### Docker
Container health, resource usage, restart counts via Docker socket.

## Configuration

WatchBot reads from `~/.hermes/watchbot.yaml`:

```yaml
watchbot:
  homelab:
    host: 192.168.0.2
    user: root
    critical: [100, 105, 106, 107, 103, 104, 111]
    optional: [101, 108, 109, 110, 115, 117, 128]

  home_assistant:
    url: http://192.168.0.244:8123
    token_env: HA_TOKEN
    sensors:
      - sensor.my_ecobee_current_temperature
      - sensor.wy27_temperature
      - sensor.wyyr_temperature

  twitter:
    enabled: false
    check_interval_minutes: 15
    keywords: []

  blogs:
    enabled: true
    check_interval_hours: 6
    feeds:
      - https://blog.nousresearch.com/feed
      - https://news.ycombinator.com/rss

  system:
    disk_threshold_pct: 85
    mem_threshold_pct: 90
    cpu_threshold_pct: 95

  docker:
    enabled: true
    socket: /var/run/docker.sock

  alerts:
    telegram:
      enabled: true
      chat_id: 642899617
    email:
      enabled: false
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .
```

## License

MIT
