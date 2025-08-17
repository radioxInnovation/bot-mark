#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/setup_vendor.py

Vendoring helper for botmark:
- Vendors *pure Python source only* from markdown-it-py (>=3.0.0) and
  mdit-py-plugins (>=0.4.2) into:
      botmark/markdown_parser/renderer/_vendor/
- Writes/overwrites botmark/markdown_parser/renderer/__init__.py to prefer the
  vendored code and re-export the same symbols/behavior you had before:
      md, parse_attributes

USAGE (from repo root):
    python scripts/setup_vendor.py
"""

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

# ── Locate project paths (works whether this file is in repo root or in scripts/ or tools/) ──
SCRIPT_DIR = Path(__file__).resolve().parent
if SCRIPT_DIR.name in {"scripts", "tools"}:
    PROJECT_ROOT = SCRIPT_DIR.parent
else:
    PROJECT_ROOT = SCRIPT_DIR

RENDERER_DIR = PROJECT_ROOT / "botmark" / "markdown_parser" / "renderer"
VENDOR_DIR   = RENDERER_DIR / "_vendor"

# Packages to vendor (you can pin ranges here)
REQS = ["markdown-it-py>=3.0.0", "mdit-py-plugins>=0.4.2"]

# __init__.py content for botmark/markdown_parser/renderer
# - Prefer vendored modules by prepending _vendor path to sys.path
# - Provide the same API you described: md, parse_attributes
RENDERER_INIT = r'''# -*- coding: utf-8 -*-
"""
botmark.markdown_parser.renderer

This module prefers vendored copies of:
- markdown-it-py (>=3.0.0)
- mdit-py-plugins (>=0.4.2)

It exposes:
- md: a configured MarkdownIt instance
- parse_attributes(text): dict of parsed attrs of the first node

Vendored packages live in: botmark/markdown_parser/renderer/_vendor/
"""

from __future__ import annotations

import sys
from types import ModuleType

def _prefer_vendor() -> None:
    """
    Make sure our vendored directory is at the front of sys.path so imports
    resolve to vendored code first.
    """
    vendor_pkg = "botmark.markdown_parser.renderer._vendor"
    if vendor_pkg not in sys.modules:
        try:
            __import__(vendor_pkg)
        except Exception:
            return
    mod: ModuleType | None = sys.modules.get(vendor_pkg)
    if mod and hasattr(mod, "__path__"):
        for p in mod.__path__:
            if p not in sys.path:
                sys.path.insert(0, p)

_prefer_vendor()

# --- Normal imports from markdown-it-py and mdit-py-plugins ---
from markdown_it import MarkdownIt
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.container import container_plugin

# Your original setup (kept as-is, just vendored-first):
md = (
    MarkdownIt("commonmark")
    .use(attrs_plugin)
    .use(container_plugin, "info")
    .enable("fence")
    .enable("table")
)
md.validateLink = lambda url: True  # allow all links

# parse_attributes as you had it:
parse_attributes = (
    lambda x: MarkdownIt("commonmark")
    .use(attrs_plugin)
    .parse(x)[1]
    .children[0]
    .attrs
)

__all__ = ["md", "parse_attributes"]
'''

def ensure_renderer_package() -> None:
    """Create renderer package structure and write __init__.py."""
    RENDERER_DIR.mkdir(parents=True, exist_ok=True)
    (VENDOR_DIR).mkdir(parents=True, exist_ok=True)

    init_file = RENDERER_DIR / "__init__.py"
    init_file.write_text(RENDERER_INIT, encoding="utf-8")

    vendor_init = VENDOR_DIR / "__init__.py"
    if not vendor_init.exists():
        vendor_init.write_text("# vendored dependencies live here\n", encoding="utf-8")

    print(f"[OK] Wrote: {init_file.relative_to(PROJECT_ROOT)}")
    print(f"[OK] Ensured: {vendor_init.relative_to(PROJECT_ROOT)}")

def is_pure_python_pkg(path: Path) -> bool:
    """
    Return True for real Python package directories:
    - contains __init__.py, OR
    - contains at least one .py file (fallback for namespace-like layouts)
    """
    if not path.is_dir():
        return False
    if (path / "__init__.py").exists():
        return True
    return any(p.is_file() and p.suffix == ".py" for p in path.iterdir())

def copytree_clean(src: Path, dst: Path) -> None:
    """
    Copy only pure Python sources; ignore dist-info, caches, tests, docs, examples, binaries.
    """
    if dst.exists():
        shutil.rmtree(dst)

    def _ignore(_dir, names):
        skip_names = {
            "__pycache__", ".pytest_cache", ".mypy_cache",
            "tests", "test", "testing",
            "docs", "doc", "examples", "example",
        }
        ignored = set()
        for n in names:
            # Always ignore metadata/build artifacts
            if n.endswith((".dist-info", ".data", ".egg-info")):
                ignored.add(n); continue
            if n.endswith((".so", ".pyd", ".dll", ".dylib", ".pyc")):
                ignored.add(n); continue
            if n in skip_names or any(n.lower().startswith(s + "-") for s in skip_names):
                ignored.add(n); continue
        return list(ignored)

    shutil.copytree(src, dst, ignore=_ignore)

def vendor_dependencies() -> None:
    """Install dependencies into a temp dir and selectively copy package folders into _vendor/."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        print(f"[*] Installing dependencies into temporary target: {tmp}")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--no-compile", "--target", str(tmp)]
            + REQS
        )

        count = 0
        for entry in sorted(tmp.iterdir()):
            if entry.is_dir() and is_pure_python_pkg(entry):
                dst = VENDOR_DIR / entry.name
                copytree_clean(entry, dst)
                print(f"[vendored] {entry.name}")
                count += 1
        print(f"[OK] Vendored {count} package folder(s) into {VENDOR_DIR.relative_to(PROJECT_ROOT)}")

def main() -> None:
    if not (PROJECT_ROOT / "botmark").exists():
        print(f"[WARN] Could not find 'botmark' directory under: {PROJECT_ROOT}")
    ensure_renderer_package()
    vendor_dependencies()
    print("\n✅ Done.")
    print("Next steps:")
    print("  - Optional install in editable mode:  python -m pip install -e .")
    print("  - Quick import test:")
    print("      python - <<'PY'\nfrom botmark.markdown_parser.renderer import md, parse_attributes\nprint('md OK:', hasattr(md, 'render'))\nprint('attrs OK:', callable(parse_attributes))\nPY")

if __name__ == "__main__":
    main()
