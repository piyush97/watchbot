"""
WatchBot — Hermes Plugin Entry Point

Hermes discovers plugins by scanning ``~/.hermes/plugins/<name>/`` for
``plugin.yaml + __init__.py``. This bridges the ``src/`` layout so the
plugin works as both a drop-in plugin and a pip package.

How it works:
  1. Adds ``src/`` to ``sys.path`` so ``import watchbot`` resolves to the
     real package at ``src/watchbot/__init__.py``.
  2. Removes *this* module from ``sys.modules`` to prevent the circular
     ``import watchbot → this module → import watchbot`` deadlock.
  3. Re-imports the real package and rebinds ``register`` / ``register_cli``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PLUGIN_DIR / "src"

# 1. Ensure src/ is on the Python path so ``import watchbot`` finds the
#    real package at src/watchbot/__init__.py, not this shim.
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# 2. Remove *this* module from sys.modules so the real import doesn't
#    resolve back to this file (circular import guard).
_THIS_KEY = "watchbot"
if _THIS_KEY in sys.modules:
    del sys.modules[_THIS_KEY]

# 3. Import the real package. All internal imports (``from watchbot.core
#    import ...``) now resolve to src/watchbot/ seamlessly.
try:
    import watchbot as _real  # type: ignore[import-unidentified]

    register = _real.register
    register_cli = getattr(_real, "register_cli", None)
    __version__ = getattr(_real, "__version__", "0.1.0")

    # Restore the shim as the public face so Hermes' module reference
    # (``from watchbot import register``) keeps working.  Python's import
    # system guarantees this runs before the import statement returns.
    sys.modules[_THIS_KEY] = sys.modules.get(_THIS_KEY, _real)

    logger.debug("WatchBot loaded from %s", _SRC_DIR)

except ImportError as e:
    logger.error("WatchBot: failed to import from %s — %s", _SRC_DIR, e)

    def register(ctx):  # type: ignore[misc]
        logger.error(
            "WatchBot not loaded. Install: cd %s && pip install -e .",
            _PLUGIN_DIR,
        )

    register_cli = None  # type: ignore[assignment]
    __version__ = "0.1.0"
