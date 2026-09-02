"""
Professional Inno Setup Builder for ColdLeads v2.0
Builds a clean, non-flagged Windows Setup Wizard (ColdLeads-Setup.exe).
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
DIST_DIR = os.path.join(SETUP_DIR, "dist")
OUTPUT_DIR = os.path.join(SETUP_DIR, "Output")
DOWNLOADS_DIR = os.path.join(DESKTOP_DIR, "Landing_Page", "downloads")

ISCC_PATHS = [
    r"C:\Users\DELL\AppData\Local\Programs\Inno Setup 6\ISCC.exe",
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
]


def find_iscc():
    for p in ISCC_PATHS:
        if os.path.isfile(p):
            return p
    return "ISCC.exe"


def build():
    print("=" * 70)
    print("   Building Official Inno Setup Installer: ColdLeads-Setup.exe")
    print("=" * 70)

    # 1. Compile Frontend
    print("\n[1/4] Compiling React Frontend (Vite)...")
    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    res = subprocess.run([npm_cmd, "run", "build"], cwd=FRONTEND_DIR)
    if res.returncode != 0:
        print("[!] Frontend compilation failed!")
        sys.exit(1)
    print("[OK] Frontend compiled successfully.")

    # 2. Build Directory-Mode Binary with PyInstaller (--onedir)
    print("\n[2/4] Building Clean Binary Bundle (--onedir mode)...")
    pyinstaller_cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name=ColdLeads",
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
        "--hidden-import=email",
        "--hidden-import=email.mime",
        "--hidden-import=email.mime.multipart",
        "--hidden-import=email.mime.text",
        "--hidden-import=email.mime.base",
        "--hidden-import=email.mime.application",
        "--hidden-import=email.mime.image",
        "--hidden-import=email.mime.audio",
        "--hidden-import=email.header",
        "--hidden-import=email.utils",
        "--hidden-import=email.encoders",
        "--hidden-import=email.parser",
        "--hidden-import=email.generator",
        "--hidden-import=email.policy",
        "--hidden-import=smtplib",
        "--hidden-import=ssl",
        "--collect-all=email",
        "--collect-all=pandas",
        "--collect-all=openpyxl",
        "--collect-all=fastapi",
        "--collect-all=uvicorn",
        "--collect-all=starlette",
        "--collect-all=pydantic",
        "--collect-all=httpx",
        "--collect-all=selenium",
        "--collect-all=jose",
        "--collect-all=passlib",
        "--collect-all=bcrypt",
        "--exclude-module=torch",
        "--exclude-module=transformers",
        "--exclude-module=scipy",
        "--exclude-module=sklearn",
        "--exclude-module=matplotlib",
        "--exclude-module=IPython",
        "--exclude-module=pytest",
        "--exclude-module=django",
        "--exclude-module=jupyter",
        f"--distpath={DIST_DIR}",
        f"--workpath={os.path.join(SETUP_DIR, 'build')}",
        f"--specpath={SETUP_DIR}",
        os.path.join(SETUP_DIR, "desktop_app.py"),
    ]

    print("[*] Running PyInstaller onedir...")
    res2 = subprocess.run(pyinstaller_cmd, cwd=SETUP_DIR)
    if res2.returncode != 0:
        print("[!] PyInstaller onedir compilation failed!")
        sys.exit(1)
    print("[OK] Directory bundle created in dist/ColdLeads.")

    # 3. Create Inno Setup Script
    print("\n[3/4] Generating Inno Setup Installer Script...")
    iss_content = f"""; Inno Setup Script for ColdLeads B2B Lead Scraper & Outreach Engine
#define MyAppName "ColdLeads"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "ColdLeads Software"
#define MyAppURL "https://scraper-eight-virid.vercel.app"
#define MyAppExeName "ColdLeads.exe"

[Setup]
AppId={{{{A7E294B1-D62F-46BE-99A4-F2D72605E412}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
AppPublisherURL={{#MyAppURL}}
AppSupportURL={{#MyAppURL}}
AppUpdatesURL={{#MyAppURL}}
DefaultDirName={{autopf}}\\{{#MyAppName}}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=ColdLeads-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{{cm:CreateDesktopIcon}}"; GroupDescription: "{{cm:AdditionalIcons}}"

[Files]
Source: "dist\\ColdLeads\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{autoprograms}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "{{cm:LaunchProgram,{{#StringChange(MyAppName, '&', '&&')}}}}"; Flags: nowait postinstall skipifsilent
"""
    iss_file = os.path.join(SETUP_DIR, "installer_script.iss")
    with open(iss_file, "w", encoding="utf-8") as f:
        f.write(iss_content)
    print("[OK] installer_script.iss generated.")

    # 4. Compile with Inno Setup Compiler (ISCC.exe)
    print("\n[4/4] Compiling Windows Setup Wizard (.exe) with Inno Setup...")
    iscc = find_iscc()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)

    res3 = subprocess.run([iscc, iss_file], cwd=SETUP_DIR)
    if res3.returncode != 0:
        print(f"[!] Inno Setup compilation failed! Return code: {res3.returncode}")
        sys.exit(1)

    built_installer = os.path.join(OUTPUT_DIR, "ColdLeads-Setup.exe")
    if os.path.isfile(built_installer):
        dest_installer = os.path.join(DOWNLOADS_DIR, "ColdLeads-Setup.exe")
        shutil.copyfile(built_installer, dest_installer)
        size_mb = os.path.getsize(built_installer) / (1024 * 1024)
        print(f"\n======================================================================")
        print(f" [OK] SUCCESS! Official Inno Setup Installer Created!")
        print(f"    Path: {built_installer}")
        print(f"    Size: {size_mb:.2f} MB")
        print(f"======================================================================")
    else:
        print("[!] Installer not found in Output directory.")


if __name__ == "__main__":
    build()
