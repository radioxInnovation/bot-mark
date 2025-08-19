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

def run_read(cmd, cwd=None, test=False):
    if test or TEST_MODE:
        print(f"[TEST-READ] {' '.join(cmd)}")
    return _run(cmd, cwd=cwd)

def run_do(cmd, cwd=None, test=False):
    if test or TEST_MODE:
        print(f"[TEST] {' '.join(cmd)}")
        return ""
    return _run(cmd, cwd=cwd)

def repo_root(test=False) -> Path:
    try:
        root = run_read(["git", "rev-parse", "--show-toplevel"], test=test)
        return Path(root)
    except subprocess.CalledProcessError:
        print("❌ Not inside a git repository.")
        sys.exit(1)

def list_changes(root: Path, test=False):
    staged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only", "--cached"], cwd=root, test=test).splitlines() if p.strip())
    unstaged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only"], cwd=root, test=test).splitlines() if p.strip())
    untracked = set(p.replace("\\", "/") for p in run_read(["git", "ls-files", "--others", "--exclude-standard"], cwd=root, test=test).splitlines() if p.strip())
    return staged, unstaged, untracked

def _extract_version_from_setup(text: str) -> str | None:
    m = re.search(r'setup\s*\([^)]*?\bversion\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None

def ensure_only_setup_py_changed(root: Path, test=False):
    staged, unstaged, untracked = list_changes(root, test=test)
    changed = staged | unstaged | untracked
    if not changed:
        return

    other = sorted(p for p in changed if p != "setup.py")
    if other:
        print("❌ Repo has changes outside setup.py:\n  " + "\n  ".join(other))
        sys.exit(1)

    if "setup.py" in untracked:
        print("❌ setup.py is untracked; only version changes to a tracked setup.py are allowed.")
        sys.exit(1)

    diff = run_read(["git", "--no-pager", "diff", "-U0", "HEAD", "--", "setup.py"], cwd=root, test=test)

    minus_lines, plus_lines = [], []
    for line in diff.splitlines():
        if line.startswith(('--- ', '+++ ', '@@')):
            continue
        if line.startswith('-'):
            minus_lines.append(line[1:])
        elif line.startswith('+'):
            plus_lines.append(line[1:])

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

def ensure_branch_synced(root: Path, test=False):
    branch = run_read(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=root, test=test)
    try:
        run_read(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], cwd=root, test=test)
    except subprocess.CalledProcessError:
        print(f"❌ Branch {branch} has no upstream. Push first: git push -u origin {branch}")
        sys.exit(1)
    out = run_read(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], cwd=root, test=test)
    ahead, behind = out.split()
    if ahead != "0" or behind != "0":
        print(f"❌ Branch and upstream differ ({ahead} ahead / {behind} behind). Sync first.")
        sys.exit(1)

def get_version_from_setup_py(root: Path, test=False) -> str:
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

def ensure_tag_not_exists(version: str, root: Path, test=False):
    try:
        run_read(["git", "rev-parse", "-q", "--verify", f"refs/tags/{version}"], cwd=root, test=test)
        print(f"❌ Tag '{version}' already exists locally.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass
    try:
        run_read(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{version}"], cwd=root, test=test)
        print(f"❌ Tag '{version}' already exists on origin.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass

def commit_version_bump_if_needed(root: Path, version: str):
    staged, unstaged, untracked = list_changes(root)
    if "setup.py" not in (staged | unstaged | untracked):
        return
    run_do(["git", "add", "setup.py"], cwd=root)
    run_do(["git", "commit", "-m", f"Bump version to {version}"], cwd=root)
    run_do(["git", "push"], cwd=root)
    print("✅ Committed and pushed version bump in setup.py.")

def create_and_push_tag(version: str, root: Path):
    run_do(["git", "tag", "-a", version, "-m", f"Release {version}"], cwd=root)
    run_do(["git", "push", "origin", version], cwd=root)
    print(f"🎉 Tagged and pushed '{version}'. GitHub Actions will now publish to PyPI.")

if __name__ == "__main__":
    # Step 1: Always run a dry run first
    print("🚦 Pre-check: TEST RUN (always performed first)")
    root = repo_root(test=True)
    ensure_only_setup_py_changed(root, test=True)
    ensure_branch_synced(root, test=True)
    version = get_version_from_setup_py(root, test=True)
    ensure_tag_not_exists(version, root, test=True)
    print("✅ Dry run checks passed.\n")

    if TEST_MODE:
        print("🚦 Mode: TEST — stopping after dry run.")
        sys.exit(0)

    # Step 2: Do real actions
    print("🚦 Mode: REAL (will commit/tag/push)")
    root = repo_root()
    ensure_only_setup_py_changed(root)
    ensure_branch_synced(root)
    version = get_version_from_setup_py(root)
    commit_version_bump_if_needed(root, version)
    ensure_tag_not_exists(version, root)
    create_and_push_tag(version, root)
