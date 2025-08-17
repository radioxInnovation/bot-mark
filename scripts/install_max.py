#!/usr/bin/env python3
"""
scripts/install_max.py — Build / Install / Test Helper (UTF-8 safe)

Pipeline (always):
  1) create fresh venv at ../.venv-max
  2) upgrade pip/setuptools/wheel
  3) clean __pycache__ in project tree
  4) build a fresh wheel with `python -m build --wheel`
  5) install THAT wheel as a PEP 508 direct ref with extras [all] (or override via env MAX_EXTRAS)
  6) ensure pytest and run tests (CLI args are passed through)

Notes:
- Extras default to "all". Override with env MAX_EXTRAS="jinja2,mako"
- If a constraints.txt exists in repo root, it is used automatically
"""

from __future__ import annotations
import os, sys, subprocess, shutil, venv
from pathlib import Path
from typing import Iterable, Optional

DEFAULT_TIMEOUT_PIP = 15 * 60
DEFAULT_TIMEOUT_TEST = None  # override with env MAX_TEST_TIMEOUT

# ---------- subprocess wrapper (UTF-8 safe) ----------

def run(
    cmd: Iterable[str],
    cwd: Optional[str] = None,
    capture: bool = False,
    timeout: Optional[int] = None,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    merged_env.setdefault("PYTHONIOENCODING", "utf-8")
    merged_env.setdefault("PYTHONUTF8", "1")
    merged_env.setdefault("LC_ALL", "C.UTF-8")
    merged_env.setdefault("LANG", "C.UTF-8")
    merged_env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")

    return subprocess.run(
        list(cmd),
        cwd=cwd,
        capture_output=bool(capture),
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env=merged_env,
        check=False,
    )

# ---------- venv helpers ----------

def create_venv(venv_dir: Path) -> None:
    if venv_dir.exists():
        shutil.rmtree(venv_dir)
    venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)

def venv_python(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

# ---------- pip helpers ----------

def _print_proc(label: str, res: subprocess.CompletedProcess) -> None:
    print(f"[MAX] {label}")
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, file=sys.stderr, end="")

def pip_run(python: Path, args: list[str], label: str, cwd: Optional[str] = None, timeout: Optional[int] = None) -> None:
    base = [str(python), "-X", "utf8", "-m", "pip"]
    pip_opts = ["--no-input", "--progress-bar", "off"]
    res = run(base + args + pip_opts, cwd=cwd, capture=True, timeout=timeout or DEFAULT_TIMEOUT_PIP)
    _print_proc(label, res)
    if res.returncode != 0:
        raise SystemExit(res.returncode)

def pip_upgrade_tooling(python: Path) -> None:
    pip_run(python, ["install", "--upgrade", "pip", "setuptools", "wheel"], "Upgrading pip/setuptools/wheel")

def pip_install_local_wheel_with_extras(
    python: Path,
    *,
    wheel_path: Path,
    package_name: str = "botmark",
    extras: str = "all",
    constraints_file: Optional[Path] = None,
) -> None:
    # Install as a PEP 508 direct reference so extras are honored
    if extras:
        req = f"{package_name}[{extras}] @ file://{wheel_path.resolve().as_posix()}"
    else:
        req = f"{package_name} @ file://{wheel_path.resolve().as_posix()}"
    args = ["install", req]
    if constraints_file and constraints_file.exists():
        args = ["install", "-c", str(constraints_file), req]
    pip_run(python, args, f"Installing {package_name}[{extras}] from local wheel {wheel_path.name}")

def ensure_pytest(python: Path, constraints_file: Optional[Path]) -> None:
    check = run([str(python), "-X", "utf8", "-c", "import pytest; print(pytest.__version__)"], capture=True)
    if check.returncode == 0:
        print(f"[MAX] pytest found ({check.stdout.strip()})")
        return
    args = ["install"]
    if constraints_file and constraints_file.exists():
        args += ["-c", str(constraints_file)]
    args += ["pytest"]
    pip_run(python, args, "Installing pytest")

# ---------- cleaning ----------

def clear_pycache(root: Path) -> None:
    for path in root.rglob("__pycache__"):
        try:
            shutil.rmtree(path)
            print(f"[MAX] Removed {path}")
        except Exception as e:
            print(f"[MAX] Warning: failed to remove {path}: {e}", file=sys.stderr)

# ---------- build ----------

def ensure_build_tool(python: Path) -> None:
    check = run([str(python), "-X", "utf8", "-c", "import build, sys; print(build.__version__)"], capture=True)
    if check.returncode == 0:
        print(f"[MAX] build package found ({check.stdout.strip()})")
        return
    pip_run(python, ["install", "build"], "Installing build tool")

def build_wheel(python: Path, project_root: Path) -> Path:
    dist_dir = project_root / "dist"
    if dist_dir.exists():
        for p in dist_dir.glob("*"):
            try:
                p.unlink()
            except IsADirectoryError:
                shutil.rmtree(p)
    dist_dir.mkdir(exist_ok=True)

    ensure_build_tool(python)
    print("[MAX] Building wheel with 'python -m build --wheel'")
    res = run([str(python), "-X", "utf8", "-m", "build", "--wheel"], cwd=str(project_root), capture=True, timeout=DEFAULT_TIMEOUT_PIP)
    _print_proc("Build output", res)
    if res.returncode != 0:
        raise SystemExit(res.returncode)

    wheels = sorted(dist_dir.glob("*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        print("[MAX] ERROR: No wheel found in dist/", file=sys.stderr)
        raise SystemExit(2)
    wheel_path = wheels[0]
    print(f"[MAX] Built wheel: {wheel_path.name}")
    return wheel_path

# ---------- pytest ----------

def run_pytest(python: Path, project_root: Path, pytest_args: list[str], extra_env: Optional[dict] = None, timeout: Optional[int] = None) -> int:
    print("[MAX] Running pytest")
    res = run([str(python), "-X", "utf8", "-m", "pytest"] + pytest_args, cwd=str(project_root), capture=True, env=extra_env, timeout=timeout)
    if res.stdout:
        print(res.stdout, end="")
    if res.stderr:
        print(res.stderr, file=sys.stderr, end="")
    return res.returncode

# ---------- pipeline ----------

def install_and_test(
    name: str,
    project_root: Path,
    constraints_file: Optional[Path],
    extras_default: str = "all",
    keep: bool = False,
    pytest_args: Optional[list[str]] = None,
) -> int:
    print(f"[{name}] Starting install/test pipeline")
    venv_dir = project_root / f".venv-{name.lower()}"
    create_venv(venv_dir)
    py = venv_python(venv_dir)

    ver = run([str(py), "-X", "utf8", "-c", "import sys; print(sys.version)"], capture=True)
    if ver.stdout:
        print(f"[MAX] Python in venv: {ver.stdout.strip()}")

    try:
        pip_upgrade_tooling(py)
        clear_pycache(project_root)

        wheel_path = build_wheel(py, project_root)

        # Allow override via env MAX_EXTRAS, default to "all"
        extras = os.getenv("MAX_EXTRAS", extras_default)
        if extras:
            extras = ",".join(part.strip() for part in extras.split(",") if part.strip()) or None

        pip_install_local_wheel_with_extras(
            py,
            wheel_path=wheel_path,
            package_name="botmark",
            extras=extras or "",
            constraints_file=constraints_file,
        )

        ensure_pytest(py, constraints_file)

        test_timeout_env = os.getenv("MAX_TEST_TIMEOUT")
        test_timeout = int(test_timeout_env) if test_timeout_env else DEFAULT_TIMEOUT_TEST
        code = run_pytest(py, project_root, pytest_args or ["-q"], timeout=test_timeout)
        print(f"[{name}] pytest exit code: {code}")
        if code != 0:
            print(f"[{name}] Tests failed.", file=sys.stderr)
        else:
            print(f"[{name}] Tests passed.")
        return code
    finally:
        if not keep:
            try:
                shutil.rmtree(venv_dir)
                print(f"[MAX] Removed {venv_dir}")
            except Exception as e:
                print(f"[MAX] Warning: failed to remove {venv_dir}: {e}", file=sys.stderr)

# ---------- entry point ----------

def main() -> None:
    # project_root = scripts/.. (repo root)
    project_root = Path(__file__).resolve().parent.parent

    # Auto-detect constraints.txt in repo root
    constraints = project_root / "constraints.txt"
    if not constraints.exists():
        constraints = None

    # Pass any remaining args to pytest
    pytest_args = sys.argv[1:]

    exit_code = install_and_test(
        name="MAX",
        project_root=project_root,
        constraints_file=constraints,
        extras_default="all",
        keep=False,
        pytest_args=pytest_args,
    )
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
