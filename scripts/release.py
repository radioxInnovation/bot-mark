#!/usr/bin/env python3
# Default = REAL. Use --test to only log and skip commits/tags/pushes.

import subprocess
import sys
import re
from pathlib import Path

TEST_MODE = "--test" in sys.argv
REAL_MODE = not TEST_MODE

def _run(cmd, check=True, cwd=None):
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd).stdout.strip()

def run_read(cmd, cwd=None):
    if TEST_MODE:
        print(f"[TEST-READ] {' '.join(cmd)}")
    return _run(cmd, cwd=cwd)

def run_do(cmd, cwd=None):
    if TEST_MODE:
        print(f"[TEST] {' '.join(cmd)}")
        return ""
    return _run(cmd, cwd=cwd)

def repo_root() -> Path:
    try:
        root = run_read(["git", "rev-parse", "--show-toplevel"])
        return Path(root)
    except subprocess.CalledProcessError:
        print("❌ Not inside a git repository.")
        sys.exit(1)

def list_changes(root: Path):
    staged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only", "--cached"], cwd=root).splitlines() if p.strip())
    unstaged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only"], cwd=root).splitlines() if p.strip())
    untracked = set(p.replace("\\", "/") for p in run_read(["git", "ls-files", "--others", "--exclude-standard"], cwd=root).splitlines() if p.strip())
    return staged, unstaged, untracked

def _extract_version_from_setup(text: str) -> str | None:
    """
    Extract version only from the setuptools.setup(...) call:
      setup(..., version="1.2.3", ...)
    Ignores any other variables like PAI_VERSION.
    """
    m = re.search(r'setup\s*\([^)]*?\bversion\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None

def ensure_only_setup_py_changed(root: Path):
    """
    Allow only changes in setup.py, and only a single version-line change.
    Verified by parsing `git diff -U0 HEAD -- setup.py`:
      - exactly one '-' line and one '+' line, both matching a version=... assignment
      - nothing else changed.
    """
    staged, unstaged, untracked = list_changes(root)
    changed = staged | unstaged | untracked
    if not changed:
        return  # repo clean

    other = sorted(p for p in changed if p != "setup.py")
    if other:
        print("❌ Repo has changes outside setup.py:\n  " + "\n  ".join(other))
        sys.exit(1)

    if "setup.py" in untracked:
        print("❌ setup.py is untracked; only version changes to a tracked setup.py are allowed.")
        sys.exit(1)

    try:
        diff = run_read(["git", "--no-pager", "diff", "-U0", "HEAD", "--", "setup.py"], cwd=root)
    except subprocess.CalledProcessError:
        diff = ""

    minus_lines, plus_lines = [], []
    for line in diff.splitlines():
        if line.startswith(('--- ', '+++ ', '@@')):
            continue
        if line.startswith('-'):
            minus_lines.append(line[1:])
        elif line.startswith('+'):
            plus_lines.append(line[1:])

    # If there is no actual diff (e.g. staged identical), accept and proceed.
    if not minus_lines and not plus_lines:
        txt = (root / "setup.py").read_text(encoding="utf-8", errors="ignore")
        if not _extract_version_from_setup(txt):
            print("❌ setup.py present but no setup(..., version=...) entry.")
            sys.exit(1)
        print("ℹ️ setup.py shows as changed, but diff to HEAD is empty; proceeding.")
        return

    vpattern = re.compile(r'(?i)^\s*version\s*=\s*[\'"][^\'"]+[\'"]\s*,?\s*$')
    if len(minus_lines) != 1 or len(plus_lines) != 1:
        print("❌ setup.py has multiple changes; only a single version line change is allowed.")
        print("--- diff ---\n" + diff + "\n------------")
        sys.exit(1)
    if not vpattern.match(minus_lines[0]) or not vpattern.match(plus_lines[0]):
        print("❌ setup.py change is not limited to the version=... line.")
        print("--- diff ---\n" + diff + "\n------------")
        sys.exit(1)
    if minus_lines[0] == plus_lines[0]:
        print("❌ version line did not change.")
        sys.exit(1)

    print("✅ Detected only a version-line change in setup.py.")

def ensure_branch_synced(root: Path):
    branch = run_read(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root)
    try:
        run_read(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=root)
    except subprocess.CalledProcessError:
        print(f"❌ Branch {branch} has no upstream. Push first: git push -u origin {branch}")
        sys.exit(1)
    out = run_read(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], cwd=root)
    ahead, behind = out.split()
    if ahead != "0" or behind != "0":
        print(f"❌ Branch and upstream differ ({ahead} ahead / {behind} behind). Sync first.")
        sys.exit(1)

def get_version_from_setup_py(root: Path) -> str:
    text = (root / "setup.py").read_text(encoding="utf-8", errors="ignore")
    version = _extract_version_from_setup(text)
    if not version:
        print("❌ Could not find setup(..., version=...) in setup.py")
        sys.exit(1)
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([abrc][0-9]+)?$", version):
        print(f"❌ Version '{version}' does not match expected pattern (e.g. 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3rc1)")
        sys.exit(1)
    print(f"✅ Version in setup.py: {version}")
    return version

def ensure_tag_not_exists(version: str, root: Path):
    try:
        run_read(["git", "rev-parse", "-q", "--verify", f"refs/tags/{version}"], cwd=root)
        print(f"❌ Tag '{version}' already exists locally.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass
    try:
        run_read(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{version}"], cwd=root)
        print(f"❌ Tag '{version}' already exists on origin.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass

def commit_version_bump_if_needed(root: Path, version: str):
    staged, unstaged, untracked = list_changes(root)
    if "setup.py" not in (staged | unstaged | untracked):
        return  # nothing to commit
    run_do(["git", "add", "setup.py"], cwd=root)
    run_do(["git", "commit", "-m", f"Bump version to {version}"], cwd=root)
    run_do(["git", "push"], cwd=root)
    print("✅ Committed and pushed version bump in setup.py.")

def create_and_push_tag(version: str, root: Path):
    run_do(["git", "tag", "-a", version, "-m", f"Release {version}"], cwd=root)
    run_do(["git", "push", "origin", version], cwd=root)
    print(f"🎉 Tagged and pushed '{version}'. GitHub Actions will now publish to PyPI.")

if __name__ == "__main__":
    print("🚦 Mode:", "TEST (logs only)" if TEST_MODE else "REAL (will commit/tag/push)")
    root = repo_root()
    ensure_only_setup_py_changed(root)
    ensure_branch_synced(root)
    version = get_version_from_setup_py(root)
    commit_version_bump_if_needed(root, version)   # logs in TEST, acts in REAL
    ensure_tag_not_exists(version, root)
    create_and_push_tag(version, root)
