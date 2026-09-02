"""
Automated Standalone Setup Executable Builder for ColdLeads v2.0
Compiles React frontend + Python backend + Chrome drivers into ColdLeads-Setup.exe.
"""

import os
import sys
import shutil
import subprocess

SETUP_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_DIR = os.path.dirname(SETUP_DIR)
PROJECT_DIR = os.path.dirname(DESKTOP_DIR)

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
OUTPUT_DIR = os.path.join(SETUP_DIR, "Output")
DOWNLOADS_DIR = os.path.join(DESKTOP_DIR, "Landing_Page", "downloads")


def build():
    print("=" * 70)
    print("   Building ColdLeads-Setup.exe Standalone Windows Application")
    print("=" * 70)

    # 1. Build React Frontend
    print("\n[1/3] Compiling React Frontend (Vite)...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    res = subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)
    if res.returncode != 0:
        print("[!] Frontend compilation failed!")
        sys.exit(1)
    print("[OK] Frontend compiled.")

    # 2. Build PyInstaller Executable
    print("\n[2/3] Compiling Standalone Executable (PyInstaller)...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--name=ColdLeads-Setup",
        f"--add-data={FRONTEND_DIST};frontend/dist",
        f"--add-data={os.path.join(BACKEND_DIR, 'extra_locations.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'locations.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'scraper_api.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'database.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'smtp_service.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'auth.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'main.py')};.",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespans",
        "--hidden-import=uvicorn.lifespans.on",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={os.path.join(SETUP_DIR, 'build')}",
        f"--specpath={SETUP_DIR}",
        os.path.join(SETUP_DIR, "desktop_app.py"),
    ]

    print("[*] Running PyInstaller...")
    res2 = subprocess.run(pyinstaller_cmd, cwd=SETUP_DIR)
    if res2.returncode != 0:
        print("[!] PyInstaller compilation failed!")
        sys.exit(1)

    built_exe = os.path.join(OUTPUT_DIR, "ColdLeads-Setup.exe")
    if os.path.isfile(built_exe):
        # Copy to landing page downloads
        dest_exe = os.path.join(DOWNLOADS_DIR, "ColdLeads-Setup.exe")
        shutil.copyfile(built_exe, dest_exe)
        size_mb = os.path.getsize(built_exe) / (1024 * 1024)
        print(f"\n[OK] SUCCESS! Standalone Software Executable Created:")
        print(f"    Path: {built_exe}")
        print(f"    Size: {size_mb:.2f} MB")
    else:
        print("[!] Built executable not found in output directory.")


if __name__ == "__main__":
    build()
