"""
PyInstaller Build Script for ColdLeads Desktop v2.0
Builds a standalone, one-folder/one-file executable for Windows.
"""

import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")
FRONTEND_DIST = os.path.join(FRONTEND_DIR, "dist")
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
OUTPUT_DIR = os.path.join(BASE_DIR, "dist")


def build_frontend():
    print("[1/3] Building React Frontend Production Bundle (dist)...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    res = subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)
    if res.returncode != 0:
        print("[!] Frontend build failed!")
        sys.exit(1)
    print("[✓] Frontend built successfully.")


def build_pyinstaller_exe():
    print("[2/3] Building Standalone Python Executable (PyInstaller)...")
    
    # Check if pyinstaller is available
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
        f"--workpath={os.path.join(BASE_DIR, 'build')}",
        f"--specpath={BASE_DIR}",
        os.path.join(BASE_DIR, "desktop_app.py"),
    ]

    print("[*] Running command:", " ".join(pyinstaller_args))
    subprocess.run(pyinstaller_args, cwd=BASE_DIR)
    print("[✓] PyInstaller build complete.")


def main():
    print("=" * 60)
    print("  ColdLeads Windows Executable Builder")
    print("=" * 60)
    build_frontend()
    build_pyinstaller_exe()
    print("\n[✓] Executable created at:")
    print(f"    {os.path.join(OUTPUT_DIR, 'ColdLeads', 'ColdLeads.exe')}")


if __name__ == "__main__":
    main()
