import importlib.metadata
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("botmark")
except:
    __version__ = "0.0.0+local"

from .core import BotManager, BotMarkAgent, FileSystemSource, BotmarkSource, StringSource

__all__ = ["BotManager", "BotMarkAgent", "FileSystemSource", "BotmarkSource", "StringSource"]
