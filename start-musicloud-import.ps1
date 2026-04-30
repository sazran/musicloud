param(
  [int]$SitePort = 5173,
  [string]$OAuthRedirectUri = "http://127.0.0.1:8787/callback/"
)

$ErrorActionPreference = "Stop"

function Write-Step {
  param([string]$Text)
  Write-Host ""
  Write-Host "== $Text ==" -ForegroundColor Cyan
}

function Find-Python {
  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return $python.Source }
  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) { return $py.Source }
  return $null
}

function Test-Url {
  param([string]$Url)
  try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
    return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500)
  } catch {
    return $false
  }
}

$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "Musicloud SoundCloud importer" -ForegroundColor Green
Write-Host "I will guide OAuth, download official originals, and refresh Musicloud."
Write-Host "I will not ask for your SoundCloud password."

$siteUrl = "http://127.0.0.1:$SitePort/"

Write-Step "Starting Musicloud"
if (Test-Url $siteUrl) {
  Write-Host "Musicloud is already running at $siteUrl"
} else {
  $python = Find-Python
  if (-not $python) {
    throw "Python was not found. Start any static web server in this folder, then rerun this script."
  }

  Start-Process -FilePath $python -ArgumentList @("-m", "http.server", "$SitePort", "--bind", "127.0.0.1") -WorkingDirectory $root -WindowStyle Hidden
  Start-Sleep -Seconds 2
  if (-not (Test-Url $siteUrl)) {
    throw "I tried to start Musicloud at $siteUrl, but it did not respond."
  }
  Write-Host "Musicloud is running at $siteUrl"
}
Start-Process $siteUrl

Write-Step "SoundCloud app setup"
Write-Host "A SoundCloud developer app is required for official OAuth."
Write-Host "In the app settings, add this exact redirect URL:"
Write-Host ""
Write-Host "  $OAuthRedirectUri" -ForegroundColor Yellow
Write-Host ""
Write-Host "I am opening the SoundCloud apps page now."
Start-Process "https://soundcloud.com/you/apps"
Write-Host ""
Read-Host "Create/open your app, add the redirect URL, then press Enter here"

Write-Step "App credentials"
Write-Host "Paste values from your SoundCloud app. These are not your SoundCloud login password."
$clientId = Read-Host "client_id"
$clientSecret = Read-Host "client_secret"
if ([string]::IsNullOrWhiteSpace($clientId) -or [string]::IsNullOrWhiteSpace($clientSecret)) {
  throw "client_id and client_secret are required."
}

Write-Step "OAuth and download"
Write-Host "I will open SoundCloud authorization. Approve it in the browser."
Write-Host "After approval, the local callback page will say Musicloud connected."

& (Join-Path $root "tools\soundcloud-auth.ps1") `
  -RedirectUri $OAuthRedirectUri `
  -ClientId $clientId `
  -ClientSecret $clientSecret `
  -RunExport

$manifestPath = Join-Path $root "data\tracks.json"
$downloaded = 0
$skipped = 0
if (Test-Path $manifestPath) {
  $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
  $downloaded = [int]$manifest.downloaded
  $skipped = [int]$manifest.skipped
}

if ($downloaded -eq 0 -and $skipped -gt 0) {
  Write-Step "Downloads were blocked"
  Write-Host "SoundCloud found your tracks but did not expose official download links."
  Write-Host "I can try one official fix: enable downloads on your own SoundCloud tracks, then retry."
  Write-Host "This may make those tracks downloadable on SoundCloud too."
  Write-Host ""
  $answer = Read-Host "Type YES to enable downloads for your tracks and retry"
  if ($answer -eq "YES") {
    & (Join-Path $root "tools\soundcloud-export.ps1") -EnableDownloads
  } else {
    Write-Host "Okay, I will not change your SoundCloud track permissions."
  }
}

Write-Step "Finished"
if (Test-Path (Join-Path $root "data\tracks.json")) {
  Write-Host "Your Musicloud manifest exists: data\tracks.json"
}
if (Test-Path (Join-Path $root "tracks")) {
  $count = (Get-ChildItem -Path (Join-Path $root "tracks") -File -ErrorAction SilentlyContinue | Measure-Object).Count
  Write-Host "Audio files in tracks\: $count"
}
Write-Host ""
Write-Host "Refresh Musicloud:"
Write-Host "  $siteUrl" -ForegroundColor Yellow
Start-Process $siteUrl
