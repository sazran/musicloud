import base64
import hashlib
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import argparse
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SITE_PORT = 5173
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8787
CALLBACK_PATH = "/callback/"
API_BASE = "https://api.soundcloud.com"


def say(title):
    print(f"\n== {title} ==")


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def safe_name(name):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", name).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned or "untitled"


def request_json(url, token=None, method="GET", data=None):
    headers = {"Accept": "application/json; charset=utf-8"}
    body = None
    if token:
        headers["Authorization"] = f"OAuth {token}"
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def download_file(url, path):
    with urllib.request.urlopen(url, timeout=120) as response:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)


def is_site_running(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def start_site():
    site_url = f"http://127.0.0.1:{SITE_PORT}/"
    say("Starting Musicloud")
    if is_site_running(site_url):
        print(f"Musicloud is already running at {site_url}")
        return site_url

    subprocess.Popen(
        [sys.executable, "-m", "http.server", str(SITE_PORT), "--bind", "127.0.0.1"],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    time.sleep(2)
    if not is_site_running(site_url):
        raise RuntimeError(f"I tried to start Musicloud at {site_url}, but it did not respond.")
    print(f"Musicloud is running at {site_url}")
    return site_url


class CallbackHandler(SimpleHTTPRequestHandler):
    callback_url = None
    expected_path = CALLBACK_PATH

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path != self.expected_path.rstrip("/"):
            if urllib.parse.urlparse(self.path).path != self.expected_path:
                self.send_response(404)
                self.end_headers()
                return

        CallbackHandler.callback_url = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{self.path}"
        html = (
            "<!doctype html><html><body style='font-family:sans-serif;"
            "background:#10141d;color:#f8fbff;padding:32px'>"
            "<h1>Musicloud connected</h1>"
            "<p>You can close this tab and return to the command window.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)


def get_oauth_token(client_id, client_secret, redirect_uri):
    verifier = b64url(secrets.token_bytes(32))
    challenge = b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    state = secrets.token_urlsafe(18)
    params = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    auth_url = f"https://secure.soundcloud.com/authorize?{params}"

    say("OAuth")
    print("I will open SoundCloud. Log in there and approve the app.")
    callback_url = None
    parsed_redirect = urllib.parse.urlparse(redirect_uri)
    use_local_listener = parsed_redirect.hostname in {"127.0.0.1", "localhost"} and parsed_redirect.port == CALLBACK_PORT

    server = None
    if use_local_listener:
        server = ThreadingHTTPServer((CALLBACK_HOST, CALLBACK_PORT), CallbackHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    webbrowser.open(auth_url)
    if use_local_listener:
        print("Waiting for SoundCloud to redirect back to this computer...")
        for _ in range(180):
            if CallbackHandler.callback_url:
                callback_url = CallbackHandler.callback_url
                break
            time.sleep(1)
        server.shutdown()

        if not callback_url:
            print("")
            print("I did not receive the local callback.")
            print("If your browser is sitting on a SoundCloud redirect URL, paste the full URL here.")
            pasted = input("Redirected URL, or Enter to stop: ").strip()
            if pasted:
                callback_url = pasted
            else:
                raise RuntimeError("Timed out waiting for SoundCloud OAuth callback.")
    else:
        print("After approval, SoundCloud will redirect to your configured public URL.")
        print("Paste the full redirected browser URL here. It should contain code=... and state=...")
        callback_url = input("Redirected URL: ").strip()

    parsed = urllib.parse.urlparse(callback_url)
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("state", [""])[0] != state:
        raise RuntimeError("OAuth state mismatch. Stop and try again.")
    code = query.get("code", [""])[0]
    if not code:
        raise RuntimeError("No OAuth code was returned by SoundCloud.")

    say("Token")
    print("Exchanging authorization code for access token...")
    token = request_json(
        "https://secure.soundcloud.com/oauth/token",
        method="POST",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "code": code,
        },
    )
    access_token = token.get("access_token")
    if not access_token:
        raise RuntimeError("SoundCloud did not return an access token.")
    return access_token


def fetch_tracks(token):
    tracks = []
    next_url = f"{API_BASE}/me/tracks?limit=50&linked_partitioning=1"
    while next_url:
        page = request_json(next_url, token=token)
        if isinstance(page, dict) and "collection" in page:
            tracks.extend(page.get("collection") or [])
            next_url = page.get("next_href")
        elif isinstance(page, list):
            tracks.extend(page)
            next_url = None
        else:
            next_url = None
    return tracks


def enable_download(track, token):
    return request_json(
        f"{API_BASE}/tracks/{track['id']}",
        token=token,
        method="PUT",
        data={"track[downloadable]": "true"},
    )


def extension_for(track, redirect_url):
    original = track.get("original_format")
    if original:
        return "." + str(original).lower().lstrip(".")
    guessed = mimetypes.guess_extension(urllib.request.urlopen(redirect_url, timeout=30).headers.get_content_type())
    return guessed or ".audio"


def export_tracks(token, enable_downloads=False):
    say("Reading SoundCloud")
    me = request_json(f"{API_BASE}/me", token=token)
    username = me.get("username") or "soundcloud"
    print(f"Account: {username}")
    tracks = fetch_tracks(token)
    print(f"Found {len(tracks)} tracks.")

    tracks_dir = ROOT / "tracks"
    data_dir = ROOT / "data"
    tracks_dir.mkdir(exist_ok=True)
    data_dir.mkdir(exist_ok=True)

    manifest_tracks = []
    skipped_tracks = []
    downloaded = 0
    skipped = 0

    for track in tracks:
        title = track.get("title") or f"Untitled {track.get('id')}"
        artist = ((track.get("user") or {}).get("username")) or username
        download_url = track.get("download_url")

        if (not track.get("downloadable") or not download_url) and enable_downloads:
            print(f"Trying to enable official downloads for '{title}'...")
            try:
                track = enable_download(track, token)
                download_url = track.get("download_url")
            except Exception as exc:
                print(f"Could not update '{title}': {exc}")

        if not track.get("downloadable") or not download_url:
            print(f"Skipping '{title}' because SoundCloud exposed no official download URL.")
            skipped += 1
            skipped_tracks.append(
                {
                    "title": title,
                    "artist": artist,
                    "id": track.get("id"),
                    "url": track.get("permalink_url"),
                    "downloadable": bool(track.get("downloadable")),
                    "hasDownloadUrl": bool(download_url),
                    "reason": "No official download_url exposed by SoundCloud API",
                }
            )
            continue

        print(f"Downloading '{title}'...")
        info = request_json(download_url, token=token)
        redirect_url = info.get("redirectUri")
        if not redirect_url:
            skipped += 1
            skipped_tracks.append(
                {
                    "title": title,
                    "artist": artist,
                    "id": track.get("id"),
                    "url": track.get("permalink_url"),
                    "downloadable": bool(track.get("downloadable")),
                    "hasDownloadUrl": True,
                    "reason": "Download endpoint returned no redirectUri",
                }
            )
            continue

        ext = "." + str(track.get("original_format") or "audio").lower().lstrip(".")
        filename = f"{safe_name(title)}-{track.get('id')}{ext}"
        file_path = tracks_dir / filename
        download_file(redirect_url, file_path)

        artwork = track.get("artwork_url") or ""
        if artwork:
            artwork = re.sub(r"large\.jpg$", "t500x500.jpg", artwork)
        duration = round((track.get("duration") or 0) / 1000)
        manifest_tracks.append(
            {
                "title": title,
                "artist": artist,
                "genre": (track.get("genre") or "cloudcast"),
                "duration": duration,
                "plays": track.get("playback_count") or 0,
                "comments": track.get("comment_count") or 0,
                "likes": track.get("likes_count") or 0,
                "src": f"tracks/{filename}",
                "artwork": artwork,
                "soundcloudUrl": track.get("permalink_url"),
                "soundcloudId": track.get("id"),
            }
        )
        downloaded += 1

    exported_at = datetime.now(timezone.utc).isoformat()
    (data_dir / "tracks.json").write_text(
        json.dumps(
            {
                "source": "soundcloud",
                "exportedAt": exported_at,
                "account": username,
                "downloaded": downloaded,
                "skipped": skipped,
                "tracks": manifest_tracks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (data_dir / "skipped-tracks.json").write_text(
        json.dumps(
            {
                "source": "soundcloud",
                "exportedAt": exported_at,
                "account": username,
                "skipped": skipped,
                "tracks": skipped_tracks,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return downloaded, skipped


def parse_args():
    parser = argparse.ArgumentParser(description="Interactive Musicloud SoundCloud importer")
    parser.add_argument(
        "--redirect-uri",
        default=f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}",
        help="OAuth redirect URI registered in your SoundCloud app",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    os.chdir(ROOT)
    print("")
    print("Musicloud SoundCloud importer")
    print("I will ask only for SoundCloud app values I cannot derive.")
    print("I will not ask for your SoundCloud password.")

    site_url = start_site()
    webbrowser.open(site_url)

    say("SoundCloud app")
    print("Create/open your SoundCloud developer app.")
    print("Add this exact redirect URL:")
    print(f"  {args.redirect_uri}")
    print("")
    webbrowser.open("https://soundcloud.com/you/apps")
    input("Press Enter after the app has that redirect URL...")

    say("Credentials")
    client_id = input("client_id: ").strip()
    client_secret = input("client_secret: ").strip()
    if not client_id or not client_secret:
        raise RuntimeError("client_id and client_secret are required.")

    token = get_oauth_token(client_id, client_secret, args.redirect_uri)
    downloaded, skipped = export_tracks(token, enable_downloads=False)

    if downloaded == 0 and skipped > 0:
        say("Downloads blocked")
        print("SoundCloud found your tracks but exposed zero official download links.")
        print("I can try one official fix: enable downloads on your own tracks, then retry.")
        print("This may make those tracks downloadable on SoundCloud too.")
        answer = input("Type YES to enable downloads and retry: ").strip()
        if answer == "YES":
            downloaded, skipped = export_tracks(token, enable_downloads=True)
        else:
            print("No permissions changed.")

    say("Finished")
    print(f"Downloaded: {downloaded}")
    print(f"Skipped: {skipped}")
    print("Manifest: data/tracks.json")
    print("Skipped report: data/skipped-tracks.json")
    print(f"Refresh Musicloud: {site_url}")
    webbrowser.open(site_url)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
    except urllib.error.HTTPError as exc:
        print(f"\nHTTP error {exc.code}: {exc.reason}")
        try:
            print(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            pass
        sys.exit(1)
    except Exception as exc:
        print(f"\nError: {exc}")
        sys.exit(1)
