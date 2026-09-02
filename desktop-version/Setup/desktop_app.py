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
import traceback

# Locate backend and frontend directories relative to the installation
SETUP_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.dirname(SETUP_DIR)
PROJECT_DIR = os.path.dirname(DESKTOP_DIR)

BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
FRONTEND_DIST = os.path.join(PROJECT_DIR, "frontend", "dist")

# If bundled via PyInstaller, use sys._MEIPASS or _internal folder
if getattr(sys, "frozen", False):
    BUNDLE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    BACKEND_DIR = BUNDLE_DIR
    FRONTEND_DIST = os.path.join(BUNDLE_DIR, "frontend", "dist")
    if not os.path.isdir(FRONTEND_DIST):
        FRONTEND_DIST = os.path.join(os.path.dirname(sys.executable), "_internal", "frontend", "dist")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Explicit top-level imports for PyInstaller packaging
try:
    import email
    import email.mime
    import email.mime.multipart
    import email.mime.text
    import email.mime.base
    import email.mime.application
    import email.mime.image
    import email.mime.audio
    import email.header
    import email.utils
    import email.encoders
    import email.parser
    import email.generator
    import email.policy
    import smtplib
    import ssl
    import sqlite3
    import queue
    import concurrent.futures
    import ipaddress
    import html
    import urllib.parse
    import urllib.request
    import pandas as pd
    import openpyxl
    import requests
    import httpx
    import fastapi
    import uvicorn
    import pydantic
    import selenium
    import dotenv
    import jose
    import bcrypt
    import psutil
except Exception as e:
    print(f"[!] Pre-import warning: {e}")


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
        print(f"[!] Backend server error: {e}")
        traceback.print_exc()


def wait_for_server_ready(port: int, max_seconds: float = 15.0) -> bool:
    """Wait until backend server is actively accepting connections."""
    start_time = time.time()
    while time.time() - start_time < max_seconds:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


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
    print(f"[*] Starting local backend on port {port}...")
    server_thread = threading.Thread(
        target=start_backend_server,
        args=(port,),
        daemon=True,
        name="ColdLeads-Server",
    )
    server_thread.start()

    # Wait for server to be fully ready before opening UI
    print("[*] Waiting for backend server to initialize...")
    if wait_for_server_ready(port, max_seconds=15.0):
        print(f"[OK] Backend server active at {app_url}")
    else:
        print("[!] Backend server took longer than expected, attempting UI launch...")

    print("[*] Opening ColdLeads Desktop Window...")
    launch_desktop_window(app_url)

    print("[OK] ColdLeads is running. Press Ctrl+C in this console to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Shutting down ColdLeads...")
        sys.exit(0)


if __name__ == "__main__":
    main()
