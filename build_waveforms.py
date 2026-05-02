import json

import musicloud_api as api


def main():
    manifest = api.load_manifest()
    waveforms = {
        "source": "musicloud",
        "generatedAt": api.utc_now(),
        "bars": api.WAVEFORM_BARS,
        "tracks": {},
    }

    for track in manifest.get("tracks", []):
        try:
            path = api.resolve_local_path(track.get("src"), api.TRACKS_DIR)
        except Exception:
            continue
        peaks = api.wav_waveform(path) or api.ffmpeg_waveform(path)
        if not peaks:
            continue
        stat = path.stat()
        waveforms["tracks"][api.track_id(track)] = {
            "src": track.get("src"),
            "mtimeNs": stat.st_mtime_ns,
            "size": stat.st_size,
            "peaks": peaks,
        }

    api.write_json_atomic(api.WAVEFORMS_PATH, waveforms)
    print(json.dumps({"tracks": len(manifest.get("tracks", [])), "waveforms": len(waveforms["tracks"])}))


if __name__ == "__main__":
    main()
