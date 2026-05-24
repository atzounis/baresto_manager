# Windows launcher

Double-click launcher for Baresto Manager on **Windows 10/11**. No Docker or Redis required. Download the project ZIP, then either:

1. **`BarestoManager.exe`** (recommended) — place in the project folder next to `manage.py`, then double-click.
2. **`scripts/windows/Start-BarestoManager.bat`** — same setup, requires Python 3.12+ already on PATH.

## What the launcher does

1. Finds the project folder (`manage.py`)
2. Installs **Python 3.12** via `winget` if missing (or opens python.org)
3. Creates `.venv` and runs `pip install -r requirements/local.txt` (first run only)
4. Copies `.env.example` → `.env` if needed, runs migrations
5. Starts `python manage.py runserver` on port **8765**
6. Opens **http://127.0.0.1:8765/login/** in your default browser

Leave the console window open while using the app. Press **Ctrl+C** to stop.

## Build the `.exe` (on a Windows PC)

PyInstaller cannot cross-compile from macOS/Linux. On Windows, after extracting the project:

```bat
cd scripts\windows
build-exe.bat
```

This creates **`BarestoManager.exe`** in the project root. Copy the whole project folder (or ZIP release) with that exe inside.

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
| Firewall prompt | Allow Python on **Private** networks for phone/tablet access on Wi‑Fi. |
| Port in use | Change `DJANGO_PORT` in `.env` or close the other app using 8765. |

See also [README — Running on Windows (beginners)](../../README.md#running-on-windows-beginners).
