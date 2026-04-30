import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SERVER = "shlomia@tubamobile.com"
DEFAULT_REMOTE_DIR = "/home/shlomia/musicloud"


def run(command, check=True, capture=False):
    print("+ " + " ".join(command))
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def remote(server, command, capture=False):
    return run(["ssh", server, command], capture=capture)


def remote_track_names(server, remote_dir):
    result = remote(
        server,
        f"mkdir -p {remote_dir}/tracks {remote_dir}/data && find {remote_dir}/tracks -maxdepth 1 -type f -printf '%f\\n'",
        capture=True,
    )
    return set(result.stdout.splitlines())


def main():
    parser = argparse.ArgumentParser(description="Sync generated Musicloud media without touching git-managed site files.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()

    tracks_dir = ROOT / "tracks"
    data_dir = ROOT / "data"
    manifest = data_dir / "tracks.json"
    skipped = data_dir / "skipped-tracks.json"

    if not manifest.exists():
        raise SystemExit("Missing data/tracks.json. Run the importer first.")
    if not tracks_dir.exists():
        raise SystemExit("Missing tracks folder. Run the importer first.")

    manifest_json = json.loads(manifest.read_text(encoding="utf-8"))
    local_tracks = sorted(path for path in tracks_dir.iterdir() if path.is_file())
    remote_names = remote_track_names(args.server, args.remote_dir)
    missing = [path for path in local_tracks if path.name not in remote_names]

    print("")
    print(f"Manifest downloaded: {manifest_json.get('downloaded')}")
    print(f"Manifest skipped: {manifest_json.get('skipped')}")
    print(f"Local track files: {len(local_tracks)}")
    print(f"Remote track files: {len(remote_names)}")
    print(f"Missing remotely: {len(missing)}")

    if args.verify_only:
        if missing:
            print("")
            print("Missing files:")
            for path in missing[:50]:
                print(f"  {path.name}")
            if len(missing) > 50:
                print(f"  ... and {len(missing) - 50} more")
        return 0

    print("")
    print("Uploading manifest files only...")
    run(["scp", str(manifest), str(skipped), f"{args.server}:{args.remote_dir}/data/"])

    if missing:
        print("")
        print("Uploading only missing track files...")
        for path in missing:
            run(["scp", str(path), f"{args.server}:{args.remote_dir}/tracks/"])
    else:
        print("No track files are missing remotely.")

    print("")
    print("Fixing nginx-readable permissions...")
    remote(args.server, f"chmod o+x /home/shlomia && chmod -R o+rX {args.remote_dir}/data {args.remote_dir}/tracks")

    print("")
    print("Done. Git remains responsible for site/code files.")
    print("Check: https://tubamobile.com/data/tracks.json")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(f"Command failed with exit code {exc.returncode}", file=sys.stderr)
        if exc.stdout:
            print(exc.stdout, file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        raise SystemExit(exc.returncode)
