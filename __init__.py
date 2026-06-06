"""
WatchBot — Hermes Plugin Entry Point

Hermes discovers plugins by scanning ``~/.hermes/plugins/<name>/`` for
``plugin.yaml + __init__.py``. This bridges the ``src/`` layout so the
plugin works as both a drop-in plugin and a pip package.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PLUGIN_DIR / "src"

# Register / register_cli / __version__ are the public API.
# Set defaults in case the bridge fails.
register = None  # type: ignore
register_cli = None  # type: ignore
__version__ = "0.1.0"


def _load_real_package():
    """Import the real watchbot package from src/watchbot/.

    Uses importlib to avoid circular import issues with the shim module.
    """
    import importlib.util

    init_py = _SRC_DIR / "watchbot" / "__init__.py"
    if not init_py.exists():
        raise ImportError(f"Real package not found at {init_py}")

    spec = importlib.util.spec_from_file_location(
        "watchbot_real",
        init_py,
        submodule_search_locations=[str(_SRC_DIR)],
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to create spec for {init_py}")

    mod = importlib.util.module_from_spec(spec)
    # Register in sys.modules so sub-imports (watchbot.core, etc.) resolve
    sys.modules["watchbot_real"] = mod
    sys.modules["watchbot"] = mod  # also register as "watchbot" for internal imports
    spec.loader.exec_module(mod)
    return mod


# Try to load the real package. If it fails (e.g., during test collection
# from src/ directly), the stub values above ensure Hermes doesn't crash.
if _SRC_DIR.joinpath("watchbot", "__init__.py").exists() and not __file__.startswith(str(_SRC_DIR)):
    try:
        _real = _load_real_package()
        register = _real.register
        register_cli = getattr(_real, "register_cli", None)
        __version__ = getattr(_real, "__version__", "0.1.0")
        logger.debug("WatchBot loaded from %s", _SRC_DIR)
    except Exception as e:
        logger.error("WatchBot: failed to load from %s — %s", _SRC_DIR, e)
