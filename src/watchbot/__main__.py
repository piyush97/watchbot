#!/usr/bin/env python3
"""WatchBot CLI — standalone entry point for ``watchbot <command>``.

Usage:
    watchbot status          # Full system status
    watchbot status --json   # Machine-readable output
    watchbot health          # Disk/CPU/memory snapshot
    watchbot lxc             # Proxmox LXC containers
    watchbot ha              # Home Assistant sensors
    watchbot twitter         # X/Twitter timeline
    watchbot blogs           # RSS feed latest
    watchbot docker          # Docker container status
    watchbot alerts          # Active alerts
    watchbot setup           # Configuration wizard
    watchbot dashboard       # Launch web dashboard

Install: pip install /path/to/watchbot  # creates the ``watchbot`` binary
"""

import argparse
import sys


def main() -> None:
    from watchbot.cli.commands import register_cli, run_command

    parser = argparse.ArgumentParser(
        prog="watchbot",
        description="Unified homelab + social media monitoring",
    )
    parser.add_argument(
        "--version", action="store_true",
        help="Show version and exit",
    )

    register_cli(parser)

    args = parser.parse_args()

    if getattr(args, "version", False):
        from watchbot import __version__
        print(f"watchbot v{__version__}")
        return

    # Default to 'status' if no subcommand given
    if not getattr(args, "watchbot_command", None):
        parser.print_help()
        return

    sys.exit(run_command(args))


if __name__ == "__main__":
    main()
