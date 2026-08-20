# Contributing to WatchBot

Thanks for wanting to contribute! 👋 WatchBot is a community project now — all
kinds of contributions are welcome: bug reports, feature ideas, docs, tests, and
code. No contribution is too small.

## Code of Conduct

Be excellent to each other. 🤝

Be kind, patient, and constructive. Assume good intent, give and receive
feedback graciously, and keep the project a welcoming place for everyone —
whether this is your first open-source PR or your hundredth.

## What We're Looking For

- **Bug reports & feature ideas** — open an [issue](https://github.com/piyush97/watchbot/issues/new) with a clear description and, for bugs, steps to reproduce.
- **Documentation** — README, docs/, SKILL.md, and this file. Docs-only changes are very welcome and a great first contribution.
- **Tests** — WatchBot uses pytest. Adding coverage is always appreciated.
- **Code** — monitor integrations, CLI commands, tools, hooks, and the dashboard.
- **Reviews** — commenting on open PRs to help maintainers and other contributors.

## Setting Up Locally

### Prerequisites

- Python **3.11+** (WatchBot targets `>=3.11`)
- [Hermes Agent](https://hermes-agent.nousresearch.com) v0.15+ (the plugin runtime — needed to run the plugin end-to-end)
- `git`

### Clone and install

```bash
# 1. Clone the repo
git clone https://github.com/piyush97/watchbot.git
cd watchbot

# 2. Create a virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install the package in editable mode with dev dependencies
pip install -e '.[dev]'
```

> **Note on Hermes Agent:** the plugin expects Hermes to be installed when run
> inside a session (see `setup.py` — `hermes-agent>=0.15.0`). The test suite
> and core monitors don't require it, so you can develop and run tests without
> a full Hermes install.

### Running the plugin

The repo uses a `src/` layout with a root `__init__.py` bridge so it works both
as a Hermes plugin (dropped into `~/.hermes/plugins/watchbot/`) and as a pip
package. To use it inside Hermes:

```bash
npx skills add piyush97/watchbot     # or: git clone into ~/.hermes/plugins/watchbot
hermes plugins enable watchbot
hermes watchbot setup
hermes watchbot status
```

## Running Tests

The test suite uses **pytest**. From the repo root:

```bash
pip install -e '.[dev]'   # once, to install dev dependencies
pytest -v
```

The suite lives in `tests/` and covers config loading, state/alerts, and the
system monitor. `pytest` is pre-configured in `pyproject.toml` (`testpaths`,
`pythonpath = ["src"]`, `--import-mode=importlib`), so a plain `pytest` should
just work.

## Linting

WatchBot uses **ruff** (configured in `pyproject.toml`, `line-length = 100`,
`target-version = "py311"`):

```bash
pip install -e '.[dev]'   # once, to install ruff
ruff check src tests
```

Please make sure `ruff check src tests` is clean before opening a PR. If you
introduce new code, keep it consistent with the surrounding style.

> CI runs the same commands (`pytest -v` and `ruff check src tests`) on Python
> 3.11 and 3.12 — see `.github/workflows/ci.yml`.

## Opening a Good PR

1. **Branch from `main`** — create a descriptive branch:
   ```bash
   git checkout main
   git pull
   git checkout -b fix/system-monitor-disk-check   # or feat/add-monitor, docs/..., etc.
   ```
2. **Make small, focused changes** — one logical change per PR. This makes
   review faster and easier to revert if needed.
3. **Write descriptive commit messages** — a short summary line plus context
   when useful:
   ```
   Fix disk threshold comparison in system monitor

   The threshold was being compared to the free-space percentage instead of
   the used-space percentage, causing spurious alerts.
   ```
4. **Add or update tests** for your change, and make sure the full suite passes
   locally: `pytest -v`.
5. **Run the linter**: `ruff check src tests`.
6. **Push and open the PR** against `main`:
   ```bash
   git push origin your-branch
   # then open a PR via https://github.com/piyush97/watchbot/compare
   ```
7. **Link issues** you're addressing (e.g. "Fixes #12") so they auto-close on merge.

### PR checklist

- [ ] Branch created from `main`
- [ ] Focused on one logical change
- [ ] `pytest -v` passes
- [ ] `ruff check src tests` is clean
- [ ] Tests added/updated for the change (where applicable)
- [ ] Docs updated if behavior changed (README, SKILL.md, docs/)

### Docs-only changes?

Great — those are explicitly welcome! Fixing a typo, clarifying a section, or
adding examples is a fantastic first contribution. Just open a PR like any
other; no code required.

## Reporting Issues

- Use the [issue templates](https://github.com/piyush97/watchbot/issues/new/choose) when available.
- Include: what you expected, what happened, steps to reproduce, and your environment (OS, Python version, Hermes version if relevant).
- Paste logs or error output; redact any secrets or tokens.

## Need help?

Open a discussion or ask in the issue — maintainers and contributors are happy
to point you in the right direction.

Thank you for contributing to WatchBot! 🚀
