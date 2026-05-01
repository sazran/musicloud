import json
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "data" / "tracks.json"
ARTWORK_DIR = ROOT / "artwork"


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value or "untitled"


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Musicloud/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    path.write_bytes(data)


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ARTWORK_DIR.mkdir(exist_ok=True)

    downloaded = 0
    reused = 0
    skipped = 0

    for track in manifest.get("tracks", []):
        artwork = track.get("artwork") or ""
        if not artwork:
            skipped += 1
            continue
        if artwork.startswith("artwork/"):
            reused += 1
            continue

        track_id = track.get("soundcloudId") or safe_name(track.get("title", "track"))
        filename = f"{safe_name(track.get('title', 'track'))}-{track_id}.jpg"
        target = ARTWORK_DIR / filename

        if target.exists() and target.stat().st_size > 0:
            reused += 1
        else:
            print(f"Downloading artwork for {track.get('title')}: {artwork}")
            download(artwork, target)
            downloaded += 1

        track["artwork"] = f"artwork/{filename}"

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"downloaded={downloaded}")
    print(f"reused={reused}")
    print(f"skipped_no_artwork={skipped}")
    print(f"manifest={MANIFEST}")


if __name__ == "__main__":
    main()
