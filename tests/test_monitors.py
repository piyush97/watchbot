"""Tests for WatchBot monitoring modules."""

from __future__ import annotations

from pathlib import Path



# ── Config tests ──────────────────────────────────────────────

class TestConfig:
    def test_defaults_loaded(self):
        """Config should return defaults when no file exists."""
        from watchbot.core.config import load_config
        cfg = load_config(Path("/tmp/nonexistent_watchbot.yaml"))
        assert "homelab" in cfg
        assert cfg["homelab"]["host"] == "192.168.0.2"
        assert cfg["system"]["disk_threshold_pct"] == 85

    def test_merge_overrides(self):
        """User config should deep-merge with defaults."""
        from watchbot.core.config import load_config
        import tempfile
        import yaml
        overrides = {"watchbot": {"homelab": {"host": "10.0.0.1"}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(overrides, f)
            cfg_path = Path(f.name)

        try:
            cfg = load_config(cfg_path)
            assert cfg["homelab"]["host"] == "10.0.0.1"
            assert cfg["system"]["disk_threshold_pct"] == 85  # From defaults
        finally:
            cfg_path.unlink()


# ── State tests ───────────────────────────────────────────────

class TestState:
    def test_set_and_get(self):
        """State should persist values per monitor+key."""
        from watchbot.core.state import get_state, set_state
        set_state("test", "foo", "bar")
        assert get_state("test", "foo") == "bar"

    def test_default_returned(self):
        """State should return default for missing keys."""
        from watchbot.core.state import get_state
        assert get_state("test", "nonexistent", 42) == 42

    def test_alert_roundtrip(self):
        """Alerts should be creatable and retrievable."""
        from watchbot.core.state import (
            create_alert,
            get_active_alerts,
            resolve_alert,
        )
        aid = create_alert("test", "warning", "Test alert", "Something happened")
        assert aid > 0

        alerts = get_active_alerts()
        assert any(a["id"] == aid for a in alerts)

        resolve_alert(aid)
        alerts = get_active_alerts()
        assert not any(a["id"] == aid for a in alerts)


# ── System monitor tests ──────────────────────────────────────

class TestSystemMonitor:
    def test_disk_usage_shape(self):
        """Disk usage should return expected keys."""
        from watchbot.monitors.system import get_disk_usage
        result = get_disk_usage("/")
        assert "total_gb" in result
        assert "used_gb" in result
        assert "used_pct" in result
        assert result["used_pct"] > 0

    def test_memory_usage_shape(self):
        """Memory usage should return expected keys."""
        from watchbot.monitors.system import get_memory_usage
        result = get_memory_usage()
        assert "total_gb" in result
        assert "used_pct" in result

    def test_cpu_usage_shape(self):
        """CPU usage should return expected keys."""
        from watchbot.monitors.system import get_cpu_usage
        result = get_cpu_usage()
        assert "used_pct" in result
        assert 0 <= result["used_pct"] <= 100


# ── Alerts tests ──────────────────────────────────────────────

class TestAlerts:
    def test_severity_classification(self):
        """Severity should be correctly classified."""
        from watchbot.core.alerts import classify_severity
        assert classify_severity(50, 80, 95) == "debug"
        assert classify_severity(70, 80, 95) == "info"
        assert classify_severity(85, 80, 95) == "warning"
        assert classify_severity(96, 80, 95) == "critical"

    def test_template_rendering(self):
        """Alert templates should render with variables."""
        from watchbot.core.alerts import render_alert_template
        msg = render_alert_template("lxc_down",
            vmid=107, name="hermes", severity="critical",
            action="auto-restart", timestamp="12:00 UTC")
        assert "LXC 107" in msg
        assert "hermes" in msg
        assert "DOWN" in msg

    def test_alert_summary(self):
        """Alert summary should return readable text."""
        from watchbot.core.alerts import build_alert_summary
        summary = build_alert_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0


# ── Healthchecks.io monitor tests ──────────────────────────────

class TestHealthchecks:
    def test_parse_status_mapping(self):
        """API status strings must map to health/severity/label."""
        from watchbot.monitors.healthchecks import parse_status
        assert parse_status("up") == ("ok", "info", "up")
        assert parse_status("grace") == ("warning", "warning", "late")
        assert parse_status("down") == ("critical", "critical", "down")
        assert parse_status("new") == ("warning", "warning", "never pinged")
        assert parse_status("paused") == ("paused", "info", "paused")
        assert parse_status("unknown") == ("unknown", "info", "unknown")

    def test_evaluate_check_alert_on_late(self):
        """A grace (late) check must produce a warning alert payload."""
        from watchbot.monitors.healthchecks import evaluate_check
        check = {
            "name": "Backup", "slug": "backup", "status": "grace",
            "last_ping": "2026-08-24T01:00:00+00:00",
            "next_ping": "2026-08-24T02:00:00+00:00",
        }
        alert = evaluate_check(check)
        assert alert is not None
        assert alert["severity"] == "warning"
        assert "Backup" in alert["title"]
        assert "late" in alert["title"]

    def test_evaluate_check_alert_on_down(self):
        """A down check (grace expired = missed deadline) must be critical."""
        from watchbot.monitors.healthchecks import evaluate_check
        check = {
            "name": "Backup", "slug": "backup", "status": "down",
            "last_ping": "2026-08-24T01:00:00+00:00",
            "next_ping": None,
        }
        alert = evaluate_check(check)
        assert alert is not None
        assert alert["severity"] == "critical"
        assert "down" in alert["title"]

    def test_evaluate_check_no_alert_when_healthy(self):
        """up/new/paused checks must not produce an alert."""
        from watchbot.monitors.healthchecks import evaluate_check
        for status in ("up", "new", "paused"):
            check = {"name": f"c-{status}", "status": status}
            assert evaluate_check(check) is None, f"{status} should not alert"
