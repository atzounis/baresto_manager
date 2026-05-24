#!/usr/bin/env python3
"""
Baresto Manager — Windows launcher.

Sets up a local venv (first run), installs Python dependencies, starts the dev server,
and opens the login page in the default browser.

Run from the project root, or place BarestoManager.exe next to manage.py.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

MIN_PYTHON = (3, 12)
DEFAULT_PORT = 8765
LOGIN_PATH = "/login/"
SETUP_MARKER = ".baresto_setup_complete"
WINGET_PYTHON_ID = "Python.Python.3.12"


def _pause_on_error(code: int = 1) -> int:
    if sys.platform == "win32" and sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass
    return code


def log(msg: str) -> None:
    print(msg, flush=True)


def find_project_root() -> Path:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
    candidates.append(Path(__file__).resolve().parent)
    for start in candidates:
        for root in [start, *start.parents]:
            if (root / "manage.py").is_file():
                return root
    log(
        "ERROR: Could not find Baresto Manager (manage.py).\n"
        "Place this launcher in the project folder that contains manage.py."
    )
    raise SystemExit(_pause_on_error(1))


def parse_port(project_root: Path) -> int:
    env_file = project_root / ".env"
    if not env_file.is_file():
        return DEFAULT_PORT
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DJANGO_PORT="):
            try:
                return int(line.split("=", 1)[1].strip())
            except ValueError:
                break
    return DEFAULT_PORT


def python_version_ok(exe: str) -> bool:
    try:
        result = subprocess.run(
            [exe, "-c", "import sys; print(sys.version_info[:2])"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode != 0:
            return False
        major, minor = map(int, result.stdout.strip().strip("()").split(", "))
        return (major, minor) >= MIN_PYTHON
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return False


def find_system_python() -> str | None:
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            if result.returncode == 0:
                exe = result.stdout.strip()
                if exe and python_version_ok(exe):
                    return exe
        except OSError:
            pass

    for name in ("python3", "python"):
        exe = shutil.which(name)
        if exe and python_version_ok(exe):
            return exe
    return None


def install_python_windows() -> str | None:
    if shutil.which("winget") is None:
        log(
            "Python 3.12+ is required but was not found.\n"
            "Install from https://www.python.org/downloads/windows/\n"
            "Enable “Add python.exe to PATH”, then run this launcher again."
        )
        webbrowser.open("https://www.python.org/downloads/windows/")
        return None

    log("Python 3.12+ not found. Installing via winget (one-time)...")
    subprocess.run(
        [
            "winget",
            "install",
            "-e",
            "--id",
            WINGET_PYTHON_ID,
            "--accept-package-agreements",
            "--accept-source-agreements",
        ],
        check=False,
    )

    common_paths = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python312/python.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python313/python.exe",
        Path("C:/Program Files/Python312/python.exe"),
        Path("C:/Program Files/Python313/python.exe"),
    ]
    for path in common_paths:
        if path.is_file() and python_version_ok(str(path)):
            return str(path)

    return find_system_python()


def venv_python(project_root: Path) -> Path:
    return project_root / ".venv" / "Scripts" / "python.exe"


def needs_setup(project_root: Path) -> bool:
    py = venv_python(project_root)
    if not py.is_file():
        return True
    marker = project_root / ".venv" / SETUP_MARKER
    req = project_root / "requirements" / "local.txt"
    if not marker.is_file():
        return True
    if req.is_file() and req.stat().st_mtime > marker.stat().st_mtime:
        return True
    return False


def run_command(cmd: list[str], *, cwd: Path, label: str) -> None:
    log(f"  → {label}")
    result = subprocess.run(cmd, cwd=cwd, check=False)
    if result.returncode != 0:
        log(f"ERROR: {label} failed (exit {result.returncode}).")
        raise SystemExit(_pause_on_error(result.returncode))


def setup_project(project_root: Path, system_python: str) -> Path:
    py = venv_python(project_root)
    if not py.is_file():
        log("Creating virtual environment (.venv)...")
        run_command([system_python, "-m", "venv", str(project_root / ".venv")], cwd=project_root, label="venv")

    py = venv_python(project_root)
    requirements = project_root / "requirements" / "local.txt"
    if not requirements.is_file():
        log(f"ERROR: Missing {requirements}")
        raise SystemExit(_pause_on_error(1))

    log("Installing / updating Python libraries (first run may take several minutes)...")
    run_command([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=project_root, label="pip upgrade")
    run_command(
        [str(py), "-m", "pip", "install", "-r", str(requirements)],
        cwd=project_root,
        label="pip install requirements",
    )

    env_file = project_root / ".env"
    env_example = project_root / ".env.example"
    if not env_file.is_file() and env_example.is_file():
        log("Creating .env from .env.example...")
        shutil.copy2(env_example, env_file)

    log("Applying database migrations...")
    run_command([str(py), "manage.py", "migrate", "--noinput"], cwd=project_root, label="migrate")

    marker = project_root / ".venv" / SETUP_MARKER
    marker.write_text("ok\n", encoding="utf-8")
    log("Setup complete.\n")
    return py


def firewall_rule_name(port: int) -> str:
    return f"Baresto Manager (TCP {port})"


def firewall_rule_exists(name: str) -> bool:
    result = subprocess.run(
        ["netsh", "advfirewall", "firewall", "show", "rule", f"name={name}"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode == 0 and name in result.stdout


def ensure_firewall_rule(project_root: Path, port: int) -> None:
    """Allow inbound TCP on the app port so phones on the same Wi‑Fi can connect."""
    if sys.platform != "win32":
        return

    name = firewall_rule_name(port)
    if firewall_rule_exists(name):
        log(f"Windows Firewall rule already present: {name}")
        return

    log(f"Adding Windows Firewall rule for incoming TCP port {port} (private networks)...")
    result = subprocess.run(
        [
            "netsh",
            "advfirewall",
            "firewall",
            "add",
            "rule",
            f"name={name}",
            "dir=in",
            "action=allow",
            "protocol=TCP",
            f"localport={port}",
            "profile=private",
            "enable=yes",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode == 0:
        log(f"Firewall rule added: {name}")
        return

    bat = project_root / "scripts" / "windows" / "Add-Firewall-Rule.bat"
    bat_hint = str(bat.relative_to(project_root)) if bat.is_file() else "scripts\\windows\\Add-Firewall-Rule.bat"
    log(
        "Could not add the firewall rule automatically (Administrator rights may be required).\n"
        "Phones on Wi‑Fi may not connect until you allow the port.\n"
        f"  Option 1: Right-click {bat_hint} → Run as administrator\n"
        f"  Option 2: In an elevated Command Prompt, run:\n"
        f'    netsh advfirewall firewall add rule name="{name}" dir=in action=allow '
        f"protocol=TCP localport={port} profile=private enable=yes\n"
        "  Option 3: Allow Python when Windows prompts you on first run."
    )


def wait_for_server(url: str, timeout: int = 90) -> bool:
    for _ in range(timeout):
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if 200 <= resp.status < 500:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(1)
    return False


def start_server(project_root: Path, py: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    log(f"Starting Baresto Manager on port {port}...")
    log("Leave this window open while using the app. Press Ctrl+C to stop.\n")
    return subprocess.Popen(
        [str(py), "manage.py", "runserver"],
        cwd=project_root,
        env=env,
    )


def main() -> int:
    if sys.platform != "win32":
        log("NOTE: This launcher is intended for Windows. Continuing anyway...\n")

    project_root = find_project_root()
    os.chdir(project_root)
    log(f"Baresto Manager — {project_root}\n")

    system_python = find_system_python()
    if not system_python:
        if sys.platform == "win32":
            system_python = install_python_windows()
        if not system_python:
            return _pause_on_error(1)

    log(f"Using Python: {system_python}")

    py = venv_python(project_root)
    if needs_setup(project_root):
        py = setup_project(project_root, system_python)
    elif not py.is_file():
        py = setup_project(project_root, system_python)

    port = parse_port(project_root)
    login_url = f"http://127.0.0.1:{port}{LOGIN_PATH}"

    ensure_firewall_rule(project_root, port)
    server = start_server(project_root, py, port)
    try:
        log(f"Waiting for server at {login_url} ...")
        if wait_for_server(login_url):
            log("Opening browser...")
            webbrowser.open(login_url)
        else:
            log("Server is slow to respond. Open this URL manually:")
            log(f"  {login_url}")

        return server.wait()
    except KeyboardInterrupt:
        log("\nStopping server...")
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
