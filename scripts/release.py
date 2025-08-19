#!/usr/bin/env python3
import subprocess
import sys
import re
from pathlib import Path

# Default = TEST (safe). Use --real to actually commit/tag/push.
REAL_MODE = "--real" in sys.argv

def _run(cmd, check=True, cwd=None):
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd).stdout.strip()

def run_read(cmd, cwd=None):
    """Execute read-only commands; log them in test mode."""
    if not REAL_MODE:
        print(f"[TEST-READ] {' '.join(cmd)}")
    return _run(cmd, cwd=cwd)

def run_do(cmd, cwd=None):
    """Execute mutating commands; log only in test mode."""
    if not REAL_MODE:
        print(f"[TEST] {' '.join(cmd)}")
        return ""
    return _run(cmd, cwd=cwd)

def repo_root():
    try:
        root = run_read(["git", "rev-parse", "--show-toplevel"])
        return Path(root)
    except subprocess.CalledProcessError:
        print("❌ Not inside a git repository.")
        sys.exit(1)

def git_status_porcelain(root: Path) -> list[str]:
    out = run_read(["git", "status", "--porcelain"], cwd=root)
    return [line.strip() for line in out.splitlines() if line.strip()]

def ensure_only_setup_py_changed(root: Path):
    """
    Enforce: no changes except setup.py (tracked or untracked).
    Allow setup.py modified, but ONLY the version=... field may differ vs HEAD.
    """
    status = git_status_porcelain(root)

    # Quick allow-list: changes in setup.py only
    others = []
    setup_changed = False
    for line in status:
        # Possible prefixes: ' M', 'M ', 'A ', '??', etc.
        path = line[3:] if len(line) > 3 else ""
        if path.replace("\\", "/") == "setup.py":
            setup_changed = True
            continue
        others.append(line)

    if others:
        print("❌ Repo has changes outside setup.py:\n  " + "\n  ".join(others))
        sys.exit(1)

    if not setup_changed:
        # No local change in setup.py — fine, we still validate version and proceed.
        return

    # Validate the ONLY change in setup.py is the version field
    setup_path = root / "setup.py"
    if not setup_path.exists():
        print("❌ setup.py not found.")
        sys.exit(1)

    current_text = setup_path.read_text(encoding="utf-8", errors="ignore")

    # Get the version at HEAD for comparison; if file doesn't exist in HEAD (rare), skip strict check
    try:
        head_text = run_read(["git", "show", "HEAD:setup.py"], cwd=root)
    except subprocess.CalledProcessError:
        # Probably first commit / file new – we accept as long as version is present
        head_text = ""

    def extract_version(txt: str) -> str | None:
        m = re.search(r'version\s*=\s*[\'"]([^\'"]+)[\'"]', txt)
        return m.group(1).strip() if m else None

    def normalize(txt: str) -> str:
        # Replace the version value with a placeholder, collapse whitespace minimally
        return re.sub(r'version\s*=\s*[\'"][^\'"]+[\'"]', 'version="__VERSION__"', txt)

    cur_ver = extract_version(current_text)
    if not cur_ver:
        print("❌ Could not find version=... in current setup.py.")
        sys.exit(1)

    if head_text:
        head_ver = extract_version(head_text)
        if not head_ver:
            print("❌ Could not find version=... in HEAD:setup.py (unexpected).")
            sys.exit(1)

        if cur_ver == head_ver:
            print("❌ setup.py changed but version did not change. Only version changes are allowed.")
            sys.exit(1)

        # Compare normalized contents to ensure ONLY version changed
        if normalize(current_text) != normalize(head_text):
            print("❌ setup.py has changes other than the version line. Please revert them.")
            sys.exit(1)

    print(f"✅ Detected only version change in setup.py (HEAD → {cur_ver}).")

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

def commit_version_bump_if_needed(root: Path, version: str):
    """
    If setup.py is modified and only version changed, create a commit for it.
    No-op if setup.py is unchanged.
    """
    status = git_status_porcelain(root)
    setup_changed = any(line.endswith("setup.py") for line in status)
    if not setup_changed:
        return

    # Stage & commit only setup.py
    run_do(["git", "add", "setup.py"], cwd=root)
    run_do(["git", "commit", "-m", f"Bump version to {version}"], cwd=root)
    run_do(["git", "push"], cwd=root)
    print("✅ Committed and pushed version bump in setup.py.")

def create_and_push_tag(version, root):
    run_do(["git", "tag", "-a", version, "-m", f"Release {version}"], cwd=root)
    run_do(["git", "push", "origin", version], cwd=root)
    print(f"🎉 Tagged and pushed '{version}'. GitHub Actions will now publish to PyPI.")

if __name__ == "__main__":
    print("🚦 Mode:", "REAL (will commit/tag/push)" if REAL_MODE else "TEST (default; logs only)")
    root = repo_root()
    ensure_only_setup_py_changed(root)
    ensure_branch_synced(root)
    version = get_version_from_setup_py(root)
    # In test mode this logs the commit commands, in real mode it actually commits/pushes
    commit_version_bump_if_needed(root, version)
    ensure_tag_not_exists(version, root)
    create_and_push_tag(version, root)
