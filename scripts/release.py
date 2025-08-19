#!/usr/bin/env python3
import subprocess
import sys
import re
from pathlib import Path

# Default = TEST. Use --real to actually commit/tag/push.
REAL_MODE = "--real" in sys.argv

def _run(cmd, check=True, cwd=None):
    return subprocess.run(cmd, check=check, capture_output=True, text=True, cwd=cwd).stdout.strip()

def run_read(cmd, cwd=None):
    if not REAL_MODE:
        print(f"[TEST-READ] {' '.join(cmd)}")
    return _run(cmd, cwd=cwd)

def run_do(cmd, cwd=None):
    if not REAL_MODE:
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
    """Return three sets: staged, unstaged, untracked file paths (posix-style)."""
    staged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only", "--cached"], cwd=root).splitlines() if p.strip())
    unstaged = set(p.replace("\\", "/") for p in run_read(["git", "diff", "--name-only"], cwd=root).splitlines() if p.strip())
    untracked = set(p.replace("\\", "/") for p in run_read(["git", "ls-files", "--others", "--exclude-standard"], cwd=root).splitlines() if p.strip())
    return staged, unstaged, untracked

def ensure_only_setup_py_changed(root: Path):
    staged, unstaged, untracked = list_changes(root)
    changed = staged | unstaged | untracked
    if not changed:
        return  # repo clean, also fine

    # allow only setup.py changes
    allowed = {"setup.py"}
    other = sorted(p for p in changed if p not in allowed)
    if other:
        print("❌ Repo has changes outside setup.py:\n  " + "\n  ".join(other))
        sys.exit(1)

    # If setup.py changed, verify only the version line differs vs HEAD
    setup_path = root / "setup.py"
    current_text = setup_path.read_text(encoding="utf-8", errors="ignore")
    try:
        head_text = run_read(["git", "show", "HEAD:setup.py"], cwd=root)
    except subprocess.CalledProcessError:
        head_text = ""  # no HEAD (new repo/file) — skip strict diff

    def extract_version(txt: str):
        m = re.search(r'version\s*=\s*[\'"]([^\'"]+)[\'"]', txt)
        return (m.group(1).strip() if m else None)

    def normalize(txt: str) -> str:
        # Replace only the version value and normalize line endings
        txt = txt.replace("\r\n", "\n")
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
        if normalize(current_text) != normalize(head_text):
            print("❌ setup.py has changes other than the version line. Please revert them.")
            sys.exit(1)

    print(f"✅ Detected only version change in setup.py (→ {cur_ver}).")

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
    print("🚦 Mode:", "REAL (will commit/tag/push)" if REAL_MODE else "TEST (default; logs only)")
    root = repo_root()
    ensure_only_setup_py_changed(root)
    ensure_branch_synced(root)
    version = get_version_from_setup_py(root)
    commit_version_bump_if_needed(root, version)   # logs in TEST, acts in REAL
    ensure_tag_not_exists(version, root)
    create_and_push_tag(version, root)
