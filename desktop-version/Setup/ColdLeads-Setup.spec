# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/desktop-version/Setup/desktop_app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/frontend/dist', 'frontend/dist'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/extra_locations.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/locations.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/scraper_api.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/database.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/smtp_service.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/auth.py', '.'), ('C:/Users/DELL/Desktop/scrape final/scrape final/new scraper/scrape/backend/main.py', '.')],
    hiddenimports=['uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto', 'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespans', 'uvicorn.lifespans.on'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ColdLeads-Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
