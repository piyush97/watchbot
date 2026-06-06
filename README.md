# WatchBot 👁️

> Unified homelab + social media monitoring plugin for [Hermes Agent](https://hermes-agent.nousresearch.com)

[![Hermes Plugin](https://img.shields.io/badge/Hermes-Plugin-8B5CFE)](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**WatchBot** combines Proxmox LXC watchdog, Home Assistant sensor queries, X/Twitter monitoring, RSS/blog feed tracking, system health, and Docker container monitoring into a single Hermes Agent plugin with agent tools, CLI commands, lifecycle hooks, and a live dashboard.

## Features

### 6 Monitors, One Plugin

| Monitor | What It Tracks | How |
|---------|---------------|-----|
| **Proxmox LXC** | Container status, auto-restart critical | SSH watchdog |
| **Home Assistant** | Sensors, devices, areas | REST API |
| **X/Twitter** | Timeline, keyword search, DMs | xurl CLI |
| **Blogs/RSS** | New posts from feeds | RSS/Atom |
| **System** | Disk, CPU, memory, temperature | /proc |
| **Docker** | Container health, restart counts | Unix socket |

### 4 Agent Tools

| Tool | What It Does |
|------|-------------|
| `watchbot_status` | Health across all monitors |
| `watchbot_query` | Detailed monitor data |
| `watchbot_alert` | Alert management (list/ack/resolve/trigger) |
| `watchbot_dashboard` | Dashboard-ready aggregated data |

### 11 CLI Commands

```bash
hermes watchbot status        # Full status (also: --json)
hermes watchbot health        # Disk/CPU/Memory snapshot
hermes watchbot lxc           # Proxmox LXC containers
hermes watchbot ha            # Home Assistant sensors
hermes watchbot twitter       # X/Twitter timeline
hermes watchbot blogs         # RSS feed latest
hermes watchbot docker        # Docker container status
hermes watchbot alerts        # Active alerts
hermes watchbot setup         # Configuration wizard
hermes watchbot dashboard     # Web UI at :9099
```

## Installation

### Option 1: Drop-in plugin (recommended)

```bash
cd ~/.hermes/plugins
git clone https://github.com/piyush97/watchbot.git
hermes plugins enable watchbot
```

### Option 2: Pip install

```bash
pip install git+https://github.com/piyush97/watchbot.git
hermes plugins enable watchbot
```

### Verify

```bash
hermes plugins list
# → ✓ watchbot v0.1.0 (4 tools, 2 hooks)

hermes watchbot status
```

## Quick Start

```bash
# 1. Run setup wizard
hermes watchbot setup

# 2. Launch the dashboard
hermes watchbot dashboard
# → Open http://127.0.0.1:9099

# 3. Check system health
hermes watchbot health

# 4. Full status
hermes watchbot status --json
```

## Configuration

Edit `~/.hermes/watchbot.yaml` (auto-generated on first use):

```yaml
watchbot:
  homelab:
    host: 192.168.0.2
    critical: [100, 105, 106, 107, 103, 104, 111]
  home_assistant:
    url: http://192.168.0.244:8123
    token_env: HA_TOKEN
    sensors: [sensor.my_ecobee_current_temperature]
  twitter:
    enabled: true
    keywords: [hermes, ai]
  blogs:
    feeds: [https://blog.nousresearch.com/feed]
  system:
    disk_threshold_pct: 85
  docker:
    enabled: true
```

## Agent Usage

The LLM can call WatchBot tools autonomously during a session:

```python
# Check overall health
status = tools.watchbot_status()
print(f"Health: {status['health']}")

# Query a specific monitor
sys_data = tools.watchbot_query(monitor="system")
print(f"CPU: {sys_data['cpu']['used_pct']}%")

# Manage alerts
tools.watchbot_alert(action="trigger", source="manual",
    severity="warning", title="Disk check needed")
```

## Architecture

```
┌───────────────────────────────────────────────────────────┐
│                   Agent Tools / CLI / Dashboard             │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────┤
│ Homelab  │  HA      │ Twitter  │  Blogs   │  System  │Docker│
│ (SSH)    │  (API)   │  (xurl)  │  (RSS)   │ (/proc)  │(sock)│
├──────────┴──────────┴──────────┴──────────┴──────────┴──────┤
│          Core: Config (YAML) + State (SQLite) + Alerts       │
├──────────────────────────────────────────────────────────────┤
│     Hermes Plugin API — register(ctx), hooks, CLI, skill      │
└──────────────────────────────────────────────────────────────┘
```

## Requirements

- Python 3.11+
- Hermes Agent v0.15+
- SSH key access to Proxmox host (for homelab monitor)
- HA_TOKEN env var (for Home Assistant)
- xurl CLI (for X/Twitter, optional)
- Docker socket at `/var/run/docker.sock` (for Docker, optional)

## Related

- [Hermes Agent Plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/)
- [Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/guides-tutorials/build-a-plugin/)
- [homelab-watchdog](https://github.com/NousResearch/hermes-agent/tree/main/optional-skills) — ancestor skill
- [xurl](https://github.com/NousResearch/hermes-agent/tree/main/optional-skills) — X/Twitter skill

## License

MIT
