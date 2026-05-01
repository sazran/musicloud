import argparse
import hashlib
import json
import mimetypes
import os
import secrets
import shutil
import wave
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, Response, jsonify, redirect, request, send_file, send_from_directory
from werkzeug.exceptions import BadRequest, Forbidden, NotFound
from werkzeug.utils import secure_filename


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
TRACKS_DIR = ROOT / "tracks"
ARTWORK_DIR = ROOT / "artwork"
MANIFEST_PATH = DATA_DIR / "tracks.json"

APP_NAME = "Musicloud"
DEFAULT_ARTIST = "sazran"
MAX_UPLOAD_BYTES = int(os.environ.get("MUSICLOUD_MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".wave", ".aif", ".aiff", ".flac", ".mp3", ".aac", ".m4a", ".ogg"}
ALLOWED_ARTWORK_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    TRACKS_DIR.mkdir(exist_ok=True)
    ARTWORK_DIR.mkdir(exist_ok=True)


def read_json(path, fallback):
    if not path.exists():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BadRequest(f"Could not parse {path.relative_to(ROOT)}: {exc}") from exc


def write_json_atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def load_manifest():
    manifest = read_json(
        MANIFEST_PATH,
        {
            "source": "musicloud",
            "exportedAt": utc_now(),
            "account": DEFAULT_ARTIST,
            "downloaded": 0,
            "skipped": 0,
            "tracks": [],
        },
    )
    tracks = manifest.get("tracks")
    if not isinstance(tracks, list):
        raise BadRequest("Manifest field 'tracks' must be an array.")
    return manifest


def save_manifest(manifest):
    manifest["exportedAt"] = utc_now()
    manifest["downloaded"] = len([track for track in manifest.get("tracks", []) if not track.get("hidden")])
    manifest["skipped"] = int(manifest.get("skipped") or 0)
    write_json_atomic(MANIFEST_PATH, manifest)


def safe_stem(value):
    cleaned = secure_filename(value or "untitled").strip("._-")
    return cleaned[:64] or "untitled"


def unique_path(directory, stem, extension):
    candidate = directory / f"{stem}{extension}"
    if not candidate.exists():
        return candidate
    suffix = secrets.token_hex(3)
    candidate = directory / f"{stem}-{suffix}{extension}"
    while candidate.exists():
        suffix = secrets.token_hex(3)
        candidate = directory / f"{stem}-{suffix}{extension}"
    return candidate


def track_id(track):
    if track.get("id"):
        return str(track["id"])
    if track.get("soundcloudId"):
        return str(track["soundcloudId"])
    src = track.get("src") or track.get("title") or secrets.token_hex(8)
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:12]


def with_api_links(track):
    item = dict(track)
    item_id = track_id(track)
    item["id"] = item_id
    item["streamUrl"] = f"/api/tracks/{item_id}/stream"
    item["downloadUrl"] = f"/api/tracks/{item_id}/download"
    return item


def find_track(manifest, item_id):
    for index, track in enumerate(manifest.get("tracks", [])):
        if track_id(track) == str(item_id):
            return index, track
    raise NotFound("Track not found.")


def resolve_local_path(relative_value, allowed_root):
    if not relative_value:
        raise NotFound("Track has no file path.")
    candidate = (ROOT / relative_value).resolve()
    allowed = allowed_root.resolve()
    if allowed != candidate and allowed not in candidate.parents:
        raise Forbidden("Path is outside the Musicloud media folder.")
    if not candidate.exists() or not candidate.is_file():
        raise NotFound("Media file was not found on disk.")
    return candidate


def save_upload(file_storage, directory, allowed_extensions, preferred_stem):
    original_name = file_storage.filename or ""
    extension = Path(original_name).suffix.lower()
    if extension not in allowed_extensions:
        allowed = ", ".join(sorted(allowed_extensions))
        raise BadRequest(f"Unsupported file type '{extension or 'unknown'}'. Allowed: {allowed}")
    stem = safe_stem(preferred_stem or Path(original_name).stem)
    target = unique_path(directory, stem, extension)
    with target.open("wb") as output:
        shutil.copyfileobj(file_storage.stream, output, length=1024 * 1024)
    return target


def wav_duration(path):
    if path.suffix.lower() not in {".wav", ".wave"}:
        return 0
    try:
        with wave.open(str(path), "rb") as audio:
            frames = audio.getnframes()
            rate = audio.getframerate()
            return round(frames / float(rate)) if rate else 0
    except Exception:
        return 0


def relative_media_path(path):
    return path.relative_to(ROOT).as_posix()


def delete_local_media(relative_value, allowed_root, remaining_tracks):
    if not relative_value:
        return None
    if str(relative_value).startswith(("http://", "https://")):
        return {"path": relative_value, "status": "skipped-remote"}

    still_referenced = any(track.get("src") == relative_value or track.get("artwork") == relative_value for track in remaining_tracks)
    if still_referenced:
        return {"path": relative_value, "status": "kept-shared"}

    try:
        path = resolve_local_path(relative_value, allowed_root)
    except NotFound:
        return {"path": relative_value, "status": "already-missing"}
    except Forbidden:
        return {"path": relative_value, "status": "skipped-outside-media-folder"}

    path.unlink()
    return {"path": relative_value, "status": "deleted"}


@app.errorhandler(BadRequest)
@app.errorhandler(Forbidden)
@app.errorhandler(NotFound)
def handle_http_error(error):
    return jsonify({"error": error.description}), error.code


@app.errorhandler(413)
def handle_upload_too_large(error):
    return jsonify({"error": "Upload is larger than this Musicloud server allows."}), 413


@app.get("/api/health")
def health():
    manifest = load_manifest()
    tracks = manifest.get("tracks", [])
    return jsonify(
        {
            "ok": True,
            "name": APP_NAME,
            "tracks": len(tracks),
            "localAudioFiles": len(list(TRACKS_DIR.glob("*"))) if TRACKS_DIR.exists() else 0,
            "localArtworkFiles": len(list(ARTWORK_DIR.glob("*"))) if ARTWORK_DIR.exists() else 0,
        }
    )


@app.get("/api/tracks")
def list_tracks():
    manifest = load_manifest()
    include_hidden = request.args.get("include_hidden") == "1"
    tracks = [
        with_api_links(track)
        for track in manifest.get("tracks", [])
        if include_hidden or not track.get("hidden")
    ]
    payload = dict(manifest)
    payload["tracks"] = tracks
    payload["downloaded"] = len(tracks)
    return jsonify(payload)


@app.get("/api/tracks/<item_id>")
def get_track(item_id):
    manifest = load_manifest()
    _, track = find_track(manifest, item_id)
    return jsonify(with_api_links(track))


@app.get("/api/tracks/<item_id>/stream")
def stream_track(item_id):
    manifest = load_manifest()
    _, track = find_track(manifest, item_id)
    path = resolve_local_path(track.get("src"), TRACKS_DIR)
    return send_file(path, mimetype=mimetypes.guess_type(path.name)[0], conditional=True)


@app.get("/api/tracks/<item_id>/download")
def download_track(item_id):
    manifest = load_manifest()
    _, track = find_track(manifest, item_id)
    path = resolve_local_path(track.get("src"), TRACKS_DIR)
    download_name = path.name
    return send_file(path, as_attachment=True, download_name=download_name, conditional=True)


@app.post("/api/tracks")
def upload_track():
    audio = request.files.get("audio")
    if not audio or not audio.filename:
        raise BadRequest("Choose an audio file first.")

    title = (request.form.get("title") or Path(audio.filename).stem).strip()
    artist = (request.form.get("artist") or DEFAULT_ARTIST).strip()
    genre = (request.form.get("genre") or "cloudcast").strip()

    stem = f"{safe_stem(title)}-{secrets.token_hex(4)}"
    audio_path = save_upload(audio, TRACKS_DIR, ALLOWED_AUDIO_EXTENSIONS, stem)

    artwork_value = ""
    artwork = request.files.get("artwork")
    if artwork and artwork.filename:
        artwork_path = save_upload(artwork, ARTWORK_DIR, ALLOWED_ARTWORK_EXTENSIONS, audio_path.stem)
        artwork_value = relative_media_path(artwork_path)

    manifest = load_manifest()
    new_track = {
        "id": secrets.token_hex(8),
        "title": title or "Untitled",
        "artist": artist or DEFAULT_ARTIST,
        "genre": genre or "cloudcast",
        "duration": wav_duration(audio_path),
        "plays": 0,
        "comments": 0,
        "likes": 0,
        "src": relative_media_path(audio_path),
        "artwork": artwork_value,
        "soundcloudUrl": "",
        "soundcloudId": None,
        "source": "musicloud-upload",
        "uploadedAt": utc_now(),
    }
    manifest.setdefault("tracks", []).append(new_track)
    save_manifest(manifest)
    return jsonify(with_api_links(new_track)), 201


@app.patch("/api/tracks/<item_id>")
def update_track(item_id):
    payload = request.get_json(silent=True) or {}
    allowed_fields = {"title", "artist", "genre"}
    manifest = load_manifest()
    index, track = find_track(manifest, item_id)
    for field in allowed_fields:
        if field in payload:
            value = str(payload[field]).strip()
            if value:
                track[field] = value
    manifest["tracks"][index] = track
    save_manifest(manifest)
    return jsonify(with_api_links(track))


@app.delete("/api/tracks/<item_id>")
def delete_track(item_id):
    manifest = load_manifest()
    index, track = find_track(manifest, item_id)
    remaining_tracks = [item for item_index, item in enumerate(manifest.get("tracks", [])) if item_index != index]

    deleted = []
    deleted.append(delete_local_media(track.get("src"), TRACKS_DIR, remaining_tracks))
    deleted.append(delete_local_media(track.get("artwork"), ARTWORK_DIR, remaining_tracks))
    deleted = [item for item in deleted if item]

    manifest["tracks"] = remaining_tracks
    save_manifest(manifest)
    return jsonify({"ok": True, "track": with_api_links(track), "media": deleted})


@app.get("/musicloud-soundcloud-callback/")
def soundcloud_callback_page():
    return Response(
        "<!doctype html><html><body style='font-family:sans-serif;background:#10141d;color:#f8fbff;padding:32px'>"
        "<h1>Musicloud received the SoundCloud callback</h1>"
        "<p>Copy this browser URL back into the importer if it asks for it.</p>"
        "</body></html>",
        mimetype="text/html",
    )


@app.get("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.get("/<path:path>")
def static_files(path):
    if path.startswith("api/"):
        raise NotFound("API route not found.")
    requested = (ROOT / path).resolve()
    if not requested.exists() or requested.is_dir() or ROOT.resolve() not in requested.parents:
        return redirect("/")
    return send_from_directory(requested.parent, requested.name)


def parse_args():
    parser = argparse.ArgumentParser(description="Run the local Musicloud API server.")
    parser.add_argument("--host", default=os.environ.get("MUSICLOUD_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MUSICLOUD_PORT", "5174")))
    return parser.parse_args()


def main():
    ensure_dirs()
    args = parse_args()
    print("")
    print("Musicloud API server")
    print(f"Open: http://{args.host}:{args.port}/")
    print("Upload and delete are available from the web UI.")
    app.run(host=args.host, port=args.port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
