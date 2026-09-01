@echo off
title ColdLeads Frontend (Port 3000)
cd /d "%~dp0frontend"
echo Starting ColdLeads React Frontend on http://localhost:3000
echo.
npm run dev
pause
