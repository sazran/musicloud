@echo off
setlocal

cd /d "%~dp0"

set "SERVER=shlomia@tubamobile.com"
set "REMOTE_DIR=/home/shlomia/musicloud"

echo Deploying Musicloud to %SERVER%:%REMOTE_DIR%
echo This uploads the static site, data manifest, and downloaded tracks.
echo.

where scp >nul 2>nul
if errorlevel 1 (
  echo scp was not found. Install OpenSSH Client for Windows or use Git Bash.
  exit /b 1
)

where ssh >nul 2>nul
if errorlevel 1 (
  echo ssh was not found. Install OpenSSH Client for Windows or use Git Bash.
  exit /b 1
)

if not exist "data\tracks.json" (
  echo Missing data\tracks.json. Run start_musicloud_import.py first.
  exit /b 1
)

if not exist "tracks" (
  echo Missing tracks folder. Run start_musicloud_import.py first.
  exit /b 1
)

echo Preparing remote folders...
ssh %SERVER% "mkdir -p %REMOTE_DIR% && cd %REMOTE_DIR% && rm -rf data tracks && mkdir -p data tracks"
if errorlevel 1 exit /b 1

echo Uploading site files...
scp index.html styles.css script.js README.md %SERVER%:%REMOTE_DIR%/
if errorlevel 1 exit /b 1

echo Uploading import data...
scp -r data %SERVER%:%REMOTE_DIR%/
if errorlevel 1 exit /b 1

echo Uploading audio tracks. This may take a while...
scp -r tracks %SERVER%:%REMOTE_DIR%/
if errorlevel 1 exit /b 1

echo Fixing remote read permissions for nginx...
ssh %SERVER% "chmod o+x /home/shlomia && chmod -R o+rX %REMOTE_DIR%"
if errorlevel 1 exit /b 1

echo.
echo Done.
echo Open https://tubamobile.com/
