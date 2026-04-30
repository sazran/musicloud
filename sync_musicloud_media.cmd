@echo off
cd /d "%~dp0"
py sync_musicloud_media.py %*
if errorlevel 1 pause
