#!/usr/bin/env python3
import subprocess
import sys
import re
from pathlib import Path

# Default is TEST; only run real when --real is passed
REAL_MODE = "--real" in sys.argv

def _run(cmd, check=True, cwd=None):
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd).stdout.strip()

def run_read(cmd, cwd=None):
    """Always execute read-only commands."""
    cmd_str = " ".join(cmd)
    if not REAL_MODE:
        print(f"[TEST-READ] {cmd_str}")
    return _run(cmd, cwd=cwd)

def run_do(cmd, cwd=None):
    """Execute mutating commands in REAL mode, log only otherwise."""
    cmd_str = " ".join(cmd)
    if not REAL_MODE:
        print(f"[TEST] {cmd_str}")
        return ""
    return _run(cmd, cwd=cwd)

def repo_root():
    try:
        root = run_read(["git", "rev-parse", "--show-toplevel"])
        return Path(root)
    except subprocess.CalledProcessError:
        print("❌ Not inside a git repository.")
        sys.exit(1)

def ensure_clean_repo(root):
    status = run_read(["git", "status", "--porcelain"], cwd=root)
    if status:
        print("❌ Repo is not clean. Commit/stash/remove all changes (including untracked) first.")
        sys.exit(1)

def ensure_branch_synced(root):
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
    setup_path = root / "setup.py"
    if not setup_path.exists():
        print(f"❌ setup.py not found at {setup_path}")
        sys.exit(1)

    text = setup_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r'version\s*=\s*[\'"]([^\'"]+)[\'"]', text)
    if not m:
        print("❌ Could not find a version=... entry in setup.py")
        sys.exit(1)

    version = m.group(1).strip()
    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([abrc][0-9]+)?$", version):
        print(f"❌ Version '{version}' does not match expected pattern (e.g. 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3rc1)")
        sys.exit(1)

    print(f"✅ Version in setup.py: {version}")
    return version

def ensure_tag_not_exists(version, root):
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

def create_and_push_tag(version, root):
    run_do(["git", "tag", "-a", version, "-m", f"Release {version}"], cwd=root)
    run_do(["git", "push", "origin", version], cwd=root)
    print(f"🎉 Tagged and pushed '{version}'. GitHub Actions will now publish to PyPI.")

if __name__ == "__main__":
    if REAL_MODE:
        print("🚀 REAL MODE — commands will be executed.")
    else:
        print("🔍 TEST MODE (default) — mutating commands are logged only.")

    root = repo_root()
    ensure_clean_repo(root)
    ensure_branch_synced(root)
    version = get_version_from_setup_py(root)
    ensure_tag_not_exists(version, root)
    create_and_push_tag(version, root)
