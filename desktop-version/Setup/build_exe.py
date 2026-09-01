"""
PyInstaller Build Script for ColdLeads Desktop v2.0
Compiles the application into a standalone Windows Executable.
"""

import os
import sys
import shutil
import subprocess

SETUP_DIR = os.path.dirname(os.path.abspath(__file__))
DESKTOP_ROOT = os.path.dirname(SETUP_DIR)
WORKSPACE_ROOT = os.path.dirname(DESKTOP_ROOT)
PROJECT_DIR = os.path.join(WORKSPACE_ROOT, "new scraper", "scrape")

FRONTEND_DIR = os.path.join(PROJECT_DIR, "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")
BACKEND_DIR = os.path.join(PROJECT_DIR, "backend")
OUTPUT_DIR = os.path.join(SETUP_DIR, "dist")


def build_frontend():
    print("\n[1/3] Building React Frontend Production Bundle...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    res = subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)
    if res.returncode != 0:
        print("[!] Frontend build failed!")
        sys.exit(1)
    print("[✓] Frontend build completed successfully.")


def build_pyinstaller_exe():
    print("\n[2/3] Building Standalone Python Executable (PyInstaller)...")
    
    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("[*] Installing pyinstaller...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"])

    pyinstaller_args = [
        "pyinstaller",
        "--noconfirm",
        "--onedir",
        "--windowed",
        "--name=ColdLeads",
        f"--add-data={FRONTEND_DIST};frontend/dist",
        f"--add-data={os.path.join(BACKEND_DIR, 'extra_locations.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'locations.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'scraper_api.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'database.py')};.",
        f"--add-data={os.path.join(BACKEND_DIR, 'main.py')};.",
        f"--distpath={OUTPUT_DIR}",
        f"--workpath={os.path.join(SETUP_DIR, 'build')}",
        f"--specpath={SETUP_DIR}",
        os.path.join(SETUP_DIR, "desktop_app.py"),
    ]

    print("[*] Running PyInstaller command...")
    subprocess.run(pyinstaller_args, cwd=SETUP_DIR)
    print("[✓] PyInstaller build complete.")


def main():
    print("=" * 65)
    print("   ColdLeads Windows Executable Builder")
    print("=" * 65)
    build_frontend()
    build_pyinstaller_exe()
    print("\n" + "=" * 65)
    print("[✓] Build Finished! Standalone App location:")
    print(f"    {os.path.join(OUTPUT_DIR, 'ColdLeads', 'ColdLeads.exe')}")
    print("=" * 65)


if __name__ == "__main__":
    main()
