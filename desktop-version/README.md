# ColdLeads Desktop Edition v2.0 🚀
> Standalone B2B Lead Scraper & Executive Decision Maker Discovery Platform for Windows.

---

## 📂 Folder Structure Overview

```
desktop-version/
├── Setup/                          # Desktop Application & Installer Builder
│   ├── desktop_app.py              # Native Windows Desktop Entrypoint (FastAPI + Embedded UI)
│   ├── build_exe.py                # Standalone PyInstaller Executable Builder
│   ├── installer_script.iss        # Inno Setup Script for "ColdLeads-Setup.exe"
│   ├── build_installer.bat         # 1-Click Windows Compiler Batch Script
│   ├── ColdLeads_Launcher.bat      # 1-Click Portable App Launcher
│   └── LICENSE.txt                 # Software License Agreement
│
├── Landing_Page/                   # SaaS Landing Page & Download Portal
│   ├── index.html                  # Dark Glassmorphism Landing Page with Download Button
│   ├── styles.css                  # Modern UI Stylesheet & Animations
│   └── app.js                      # Live Interactive Lead Simulator & FAQ Accordion
│
└── README.md                       # Documentation & Quickstart
```

---

## ⚡ How to Build & Use

### 1. Test Running Locally (1-Click Portable Mode)
To launch the desktop application right now without installing:
1. Open `Setup/` folder.
2. Double-click `ColdLeads_Launcher.bat` (or run `python desktop_app.py`).
3. The embedded backend will boot up and open a native desktop application window.

### 2. Build the Standalone Setup File (`ColdLeads-Setup.exe`)
1. Open `Setup/` folder.
2. Double click **`build_installer.bat`** (or run `python build_exe.py`).
3. It will:
   - Compile the React frontend production bundle (`dist`).
   - Bundle all Python dependencies and headless Chrome drivers into a standalone executable.
   - Run Inno Setup compiler to create `Output/ColdLeads-Setup.exe`.

### 3. Open the Download Landing Page
1. Open `Landing_Page/` folder.
2. Double-click **`index.html`** in your browser.
3. You can host this folder on Vercel, Netlify, or any web server to let your clients download `ColdLeads-Setup.exe`.

---

## 🌟 Key Features Included in this Release

- 👔 **Decision Maker Extraction:** Scrapes CEO, Founder, Owner, GM, Marketing Director names and verified emails.
- 🌍 **55+ Countries & 50,000+ Cities:** Global coverage.
- ⚡ **Multi-Threaded Headless Selenium:** High-speed parallel scraping.
- 🛡️ **100% Client-Side Privacy:** Local SQLite storage; no external cloud dependency.
- 📊 **Multi-Format Exports:** CSV, Excel (.xlsx), and JSON.
