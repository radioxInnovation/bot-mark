# -*- coding: utf-8 -*-

from __future__ import annotations
import sys
from types import ModuleType

def _prefer_vendor() -> None:
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

from markdown_it import MarkdownIt
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.container import container_plugin

md = MarkdownIt("commonmark").use(attrs_plugin).use(container_plugin, "info").enable("fence").enable("table")
md.validateLink = lambda url: True

parse_attributes = lambda x: MarkdownIt("commonmark").use(attrs_plugin).parse(x)[1].children[0].attrs

__all__ = ["md", "parse_attributes"]
