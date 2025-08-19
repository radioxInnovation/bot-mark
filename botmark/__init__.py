import importlib.metadata

__version__ = importlib.metadata.version("botmark")

from .core import BotManager, BotMarkAgent, FileSystemSource, BotmarkSource, StringSource

__all__ = ["BotManager", "BotMarkAgent", "FileSystemSource", "BotmarkSource", "StringSource"]
