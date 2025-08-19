#!/usr/bin/env python3
import subprocess
import sys
import re

TEST_MODE = True#"--test" in sys.argv

def _run(cmd, check=True):
    """Execute a command and return stdout (stripped)."""
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout.strip()

def run_read(cmd):
    """
    Always EXECUTE read-only commands, even in test mode.
    Used for: git status, rev-parse, rev-list, ls-remote, and `python setup.py --version`.
    """
    cmd_str = " ".join(cmd)
    if TEST_MODE:
        print(f"[TEST-READ] {cmd_str}")
    return _run(cmd)

def run_do(cmd):
    """
    Execute mutating commands normally; in test mode, LOG ONLY (no execution).
    Used for: git tag -a, git push.
    """
    cmd_str = " ".join(cmd)
    if TEST_MODE:
        print(f"[TEST] {cmd_str}")
        return ""
    return _run(cmd)

def ensure_clean_repo():
    status = run_read(["git", "status", "--porcelain"])
    if status:
        print("❌ Repo is not clean. Commit/stash/remove all changes (including untracked) first.")
        sys.exit(1)

def ensure_branch_synced():
    branch = run_read(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    try:
        run_read(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    except subprocess.CalledProcessError:
        print(f"❌ Branch {branch} has no upstream. Push first: git push -u origin {branch}")
        sys.exit(1)

    out = run_read(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"])
    ahead, behind = out.split()
    if ahead != "0" or behind != "0":
        print(f"❌ Branch and upstream differ ({ahead} ahead / {behind} behind). Sync first.")
        sys.exit(1)

def get_version():
    # Use the current interpreter for reliability on Windows
    version = run_read([sys.executable, "setup.py", "--version"])
    if not version:
        print("❌ Could not extract version from setup.py")
        sys.exit(1)

    if not re.match(r"^[0-9]+\.[0-9]+\.[0-9]+([abrc][0-9]+)?$", version):
        print(f"❌ Version '{version}' does not match expected pattern (e.g. 1.2.3, 1.2.3a1, 1.2.3b2, 1.2.3rc1)")
        sys.exit(1)

    print(f"✅ Version in setup.py: {version}")
    return version

def ensure_tag_not_exists(version):
    try:
        run_read(["git", "rev-parse", "-q", "--verify", f"refs/tags/{version}"])
        print(f"❌ Tag '{version}' already exists locally.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass

    try:
        run_read(["git", "ls-remote", "--exit-code", "--tags", "origin", f"refs/tags/{version}"])
        print(f"❌ Tag '{version}' already exists on origin.")
        sys.exit(1)
    except subprocess.CalledProcessError:
        pass

def create_and_push_tag(version):
    run_do(["git", "tag", "-a", version, "-m", f"Release {version}"])
    run_do(["git", "push", "origin", version])
    print(f"🎉 Tagged and pushed '{version}'. GitHub Actions will now publish to PyPI.")

if __name__ == "__main__":
    if TEST_MODE:
        print("🔍 Running in TEST MODE — mutating commands are logged only; read-only checks execute.")

    # Basic sanity: ensure we’re in a repo
    try:
        _ = run_read(["git", "rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError:
        print("❌ Not inside a git repository.")
        sys.exit(1)

    ensure_clean_repo()
    ensure_branch_synced()
    version = get_version()
    ensure_tag_not_exists(version)
    create_and_push_tag(version)
