"""
Vendor bootstrap for third-party libraries.

This allows the rest of the code to keep doing regular imports:
    import markdown_it
    import mdit_py_plugins
    import frontmatter
    import yaml

The vendored copies live under botmark._vendor.* and are bound into sys.modules.
"""

from __future__ import annotations
import importlib
import sys
from types import ModuleType
from typing import Dict

_VENDOR_MAP: Dict[str, str] = {
    "markdown_it": "botmark._vendor.markdown_it",
    "mdit_py_plugins": "botmark._vendor.mdit_py_plugins",
    "frontmatter": "botmark._vendor.frontmatter",
    "yaml": "botmark._vendor.yaml",
}

def _load(dotted: str) -> ModuleType:
    return importlib.import_module(dotted)

def _install(public_name: str, vendored_name: str, prefer_vendor: bool):
    if prefer_vendor:
        mod = _load(vendored_name)
        sys.modules[public_name] = mod
        return
    try:
        _load(public_name)
        return
    except Exception:
        mod = _load(vendored_name)
        sys.modules[public_name] = mod

def install(prefer_vendor: bool = True) -> None:
    for public, vendored in _VENDOR_MAP.items():
        _install(public, vendored, prefer_vendor)
