@echo off
title ColdLeads Backend (Port 8000)
cd /d "%~dp0backend"
echo Starting ColdLeads Backend on http://localhost:8000
echo.
python -m uvicorn main:app --reload --port 8000
pause
