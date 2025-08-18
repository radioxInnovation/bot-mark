# -*- coding: utf-8 -*-
"""
Utility to prefer vendored packages by prepending their path to sys.path.
Example:
    from botmark.utils.vendor_bootstrap import prefer_vendor
    prefer_vendor("botmark.utils.yaml_parser._vendor")
"""
from __future__ import annotations
import sys, importlib, types

def prefer_vendor(vendor_pkg: str) -> None:
    try:
        importlib.import_module(vendor_pkg)
    except Exception:
        return
    mod: types.ModuleType | None = sys.modules.get(vendor_pkg)
    if mod and hasattr(mod, "__path__"):
        for p in mod.__path__:
            if p not in sys.path:
                sys.path.insert(0, p)
