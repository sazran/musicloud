@echo off
setlocal

cd /d "%~dp0"

set "SERVER=shlomia@tubamobile.com"
set "REMOTE_DIR=/home/shlomia/musicloud"

echo This script is deprecated.
echo Site/code files should be deployed through git.
echo Generated media should be synced with:
echo.
echo   sync_musicloud_media.cmd
echo.
echo Safety policy: see AGENTS.md
echo.
call sync_musicloud_media.cmd %*
