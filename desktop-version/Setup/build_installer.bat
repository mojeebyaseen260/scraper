@echo off
title Building ColdLeads-Setup.exe Installer
color 0b

echo ===================================================================
echo             ColdLeads Setup Installer Builder v2.0
echo ===================================================================
echo.

echo [1/3] Running Python Build Script...
python build_exe.py

if %ERRORLEVEL% NEQ 0 (
    echo [!] Build failed with error code %ERRORLEVEL%
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Checking for Inno Setup Compiler (ISCC.exe)...
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"

if exist "%ISCC%" (
    echo [*] Found Inno Setup at: "%ISCC%"
    echo [3/3] Compiling installer_script.iss into ColdLeads-Setup.exe...
    "%ISCC%" installer_script.iss
    echo.
    echo ===================================================================
    echo [✓] SUCCESS! Setup File generated at: Output\ColdLeads-Setup.exe
    echo ===================================================================
) else (
    echo [!] Inno Setup compiler (ISCC.exe) not found in default path.
    echo [*] You can open installer_script.iss in Inno Setup to compile ColdLeads-Setup.exe
    echo [*] Or use the standalone app directly in: dist\ColdLeads\ColdLeads.exe
)

echo.
pause
