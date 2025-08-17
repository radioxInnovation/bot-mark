# -*- coding: utf-8 -*-
"""
botmark.utils.yaml_parser

This package prefers its vendored PyYAML located in:
    botmark/utils/yaml_parser/_vendor/yaml/

Public API:
- yaml (module): vendored PyYAML
"""
from __future__ import annotations

from botmark.utils.vendor_bootstrap import prefer_vendor
prefer_vendor("botmark.utils.yaml_parser._vendor")

import yaml  # resolves to vendored PyYAML if present

__all__ = ["yaml"]
