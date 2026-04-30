param(
  [string]$RedirectUri = "http://127.0.0.1:8787/callback/",
  [string]$ClientId = "",
  [string]$ClientSecret = "",
  [switch]$SaveToUserEnvironment,
  [switch]$RunExport,
  [switch]$EnableDownloads
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Web

function ConvertTo-Base64Url {
  param([byte[]]$Bytes)
  return [Convert]::ToBase64String($Bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function New-PkceVerifier {
  $bytes = New-Object byte[] 32
  $rng = [Security.Cryptography.RandomNumberGenerator]::Create()
  $rng.GetBytes($bytes)
  $rng.Dispose()
  return ConvertTo-Base64Url $bytes
}

function New-PkceChallenge {
  param([string]$Verifier)
  $bytes = [Text.Encoding]::ASCII.GetBytes($Verifier)
  $sha = [Security.Cryptography.SHA256]::Create()
  $hash = $sha.ComputeHash($bytes)
  $sha.Dispose()
  return ConvertTo-Base64Url $hash
}

Write-Host "SoundCloud OAuth helper"
Write-Host "This asks for app credentials from your SoundCloud developer app, not your account password."
Write-Host "Your SoundCloud app must allow this redirect URL:"
Write-Host "  $RedirectUri"
Write-Host ""

if ([string]::IsNullOrWhiteSpace($ClientId)) {
  $ClientId = Read-Host "SoundCloud client_id"
}
if ([string]::IsNullOrWhiteSpace($ClientSecret)) {
  $ClientSecret = Read-Host "SoundCloud client_secret"
}
if ([string]::IsNullOrWhiteSpace($ClientId) -or [string]::IsNullOrWhiteSpace($ClientSecret)) {
  throw "client_id and client_secret are required."
}

$verifier = New-PkceVerifier
$challenge = New-PkceChallenge $verifier
$state = [Guid]::NewGuid().ToString("N")
$authUrl = "https://secure.soundcloud.com/authorize?client_id=$([Uri]::EscapeDataString($ClientId))&redirect_uri=$([Uri]::EscapeDataString($RedirectUri))&response_type=code&code_challenge=$challenge&code_challenge_method=S256&state=$state"

Write-Host ""
Write-Host "Starting temporary local callback listener..."
try {
  $listener = [System.Net.HttpListener]::new()
  $listener.Prefixes.Add($RedirectUri)
  $listener.Start()
} catch {
  Write-Host ""
  Write-Host "Could not start a local listener for $RedirectUri"
  Write-Host "Make sure no other app uses that address, and make sure the redirect URL ends with /"
  throw
}

Write-Host "Opening SoundCloud authorization..."
Write-Host $authUrl
Start-Process $authUrl

Write-Host ""
Write-Host "Waiting for SoundCloud to redirect back..."
$context = $listener.GetContext()
$callbackUrl = $context.Request.Url.AbsoluteUri

$responseHtml = "<!doctype html><html><body style='font-family:sans-serif;background:#10141d;color:#f8fbff;padding:32px'><h1>Musicloud connected</h1><p>You can close this tab and return to PowerShell.</p></body></html>"
$responseBytes = [Text.Encoding]::UTF8.GetBytes($responseHtml)
$context.Response.ContentType = "text/html; charset=utf-8"
$context.Response.ContentLength64 = $responseBytes.Length
$context.Response.OutputStream.Write($responseBytes, 0, $responseBytes.Length)
$context.Response.OutputStream.Close()
$listener.Stop()

$uri = [Uri]$callbackUrl
$query = [System.Web.HttpUtility]::ParseQueryString($uri.Query)
$code = $query["code"]
$returnedState = $query["state"]
if ($returnedState -ne $state) {
  throw "State mismatch. Stop and try again."
}
if ([string]::IsNullOrWhiteSpace($code)) {
  throw "No code found in redirected URL."
}

Write-Host "Exchanging authorization code for access token..."
$body = @{
  grant_type = "authorization_code"
  client_id = $ClientId
  client_secret = $ClientSecret
  redirect_uri = $RedirectUri
  code_verifier = $verifier
  code = $code
}

$token = Invoke-RestMethod -Method Post -Uri "https://secure.soundcloud.com/oauth/token" -ContentType "application/x-www-form-urlencoded" -Body $body -Headers @{
  Accept = "application/json; charset=utf-8"
}

$env:SOUNDCLOUD_ACCESS_TOKEN = $token.access_token
if ($SaveToUserEnvironment) {
  [Environment]::SetEnvironmentVariable("SOUNDCLOUD_ACCESS_TOKEN", $token.access_token, "User")
}

Write-Host ""
Write-Host "Access token received and set for this terminal."
if ($SaveToUserEnvironment) {
  Write-Host "It was also saved to your Windows user environment."
}
Write-Host ""
Write-Host "Now run:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\tools\soundcloud-export.ps1"

if ($RunExport) {
  Write-Host ""
  Write-Host "Running SoundCloud export now..."
  $exportScript = Join-Path $PSScriptRoot "soundcloud-export.ps1"
  if ($EnableDownloads) {
    & $exportScript -EnableDownloads
  } else {
    & $exportScript
  }
}
