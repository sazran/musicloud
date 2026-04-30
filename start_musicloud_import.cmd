@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py start_musicloud_import.py
) else (
  python start_musicloud_import.py
)
pause
