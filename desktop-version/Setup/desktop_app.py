"""
ColdLeads Desktop Application Launcher v2.0
Embeds FastAPI Backend + React Frontend into a native Windows Desktop App Window.
"""

import os
import sys
import time
import socket
import threading
import subprocess
import webbrowser

# Locate backend and frontend directories relative to the installation
SETUP_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.dirname(SETUP_DIR)
PROJECT_DIR = os.path.dirname(DESKTOP_DIR)

BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
FRONTEND_DIST = os.path.join(PROJECT_DIR, "frontend", "dist")

# If bundled via PyInstaller, use sys._MEIPASS
if getattr(sys, "frozen", False):
    BUNDLE_DIR = sys._MEIPASS
    BACKEND_DIR = BUNDLE_DIR
    FRONTEND_DIST = os.path.join(BUNDLE_DIR, "frontend", "dist")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def find_free_port(preferred_port: int = 8000) -> int:
    """Check if preferred_port is open, otherwise find an available free port."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", preferred_port))
            return preferred_port
    except OSError:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


def start_backend_server(port: int):
    """Run Uvicorn server in a dedicated background thread."""
    try:
        import uvicorn
        from main import app
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except Exception as e:
        print(f"[!] Server error: {e}")


def launch_desktop_window(url: str):
    """Launch app in a dedicated borderless Windows Chrome/Edge App Window or browser."""
    chrome_paths = [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
    ]

    for exe in chrome_paths:
        if os.path.isfile(exe):
            try:
                user_data_dir = os.path.join(os.path.expanduser("~"), ".coldleads_profile")
                subprocess.Popen([
                    exe,
                    f"--app={url}",
                    f"--user-data-dir={user_data_dir}",
                    "--window-size=1400,920",
                    "--disable-extensions",
                    "--no-first-run",
                ])
                return
            except Exception:
                pass

    # Fallback to system default browser
    webbrowser.open(url)


def main():
    print("=" * 65)
    print("   ColdLeads B2B Lead Scraper — Desktop Edition v2.0")
    print("=" * 65)

    port = find_free_port(8000)
    app_url = f"http://127.0.0.1:{port}"

    # Start FastAPI backend in background thread
    server_thread = threading.Thread(
        target=start_backend_server,
        args=(port,),
        daemon=True,
        name="ColdLeads-Server",
    )
    server_thread.start()

    # Wait briefly for server startup
    time.sleep(1.2)
    print(f"[*] Backend server started at {app_url}")
    print("[*] Opening ColdLeads Desktop Window...")

    # Launch desktop application window
    launch_desktop_window(app_url)

    print("[*] ColdLeads is running. Press Ctrl+C in this console to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down ColdLeads...")
        sys.exit(0)


if __name__ == "__main__":
    main()
