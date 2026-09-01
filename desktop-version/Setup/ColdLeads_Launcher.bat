@echo off
title ColdLeads B2B Lead Scraper
color 0a

echo ===================================================================
echo             Launching ColdLeads Desktop Application v2.0
echo ===================================================================
echo.
echo [*] Starting embedded backend & desktop application...
python desktop_app.py

if %ERRORLEVEL% NEQ 0 (
    echo [!] Application exited with error code %ERRORLEVEL%
    pause
)
