#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/vendor_pyyaml.py

Vendoring helper for botmark:
- Downloads PyYAML source tarball (pure Python files only)
- Copies into: botmark/utils/yaml_parser/_vendor/yaml/
- Ensures a bootstrap helper (botmark/utils/vendor_bootstrap.py)
- Writes botmark/utils/yaml_parser/__init__.py to prefer the vendored copy

Usage (from repo root):
    python scripts/vendor_pyyaml.py
"""

from __future__ import annotations

import urllib.request
import tarfile
import tempfile
import shutil
from pathlib import Path

# --- Config ---
PYAML_VERSION = "6.0.1"
PYAML_URL = f"https://github.com/yaml/pyyaml/archive/refs/tags/{PYAML_VERSION}.tar.gz"

# --- Project paths ---
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent if SCRIPT_DIR.name in {"scripts", "tools"} else SCRIPT_DIR

UTILS_DIR = PROJECT_ROOT / "botmark" / "utils"
YAML_PARSER_DIR = UTILS_DIR / "yaml_parser"
VENDOR_BASE = YAML_PARSER_DIR / "_vendor"
TARGET_DIR = VENDOR_BASE / "yaml"

VENDOR_BOOTSTRAP = UTILS_DIR / "vendor_bootstrap.py"
YAML_PARSER_INIT = YAML_PARSER_DIR / "__init__.py"
VENDOR_INIT = VENDOR_BASE / "__init__.py"

# --- File contents ---
VENDOR_BOOTSTRAP_CONTENT = '''# -*- coding: utf-8 -*-
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
'''

YAML_PARSER_INIT_CONTENT = '''# -*- coding: utf-8 -*-
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
'''

# --- Helpers ---
def ensure_bootstrap() -> None:
    """Ensure vendor_bootstrap.py exists."""
    UTILS_DIR.mkdir(parents=True, exist_ok=True)
    if not VENDOR_BOOTSTRAP.exists():
        VENDOR_BOOTSTRAP.write_text(VENDOR_BOOTSTRAP_CONTENT, encoding="utf-8")
        print(f"[OK] Wrote: {VENDOR_BOOTSTRAP.relative_to(PROJECT_ROOT)}")
    else:
        print(f"[SKIP] Exists: {VENDOR_BOOTSTRAP.relative_to(PROJECT_ROOT)}")

def ensure_yaml_parser_init() -> None:
    """Ensure yaml_parser/__init__.py exists (overwrites with vendored-first logic)."""
    YAML_PARSER_DIR.mkdir(parents=True, exist_ok=True)
    YAML_PARSER_INIT.write_text(YAML_PARSER_INIT_CONTENT, encoding="utf-8")
    print(f"[OK] Wrote: {YAML_PARSER_INIT.relative_to(PROJECT_ROOT)}")

def ensure_vendor_package() -> None:
    """Ensure _vendor/ exists and is a Python package."""
    VENDOR_BASE.mkdir(parents=True, exist_ok=True)
    if not VENDOR_INIT.exists():
        VENDOR_INIT.write_text("# vendored dependencies live here\n", encoding="utf-8")
        print(f"[OK] Wrote: {VENDOR_INIT.relative_to(PROJECT_ROOT)}")
    else:
        print(f"[SKIP] Exists: {VENDOR_INIT.relative_to(PROJECT_ROOT)}")

def vendor_pyyaml() -> None:
    """Download PyYAML and copy pure-Python sources into _vendor/yaml/."""
    if TARGET_DIR.exists():
        print(f"❌ {TARGET_DIR.relative_to(PROJECT_ROOT)} already exists – delete or move it first.")
        return

    VENDOR_BASE.mkdir(parents=True, exist_ok=True)  # make sure base exists

    print(f"⬇️  Downloading PyYAML {PYAML_VERSION} …")
    with tempfile.TemporaryDirectory() as td:
        tmpdir = Path(td)
        tar_path = tmpdir / "pyyaml.tar.gz"
        urllib.request.urlretrieve(PYAML_URL, tar_path)

        print("📦 Extracting …")
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(tmpdir)

        src_root = tmpdir / f"pyyaml-{PYAML_VERSION}" / "lib" / "yaml"
        if not src_root.exists():
            raise RuntimeError(f"Could not find expected source folder: {src_root}")

        print(f"🧩 Copying pure-Python files into {TARGET_DIR.relative_to(PROJECT_ROOT)} …")
        shutil.copytree(
            src_root,
            TARGET_DIR,
            ignore=shutil.ignore_patterns("*.c", "*.pyx", "*.h", "*.so", "*.pyd", "*.dll", "*.dylib", "__pycache__"),
        )
        print(f"[vendored] yaml -> {TARGET_DIR.relative_to(PROJECT_ROOT)}")

def main() -> None:
    if not (PROJECT_ROOT / "botmark").exists():
        print(f"[WARN] Could not find 'botmark' directory under: {PROJECT_ROOT}")

    ensure_bootstrap()
    ensure_yaml_parser_init()
    ensure_vendor_package()
    vendor_pyyaml()

    print("\n✅ Done.")
    print("Quick test:\n")
    print("  python - <<'PY'\nfrom botmark.utils.yaml_parser import yaml\nprint('yaml version:', getattr(yaml, '__version__', 'unknown'))\nprint('safe_load works:', hasattr(yaml, 'safe_load'))\nPY")

if __name__ == "__main__":
    main()
