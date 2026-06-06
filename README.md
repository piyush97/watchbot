# WatchBot 👁️

> Unified homelab + social media monitoring plugin for [Hermes Agent](https://hermes-agent.nousresearch.com)

[![Hermes Plugin](https://img.shields.io/badge/Hermes-Plugin-8B5CFE)](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins)
[![skills.sh](https://skills.sh/b/piyush97/watchbot)](https://skills.sh/piyush97/watchbot)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/piyush97/watchbot)](https://github.com/piyush97/watchbot/stargazers)

**WatchBot** combines Proxmox LXC watchdog, Home Assistant sensor queries, X/Twitter monitoring, RSS/blog feed tracking, system health, and Docker container monitoring into a single Hermes Agent plugin with agent tools, CLI commands, lifecycle hooks, and a live dashboard.

```bash
npx skills add piyush97/watchbot
hermes plugins enable watchbot
hermes watchbot status
```

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

## Quick Start

```bash
# Install via skills.sh (recommended)
npx skills add piyush97/watchbot

# Or clone directly
cd ~/.hermes/plugins
git clone https://github.com/piyush97/watchbot.git

# Enable
hermes plugins enable watchbot

# Run setup wizard
hermes watchbot setup

# Check status
hermes watchbot status

# Launch dashboard
hermes watchbot dashboard
# → Open http://127.0.0.1:9099
```

## Configuration

Auto-generated at `~/.hermes/watchbot.yaml`:

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

## Publishing Channels

| Channel | Status | Link |
|---------|--------|------|
| skills.sh | ✅ Listed | [piyush97/watchbot](https://skills.sh/piyush97/watchbot) |
| PyPI | ⏳ Planned | `pip install watchbot` |
| Hermes optional-skills | ⏳ PR planned | PR to NousResearch/hermes-agent |
| OpenClaw Hub | ⏳ Planned | `hermes skills tap add` |

## Requirements

- Python 3.11+
- Hermes Agent v0.15+
- SSH key access to Proxmox host (for homelab monitor)
- HA_TOKEN env var (for Home Assistant)
- xurl CLI (for X/Twitter, optional)
- Docker socket at `/var/run/docker.sock` (for Docker, optional)

## X/Twitter Source Options

WatchBot's built-in X/Twitter monitor uses `xurl` for timeline and keyword
snapshots inside Hermes. OpenClaw users who need deeper X/Twitter workflows can
run TweetClaw beside WatchBot for structured tweet search, search tweet replies,
follower export, explicit monitors, webhooks, media workflows, giveaway draws,
and approval-gated posting.

See [X/Twitter Source Options](docs/x-twitter-source-options.md) for setup,
credential boundaries, and a WatchBot plus TweetClaw workflow.

## Related

- [Hermes Agent Plugins](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins/)
- [Build a Hermes Plugin](https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin/)
- [skills.sh](https://skills.sh) — Agent skill marketplace

## License

MIT
