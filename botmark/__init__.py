# Auto-install vendored libraries so normal imports work.
try:
    from ._vendor import install as _install_vendor
    _install_vendor(prefer_vendor=True)  # force vendored copies for consistent wheels
except Exception:
    # Fail quietly if vendor bootstrap is unavailable (e.g., in dev before vendoring)
    pass

import importlib.metadata

__version__ = importlib.metadata.version("botmark")

from .core import BotManager, BotMarkAgent, FileSystemSource, BotmarkSource

__all__ = ["BotManager", "BotMarkAgent", "FileSystemSource", "BotmarkSource"]
