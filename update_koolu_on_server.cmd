@echo off
cd /d "%~dp0"
py update_koolu_on_server.py %*
if errorlevel 1 pause
