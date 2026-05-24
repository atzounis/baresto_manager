# Windows launcher

Double-click launcher for Baresto Manager on **Windows 10/11**. No Docker or Redis required. Download the project ZIP, then either:

1. **`BarestoManager.exe`** (recommended) — place in the project folder next to `manage.py`, then double-click.
2. **`BarestoUpdate.exe`** — download the latest version, refresh libraries, and run migrations (see [Update](#update) below).
3. **`scripts/windows/Start-BarestoManager.bat`** — same setup as the launcher, requires Python 3.12+ already on PATH.

## What the launcher does

1. Finds the project folder (`manage.py`)
2. Installs **Python 3.12** via `winget` if missing (or opens python.org)
3. Creates `.venv` and runs `pip install -r requirements/local.txt` (first run only)
4. Copies `.env.example` → `.env` if needed, runs migrations
5. Adds a Windows Firewall inbound rule for TCP port **8765** (private networks), or prints how to run `Add-Firewall-Rule.bat` as administrator
6. Starts `python manage.py runserver` on port **8765**
7. Opens **http://127.0.0.1:8765/login/** in your default browser

Leave the console window open while using the app. Press **Ctrl+C** to stop.

## Update

Stop the server first (**Ctrl+C** in the launcher window), then either:

1. **`BarestoUpdate.exe`** in the project root (build with `build-update-exe.bat`), or
2. **`Update-BarestoManager.bat`** at the project root, or
3. **`scripts/windows/Update-BarestoManager.bat`**

The updater will:

1. **`git pull`** if the folder is a git clone and git is installed
2. Otherwise download the latest **GitHub release** ZIP, or the **`main`** branch archive
3. Merge files into the project folder — **preserves** `.env`, `db.sqlite3`, `media/`, and `.venv/`
4. Run `pip install -r requirements/local.txt` and `python manage.py migrate`

Optional in `.env`: `BARESTO_GITHUB_REPO`, `BARESTO_UPDATE_BRANCH`.

## Build the `.exe` (on a Windows PC)

PyInstaller cannot cross-compile from macOS/Linux. On Windows, after extracting the project:

```bat
cd scripts\windows
build-exe.bat
```

This creates **`BarestoManager.exe`** in the project root. Copy the whole project folder (or ZIP release) with that exe inside.

Build the updater executable:

```bat
cd scripts\windows
build-update-exe.bat
```

This creates **`BarestoUpdate.exe`** in the project root.

Alternatively:

```bat
cd scripts\windows
python -m pip install -r requirements-build.txt
python -m PyInstaller --onefile --console --name BarestoManager baresto_launcher.py
copy dist\BarestoManager.exe ..\..\BarestoManager.exe
```

## Demo login

| Role   | Username | Password    | PIN  |
|--------|----------|-------------|------|
| Waiter | waiter   | waiter1234  | 2222 |
| Manager| manager  | manager1234 | 1111 |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `manage.py` not found | Put `BarestoManager.exe` in the same folder as `manage.py`. |
| Python install fails | Install manually from [python.org](https://www.python.org/downloads/windows/) with **Add to PATH**. |
| Firewall / phone access | The launcher adds rule **Baresto Manager (TCP 8765)** automatically. If phones still cannot connect, run **`Add-Firewall-Rule.bat`** as administrator (reads `DJANGO_PORT` from `.env`). |
| Port in use | Change `DJANGO_PORT` in `.env` or close the other app using 8765. |
| Update failed | Stop the server first; run **`Update-BarestoManager.bat`** as administrator if files are locked. |

See also [README — Running on Windows (beginners)](../../README.md#running-on-windows-beginners).
