#!/usr/bin/env python3
"""
Collect Python source files recursively, annotate each with its file path,
assemble a single prompt-friendly text, and copy it to the clipboard.
Optionally write to an output file.

Usage:
  python collect_py_for_chatgpt.py /path/to/project [--out prompt.txt] [--absolute] [--include-hidden]
  python collect_py_for_chatgpt.py . --out prompt.txt
"""

from __future__ import annotations
import argparse
import os
import sys
import subprocess
from pathlib import Path
from typing import Iterable, List

# Default directories to exclude (common virtualenvs, caches, IDE configs, etc.)
DEFAULT_EXCLUDES = {
    ".git", ".hg", ".svn",
    "__pycache__", ".mypy_cache", ".pytest_cache",
    ".venv", "venv", "env", ".tox",
    "node_modules", "dist", "build", ".idea", ".vscode",
}

def read_text_safely(path: Path) -> str:
    """Try reading a file with multiple encodings; replace errors if needed."""
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=enc, errors="replace")
        except Exception:
            continue
    # Last resort: read bytes and decode with replacement
    try:
        return path.read_bytes().decode("utf-8", errors="replace")
    except Exception:
        return f"<<Error reading {path}>>"

def is_hidden(path: Path) -> bool:
    """Check if path contains hidden elements (Unix-style: starts with '.')"""
    return any(part.startswith(".") for part in path.parts if part)

def iter_python_files(root: Path,
                      exclude_dirs: set[str],
                      include_hidden: bool) -> Iterable[Path]:
    """Walk the directory tree and yield Python files, respecting exclusions."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter directories in-place so os.walk does not descend into them
        dirnames[:] = [
            d for d in dirnames
            if d not in exclude_dirs and (include_hidden or not d.startswith("."))
        ]
        # Yield .py files
        for name in filenames:
            if not name.endswith(".py"):
                continue
            if not include_hidden and name.startswith("."):
                continue
            yield Path(dirpath) / name

def assemble_prompt(files: List[Path],
                    root: Path,
                    use_absolute: bool) -> str:
    """Combine all file contents into a ChatGPT-friendly prompt."""
    lines = []
    lines.append("# Project Snapshot (Python files)\n")
    lines.append(f"Root: {str(root.resolve())}\n")
    lines.append("Note: Each file is annotated with its path. Code is inside fenced blocks.\n")
    for fp in sorted(files, key=lambda p: str(p).lower()):
        rel = str(fp if use_absolute else fp.relative_to(root))
        lines.append("\n" + "=" * 80)
        lines.append(f"FILE: {rel}")
        lines.append("=" * 80 + "\n")
        lines.append("```python")
        lines.append(read_text_safely(fp))
        lines.append("```")
    lines.append("")  # final newline
    return "\n".join(lines)

def copy_to_clipboard(text: str) -> bool:
    """
    Try to copy 'text' to the system clipboard.
    Strategies:
      - pyperclip (if installed)
      - macOS: pbcopy
      - Linux: wl-copy / xclip / xsel
      - Windows: clip
    Returns True if successful.
    """
    # 1) Try pyperclip if available
    try:
        import pyperclip  # type: ignore
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    # 2) Fallbacks per platform
    try:
        if sys.platform == "darwin":
            p = subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
            return p.returncode == 0
        elif sys.platform.startswith("linux"):
            for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]):
                try:
                    p = subprocess.run(cmd, input=text.encode("utf-8"), check=True)
                    return p.returncode == 0
                except Exception:
                    continue
        elif sys.platform.startswith("win"):
            p = subprocess.run(["clip"], input=text.encode("utf-16-le"), check=True)
            return p.returncode == 0
    except Exception:
        pass
    return False

def main():
    ap = argparse.ArgumentParser(description="Recursively collect Python files as a ChatGPT prompt.")
    ap.add_argument("root", type=str, help="Project root folder")
    ap.add_argument("--out", type=str, default=None, help="Optional output file path")
    ap.add_argument("--absolute", action="store_true", help="Use absolute paths instead of relative")
    ap.add_argument("--include-hidden", action="store_true", help="Include hidden files/folders")
    ap.add_argument("--no-default-excludes", action="store_true", help="Do not use the built-in exclude list")
    ap.add_argument("--exclude", action="append", default=[], help="Additional directories to exclude (can be repeated)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: '{root}' is not a valid folder.", file=sys.stderr)
        sys.exit(1)

    exclude_dirs = set(args.exclude)
    if not args.no_default_excludes:
        exclude_dirs |= DEFAULT_EXCLUDES

    files = list(iter_python_files(root, exclude_dirs=exclude_dirs, include_hidden=args.include_hidden))
    if not files:
        print("No Python files found.")
        sys.exit(0)

    prompt_text = assemble_prompt(files, root=root, use_absolute=args.absolute)

    wrote_file = False
    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(prompt_text, encoding="utf-8")
        wrote_file = True

    copied = copy_to_clipboard(prompt_text)

    # Summary message
    msg = []
    msg.append(f"Found .py files: {len(files)}")
    msg.append(f"Clipboard: {'OK' if copied else 'FAILED'}")
    if wrote_file:
        msg.append(f"Output file: {out_path}")
    if not copied:
        msg.append("Tip: Install 'pyperclip' or ensure pbcopy/clip/wl-copy/xclip is available.")
    print(" | ".join(msg))

if __name__ == "__main__":
    main()
