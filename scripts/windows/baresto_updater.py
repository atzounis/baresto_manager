#!/usr/bin/env python3
"""
Baresto Manager — Windows updater.

Downloads the latest version from GitHub (git pull when available, else ZIP),
preserves local data (.env, db.sqlite3, media/, .venv/), refreshes dependencies,
and runs database migrations.

Run from the project root, or place BarestoUpdate.exe next to manage.py.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from baresto_launcher import (
    SETUP_MARKER,
    find_project_root,
    find_system_python,
    run_command,
    venv_python,
)

DEFAULT_REPO = "atzounis/baresto_manager"
DEFAULT_BRANCH = "main"
GITHUB_API = "https://api.github.com/repos/{repo}/releases/latest"
GITHUB_ZIP = "https://github.com/{repo}/archive/refs/heads/{branch}.zip"

# Never overwrite these paths inside the project root (relative segments).
PRESERVE_SEGMENTS = frozenset(
    {
        ".env",
        "db.sqlite3",
        ".venv",
        "media",
        "BarestoManager.exe",
        "BarestoUpdate.exe",
    }
)


def _pause_on_error(code: int = 1) -> int:
    if sys.platform == "win32" and sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


def log(msg: str) -> None:
    print(msg, flush=True)


def repo_settings(project_root: Path) -> tuple[str, str]:
    repo = os.environ.get("BARESTO_GITHUB_REPO", DEFAULT_REPO).strip() or DEFAULT_REPO
    branch = DEFAULT_BRANCH
    env_file = project_root / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("BARESTO_GITHUB_REPO="):
                value = line.split("=", 1)[1].strip()
                if value:
                    repo = value
            elif line.startswith("BARESTO_UPDATE_BRANCH="):
                value = line.split("=", 1)[1].strip()
                if value:
                    branch = value
    return repo, branch


def should_preserve(rel: Path) -> bool:
    return any(part in PRESERVE_SEGMENTS for part in rel.parts)


def try_git_pull(project_root: Path) -> bool:
    if not (project_root / ".git").is_dir() or shutil.which("git") is None:
        return False
    log("Git repository detected — pulling latest changes...")
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=project_root,
        check=False,
    )
    if result.returncode != 0:
        log("WARNING: git pull failed; falling back to GitHub ZIP download.")
        return False
    log("Git pull complete.")
    return True


def _download(url: str, dest: Path) -> None:
    log(f"Downloading {url} ...")
    request = urllib.request.Request(url, headers={"User-Agent": "BarestoManager-Updater/1.0"})
    with urllib.request.urlopen(request, timeout=120) as response:
        dest.write_bytes(response.read())


def latest_release_zip_url(repo: str) -> str | None:
    api_url = GITHUB_API.format(repo=repo)
    request = urllib.request.Request(api_url, headers={"User-Agent": "BarestoManager-Updater/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError):
        return None
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.endswith(".zip"):
            return asset.get("browser_download_url")
    return data.get("zipball_url")


def extract_root_dir(extract_dir: Path) -> Path:
    children = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    raise RuntimeError("Unexpected archive layout — could not find project folder in ZIP.")


def merge_update_tree(source_root: Path, project_root: Path) -> int:
    copied = 0
    for src in source_root.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(source_root)
        if should_preserve(rel):
            continue
        dest = project_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied += 1
    return copied


def download_and_apply_zip(project_root: Path, repo: str, branch: str) -> None:
    zip_url = latest_release_zip_url(repo)
    if zip_url:
        log("Using latest GitHub release.")
    else:
        zip_url = GITHUB_ZIP.format(repo=repo, branch=branch)
        log(f"Using branch archive: {branch}")

    with tempfile.TemporaryDirectory(prefix="baresto-update-") as tmp:
        tmp_path = Path(tmp)
        zip_path = tmp_path / "update.zip"
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()

        _download(zip_url, zip_path)
        log("Extracting update package...")
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)

        source_root = extract_root_dir(extract_dir)
        count = merge_update_tree(source_root, project_root)
        log(f"Updated {count} file(s). Preserved .env, db.sqlite3, media/, and .venv/.")


def refresh_dependencies_and_migrate(project_root: Path) -> None:
    system_python = find_system_python()
    if not system_python:
        log(
            "ERROR: Python 3.12+ is required to finish the update.\n"
            "Install Python, then run this updater again."
        )
        raise SystemExit(_pause_on_error(1))

    py = venv_python(project_root)
    if not py.is_file():
        log("Creating virtual environment (.venv)...")
        run_command([system_python, "-m", "venv", str(project_root / ".venv")], cwd=project_root, label="venv")
        py = venv_python(project_root)

    requirements = project_root / "requirements" / "local.txt"
    if not requirements.is_file():
        log(f"ERROR: Missing {requirements}")
        raise SystemExit(_pause_on_error(1))

    log("Installing / updating Python libraries...")
    run_command([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=project_root, label="pip upgrade")
    run_command(
        [str(py), "-m", "pip", "install", "-r", str(requirements)],
        cwd=project_root,
        label="pip install requirements",
    )

    log("Applying database migrations...")
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    result = subprocess.run(
        [str(py), "manage.py", "migrate", "--noinput"],
        cwd=project_root,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        log("ERROR: migrate failed.")
        raise SystemExit(_pause_on_error(result.returncode))

    marker = project_root / ".venv" / SETUP_MARKER
    marker.write_text("ok\n", encoding="utf-8")
    log("Migrations complete.")


def main() -> int:
    if sys.platform != "win32":
        log("NOTE: This updater is intended for Windows. Continuing anyway...\n")

    project_root = find_project_root()
    os.chdir(project_root)
    repo, branch = repo_settings(project_root)

    log(f"Baresto Manager updater — {project_root}")
    log(f"Source: github.com/{repo} ({branch})\n")
    log("Stop the running server (Ctrl+C in its window) before updating.\n")

    if not try_git_pull(project_root):
        download_and_apply_zip(project_root, repo, branch)

    refresh_dependencies_and_migrate(project_root)

    log("\nUpdate complete. Start Baresto Manager again with Start-BarestoManager.bat or BarestoManager.exe.")
    if sys.platform == "win32" and sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
