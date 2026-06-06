---
name: watchbot
description: "Unified homelab + social media monitoring for Hermes Agent. Combines Proxmox LXC watchdog, Home Assistant, X/Twitter, RSS feeds, system health, and Docker into a single plugin with agent tools, CLI, and dashboard."
version: 0.1.0
author: Piyush Mehta (@piyush97)
metadata:
  hermes:
    tags: [monitoring, homelab, proxmox, home-assistant, docker, twitter, rss, system-health, dashboard]
    related_skills: [homelab-watchdog, xurl, blogwatcher]
---

# WatchBot 👁️

Unified monitoring plugin for Hermes Agent combining multiple data sources into a single status view with agent tools, CLI commands, hooks, and a web dashboard.

## When to Use This Skill

Trigger when the user:
- Wants to check overall system/home/social health
- Asks "what's the status of my homelab?"
- Wants docker container status
- Wants current temperature from Home Assistant
- Wants the latest X/Twitter mentions or timeline
- Wants RSS/blog updates
- Wants to see system resource usage (disk, CPU, memory)

## Agent Tools

### watchbot_status
```python
# Returns aggregated data from all monitors
result = tools.watchbot_status()
print(f"Health: {result['health']}")
for name, mon in result['monitors'].items():
    print(f"  {name}: {mon.get('health', '?')}")
```

### watchbot_query
```python
# Query a specific monitor
homelab = tools.watchbot_query(monitor="homelab")
print(f"LXCs: {homelab['running']}/{homelab['total']} running")

system = tools.watchbot_query(monitor="system")
print(f"CPU: {system['cpu']['used_pct']}% | Disk: {system['disk']['used_pct']}%")
```

### watchbot_alert
```python
# List active alerts
alerts = tools.watchbot_alert(action="list")
print(alerts['summary'])

# Trigger a manual alert
tools.watchbot_alert(action="trigger", source="manual",
    severity="warning", title="Disk check needed",
    message="/dev/sda1 at 90%")
```

## CLI Commands

```bash
hermes watchbot status        # Full status across all monitors
hermes watchbot health        # Disk / CPU / memory snapshot
hermes watchbot lxc           # Proxmox LXC containers
hermes watchbot ha            # Home Assistant sensors
hermes watchbot twitter       # X/Twitter timeline + keyword matches
hermes watchbot blogs         # New RSS/blog posts
hermes watchbot docker        # Docker containers
hermes watchbot alerts        # Active alerts
hermes watchbot setup         # Initial configuration wizard
hermes watchbot status --json # Machine-readable JSON output
```

## Dashboard

```bash
hermes watchbot dashboard
# Opens http://127.0.0.1:9099 with live monitoring UI
```

## Configuration

Edit `~/.hermes/watchbot.yaml`:

```yaml
watchbot:
  homelab:
    host: 192.168.0.2
    critical: [100, 105, 106, 107, 103, 104, 111]
    optional: [101, 108, 109, 110, 115, 117, 128]
  home_assistant:
    url: http://192.168.0.244:8123
    token_env: HA_TOKEN
    sensors:
      - sensor.my_ecobee_current_temperature
  twitter:
    enabled: true
    keywords: [hermesagent, piyush97]
  blogs:
    feeds:
      - https://blog.nousresearch.com/feed
  system:
    disk_threshold_pct: 85
  docker:
    enabled: true
```

## Architecture

```
  ┌─────────────────────────────────────────────────────┐
  │                   Agent Tools / CLI                 │
  ├──────────┬──────────┬──────────┬──────────┬─────────┤
  │ Homelab  │  HA      │ Twitter  │  Blogs   │ System  │
  │ (SSH)    │  (API)   │  (xurl)  │  (RSS)   │ (/proc) │
  ├──────────┴──────────┴──────────┴──────────┴─────────┤
  │              Core: Config + State + Alerts           │
  ├──────────────────────────────────────────────────────┤
  │              SQLite DB + YAML Config                  │
  └──────────────────────────────────────────────────────┘
```

## Pitfalls

1. **SSH key for Proxmox** — The homelab monitor needs SSH key-based access to `root@192.168.0.2`. Ensure `~/.ssh/id_ed25519` is in the authorized_keys on the Proxmox host.
2. **HA token** — Set `HA_TOKEN` env var or the config's `token_env` name. The token is read from environment at query time.
3. **Twitter requires xurl CLI** — Install and auth with `xurl` separately. Without it, the Twitter monitor returns empty.
4. **Docker socket** — The plugin reads `/var/run/docker.sock`. If running Hermes in a container, mount the socket.
5. **Feedparser optional** — For direct RSS parsing without blogwatcher-cli: `pip install feedparser`
6. **CLI caveat** — Hermes top-level CLI doesn't auto-discover external plugin commands. Use `python3 -m watchbot <command>` or add this bash alias to `~/.bash_aliases`:
   ```bash
   hermes() {
       if [ "$1" = "watchbot" ]; then shift; python3 -m watchbot "$@"
       else command hermes "$@"; fi
   }
   ```
