param(
  [string]$OutputDir = "tracks",
  [string]$DataDir = "data",
  [int]$PageSize = 50,
  [switch]$EnableDownloads
)

$ErrorActionPreference = "Stop"

function Get-RequiredEnv {
  param([string]$Name)

  $value = [Environment]::GetEnvironmentVariable($Name, "Process")
  if ([string]::IsNullOrWhiteSpace($value)) {
    $value = [Environment]::GetEnvironmentVariable($Name, "User")
  }
  if ([string]::IsNullOrWhiteSpace($value)) {
    Write-Host ""
    Write-Host "Missing $Name."
    Write-Host "This script does not ask for your SoundCloud password."
    Write-Host "Paste an official OAuth access token into this terminal first:"
    Write-Host ""
    Write-Host '  $env:SOUNDCLOUD_ACCESS_TOKEN = "paste_your_oauth_access_token_here"'
    Write-Host ""
    Write-Host "Then run:"
    Write-Host ""
    Write-Host "  powershell -ExecutionPolicy Bypass -File .\tools\soundcloud-export.ps1"
    Write-Host ""
    Write-Host "More details: tools\soundcloud-import.md"
    exit 2
  }
  return $value
}

function ConvertTo-SafeFileName {
  param([string]$Name)

  $invalid = [IO.Path]::GetInvalidFileNameChars() -join ""
  $regex = "[{0}]" -f [Regex]::Escape($invalid)
  $safe = ($Name -replace $regex, "-").Trim()
  $safe = $safe -replace "\s+", " "
  if ([string]::IsNullOrWhiteSpace($safe)) {
    return "untitled"
  }
  return $safe
}

function Invoke-SoundCloudJson {
  param(
    [string]$Uri,
    [string]$Token
  )

  Invoke-RestMethod -Uri $Uri -Headers @{
    Authorization = "OAuth $Token"
    Accept = "application/json; charset=utf-8"
  }
}

function Update-TrackDownloadPermission {
  param(
    [object]$Track,
    [string]$Token
  )

  $uri = "https://api.soundcloud.com/tracks/$($Track.id)"
  $body = @{
    "track[downloadable]" = "true"
  }

  Invoke-RestMethod -Method Put -Uri $uri -Headers @{
    Authorization = "OAuth $Token"
    Accept = "application/json; charset=utf-8"
  } -ContentType "application/x-www-form-urlencoded" -Body $body
}

$accessToken = Get-RequiredEnv "SOUNDCLOUD_ACCESS_TOKEN"
$apiBase = "https://api.soundcloud.com"
$outputPath = Join-Path (Resolve-Path ".").Path $OutputDir
$dataPath = Join-Path (Resolve-Path ".").Path $DataDir
$manifestPath = Join-Path $dataPath "tracks.json"

New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
New-Item -ItemType Directory -Force -Path $dataPath | Out-Null

Write-Host "Fetching your SoundCloud profile..."
$me = Invoke-SoundCloudJson -Uri "$apiBase/me" -Token $accessToken

Write-Host "Fetching uploaded tracks for $($me.username)..."
$tracks = @()
$nextUrl = "$apiBase/me/tracks?limit=$PageSize&linked_partitioning=1"

while ($nextUrl) {
  $page = Invoke-SoundCloudJson -Uri $nextUrl -Token $accessToken
  if ($page.collection) {
    $tracks += $page.collection
    $nextUrl = $page.next_href
  } else {
    $tracks += $page
    $nextUrl = $null
  }
}

Write-Host "Found $($tracks.Count) tracks."

$manifestTracks = @()
$downloaded = 0
$skipped = 0
$skippedTracks = @()

foreach ($track in $tracks) {
  $title = if ($track.title) { $track.title } else { "Untitled $($track.id)" }
  $artist = if ($track.user.username) { $track.user.username } elseif ($me.username) { $me.username } else { "SoundCloud" }
  $downloadUrl = $track.download_url

  if (-not $track.downloadable -or [string]::IsNullOrWhiteSpace($downloadUrl)) {
    if ($EnableDownloads) {
      Write-Host "Trying to enable official downloads for '$title'..."
      try {
        $updatedTrack = Update-TrackDownloadPermission -Track $track -Token $accessToken
        $track = $updatedTrack
        $downloadUrl = $track.download_url
      } catch {
        Write-Host "Could not update '$title': $($_.Exception.Message)"
      }
    }

    if (-not $track.downloadable -or [string]::IsNullOrWhiteSpace($downloadUrl)) {
      Write-Host "Skipping '$title' because SoundCloud did not expose an official download URL."
      $skippedTracks += [PSCustomObject]@{
        title = $title
        artist = $artist
        id = $track.id
        url = $track.permalink_url
        downloadable = [bool]$track.downloadable
        hasDownloadUrl = -not [string]::IsNullOrWhiteSpace($downloadUrl)
        reason = "No official download_url exposed by SoundCloud API"
      }
      $skipped++
      continue
    }
  }

  Write-Host "Preparing download for '$title'..."
  $downloadInfo = Invoke-SoundCloudJson -Uri $downloadUrl -Token $accessToken
  $redirectUri = $downloadInfo.redirectUri
  if ([string]::IsNullOrWhiteSpace($redirectUri)) {
    Write-Host "Skipping '$title' because the API did not return a redirectUri."
    $skipped++
    continue
  }

  $safeTitle = ConvertTo-SafeFileName $title
  $extension = ".audio"
  if ($track.original_format) {
    $extension = "." + ($track.original_format.ToString().TrimStart(".").ToLowerInvariant())
  } elseif ($track.download_filename -match "\.[A-Za-z0-9]{2,5}$") {
    $extension = [IO.Path]::GetExtension($track.download_filename)
  }

  $fileName = "$safeTitle-$($track.id)$extension"
  $filePath = Join-Path $outputPath $fileName
  Invoke-WebRequest -Uri $redirectUri -OutFile $filePath

  $durationSeconds = if ($track.duration) { [Math]::Round($track.duration / 1000) } else { 0 }
  $genre = if ($track.genre) { $track.genre } else { "cloudcast" }
  $artwork = $track.artwork_url
  if ($artwork) {
    $artwork = $artwork -replace "large\.jpg$", "t500x500.jpg"
  }

  $manifestTracks += [PSCustomObject]@{
    title = $title
    artist = $artist
    genre = $genre
    duration = $durationSeconds
    plays = if ($track.playback_count) { $track.playback_count } else { 0 }
    comments = if ($track.comment_count) { $track.comment_count } else { 0 }
    likes = if ($track.likes_count) { $track.likes_count } else { 0 }
    src = "$OutputDir/$fileName"
    artwork = $artwork
    soundcloudUrl = $track.permalink_url
    soundcloudId = $track.id
  }

  $downloaded++
}

$manifest = [PSCustomObject]@{
  source = "soundcloud"
  exportedAt = (Get-Date).ToUniversalTime().ToString("o")
  account = $me.username
  downloaded = $downloaded
  skipped = $skipped
  tracks = $manifestTracks
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

$skippedReportPath = Join-Path $dataPath "skipped-tracks.json"
$skippedReport = [PSCustomObject]@{
  source = "soundcloud"
  exportedAt = (Get-Date).ToUniversalTime().ToString("o")
  account = $me.username
  skipped = $skipped
  tracks = $skippedTracks
}
$skippedReport | ConvertTo-Json -Depth 8 | Set-Content -Path $skippedReportPath -Encoding UTF8

Write-Host ""
Write-Host "Done."
Write-Host "Downloaded: $downloaded"
Write-Host "Skipped: $skipped"
Write-Host "Manifest: $manifestPath"
Write-Host "Skipped report: $skippedReportPath"
