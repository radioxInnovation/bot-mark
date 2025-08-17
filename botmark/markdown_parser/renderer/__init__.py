# -*- coding: utf-8 -*-
"""
Vendor-first MarkdownIt-Setup für botmark.markdown_parser.renderer

Dieses Modul bevorzugt die lokal vendorten Versionen von:
- markdown-it-py (>=3.0.0)
- mdit-py-plugins (>=0.4.2)

und bietet die bisherigen Symbole/Verhalten:
- md: konfiguriertes MarkdownIt-Objekt
- parse_attributes(text): dict der geparsten Attribute der ersten Node
"""

from __future__ import annotations
import sys
from types import ModuleType

def _prefer_vendor() -> None:
    """Stellt sicher, dass botmark.markdown_parser.renderer._vendor im Importpfad vorn liegt."""
    vendor_pkg = __name__ + "._vendor"  # botmark.markdown_parser.renderer._vendor
    if vendor_pkg not in sys.modules:
        try:
            __import__(vendor_pkg)
        except Exception:
            return
    vm: ModuleType | None = sys.modules.get(vendor_pkg)
    if vm and hasattr(vm, "__path__"):
        for p in vm.__path__:
            if p not in sys.path:
                sys.path.insert(0, p)

_prefer_vendor()

# ── Ab hier ganz normale Imports aus markdown-it-py & mdit_py_plugins ────────
from markdown_it import MarkdownIt
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.container import container_plugin

# Dein bisheriges Setup (beibehalten, nur vendored-first):
md = MarkdownIt("commonmark").use(attrs_plugin).use(container_plugin, "info").enable("fence").enable("table")
md.validateLink = lambda url: True  # Links nicht validieren

# parse_attributes wie gehabt:
parse_attributes = lambda x: MarkdownIt("commonmark").use(attrs_plugin).parse(x)[1].children[0].attrs

__all__ = ["md", "parse_attributes"]
