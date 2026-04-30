param(
  [string]$TracksDir = "tracks",
  [string]$DataDir = "data",
  [string]$Artist = "Sazran"
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path ".").Path
$tracksPath = Join-Path $root $TracksDir
$dataPath = Join-Path $root $DataDir
$manifestPath = Join-Path $dataPath "tracks.json"

if (-not (Test-Path $tracksPath)) {
  throw "Missing $TracksDir folder. Create it and place audio files inside."
}

New-Item -ItemType Directory -Force -Path $dataPath | Out-Null

$extensions = @(".wav", ".wave", ".aif", ".aiff", ".flac", ".mp3", ".aac", ".m4a", ".ogg")
$files = Get-ChildItem -Path $tracksPath -File | Where-Object { $extensions -contains $_.Extension.ToLowerInvariant() }

$tracks = @()
$index = 0
foreach ($file in $files) {
  $index++
  $title = [IO.Path]::GetFileNameWithoutExtension($file.Name) -replace "[-_]+", " "
  $tracks += [PSCustomObject]@{
    title = (Get-Culture).TextInfo.ToTitleCase($title)
    artist = $Artist
    genre = "cloudcast"
    duration = 0
    plays = 0
    comments = 0
    likes = 0
    src = "$TracksDir/$($file.Name)"
    artwork = ""
    soundcloudUrl = ""
    soundcloudId = ""
  }
}

$manifest = [PSCustomObject]@{
  source = "local"
  exportedAt = (Get-Date).ToUniversalTime().ToString("o")
  account = $Artist
  downloaded = $tracks.Count
  skipped = 0
  tracks = $tracks
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host "Wrote $manifestPath with $($tracks.Count) tracks."
