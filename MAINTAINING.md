# Maintaining WatchBot

Runbook for contributors and maintainers of
[`piyush97/watchbot`](https://github.com/piyush97/watchbot) — the Hermes Agent
plugin for unified homelab + social media monitoring.

## CI

CI runs on every push to `main` and on every pull request via
`.github/workflows/ci.yml`:

- **Lint (ruff)** — `ruff check .` on Python 3.12.
  - The project pins `select = ["E4", "E7", "E9", "F"]` in `pyproject.toml`
    (safety-critical rules only). This keeps `ruff check` green across ruff
    versions; do not broaden the rule set without a deliberate decision.
- **Test (Python 3.11 / 3.12)** — `pytest -v`.

Local equivalents (Python ≥ 3.11):

```bash
pip install -e '.[dev]'
ruff check .
pytest -v
```

Test configuration notes (see `[tool.pytest.ini_options]` in `pyproject.toml`):

- `pythonpath = ["src"]` puts `src/` on `sys.path` so `watchbot.*` imports
  resolve under the `src/` layout.
- `--import-mode=importlib` (via `addopts`) prevents pytest from re-deriving
  the tests as `watchbot.tests`, which collides with the root plugin bridge
  and previously broke collection with `No module named 'watchbot.tests'`.

## Local development

```bash
# Editable install with dev extras (pytest, pytest-asyncio, ruff)
pip install -e '.[dev]'

# Optional extras (not required for tests)
pip install -e '.[dashboard]'   # Flask web dashboard
pip install -e '.[twitter]'     # X/Twitter companion tooling
pip install -e '.[all]'         # everything
```

## Hermes plugin notes

WatchBot is a Hermes Agent plugin. Hermes discovers plugins by scanning
`~/.hermes/plugins/<name>/` for `plugin.yaml` + `__init__.py`, so the repo
doubles as a drop-in plugin:

```bash
# Drop-in plugin install (clone into the Hermes plugins dir)
cd ~/.hermes/plugins
git clone https://github.com/piyush97/watchbot.git
hermes plugins enable watchbot

# Or install via skills.sh
npx skills add piyush97/watchbot
```

After installing, the Hermes CLI exposes the plugin commands:

```bash
hermes watchbot setup      # Configuration wizard (writes ~/.hermes/watchbot.yaml)
hermes watchbot status     # Full status (also: --json)
hermes watchbot health     # Disk/CPU/memory snapshot
hermes watchbot lxc        # Proxmox LXC containers
hermes watchbot ha         # Home Assistant sensors
hermes watchbot twitter    # X/Twitter timeline
hermes watchbot blogs      # RSS feed latest
hermes watchbot docker     # Docker container status
hermes watchbot alerts     # Active alerts
hermes watchbot dashboard  # Web UI at :9099
```

### The `src/` bridge

The root `__init__.py` is a **bridge** that loads the real package from
`src/watchbot/` via `importlib` with `submodule_search_locations` pointed at
the package directory. This makes the repo work both as a drop-in plugin
(`~/.hermes/plugins/watchbot`) and as a pip package. Keep this contract in
mind when restructuring:

- If the package moves, update the bridge in root `__init__.py` (the search
  location must point at the package directory, not `src/`).
- When adding modules, put them under `src/watchbot/` so the bridge and the
  `pythonpath = ["src"]` pytest config both resolve them.

## Dependency updates (Dependabot)

`.github/dependabot.yml` configures Dependabot for this repo:

- **pip** — weekly (Monday 06:00 UTC), `open-pull-requests-limit: 5`, labelled
  `dependencies`, with `pip-minor-patch` grouping (minor + patch bumps land in
  one PR; major bumps stay separate).
- **github-actions** — weekly, labelled `dependencies`.

Notes:

- There is **no lockfile** — dependencies are declared as ranges in
  `pyproject.toml` (and mirrored in `setup.py`). Dependabot therefore proposes
  version-range bumps for direct dependencies; it does not pin transitive
  deps. If reproducible installs become important, add a lockfile (e.g.
  `uv lock`) as a deliberate decision.
- The stale workflow exempts PRs labelled `dependencies` so Dependabot PRs are
  never nagged as stale.
- When a Dependabot PR bumps `ruff`, the pinned `select` rule set is
  version-tolerant by design, but still run `ruff check .` locally before
  merging.

## Stale policy

`.github/workflows/stale.yml` (actions/stale@v11) runs weekly:

- Issues: labelled `stale` after 60 days of inactivity, **never auto-closed**
  (`days-before-issue-close: -1`).
- PRs: labelled `stale` after 30 days of inactivity, **never auto-closed**.
- Dependabot PRs (`dependencies` label) are exempt.

Stale-labelled items stay open and are simply flagged for triage — nothing is
deleted or auto-closed.

## Release

WatchBot is at `0.1.0` (see `CHANGELOG.md`). Version is declared in three
places — keep them in sync:

1. `pyproject.toml` — `[project] version`
2. `setup.py` — `version=`
3. Root `__init__.py` — `__version__` (and `plugin.yaml` `version:`)

Suggested flow:

1. Update `CHANGELOG.md` (Keep a Changelog style).
2. Bump the version in all four places above.
3. Run the full gate: `ruff check . && pytest -v`.
4. Merge to `main` — CI (Lint + Test on 3.11/3.12) must be green.
5. Tag the release commit (e.g. `git tag v0.2.0 && git push --tags`).
