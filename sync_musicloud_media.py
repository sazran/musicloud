import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SERVER = "shlomia@tubamobile.com"
DEFAULT_REMOTE_DIR = "/home/shlomia/musicloud"
DEFAULT_IDENTITY = Path.home() / ".ssh" / "musicloud_deploy_ed25519"


def run(command, check=True, capture=False):
    print("+ " + " ".join(command))
    return subprocess.run(
        command,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def ssh_base(identity):
    command = ["ssh"]
    if identity:
        command.extend(["-i", str(identity)])
    return command


def scp_base(identity):
    command = ["scp"]
    if identity:
        command.extend(["-i", str(identity)])
    return command


def remote(server, command, identity=None, capture=False):
    return run([*ssh_base(identity), server, command], capture=capture)


def remote_track_names(server, remote_dir, identity=None):
    result = remote(
        server,
        f"mkdir -p {remote_dir}/tracks {remote_dir}/data && find {remote_dir}/tracks -maxdepth 1 -type f -printf '%f\\n'",
        identity=identity,
        capture=True,
    )
    return set(result.stdout.splitlines())


def manifest_sources(manifest):
    return [track.get("src", "").replace("/", "\\") for track in manifest.get("tracks", []) if track.get("src")]


def upload_many(files, destination, identity=None):
    if not files:
        return
    command = [*scp_base(identity), *[path.relative_to(ROOT).as_posix() for path in files], destination]
    run(command)


def main():
    parser = argparse.ArgumentParser(description="Sync generated Musicloud media without touching git-managed site files.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    parser.add_argument(
        "--identity",
        default=str(DEFAULT_IDENTITY) if DEFAULT_IDENTITY.exists() else "",
        help="SSH private key to use for server auth",
    )
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    identity = Path(os.path.expandvars(args.identity)).expanduser() if args.identity else None

    tracks_dir = ROOT / "tracks"
    artwork_dir = ROOT / "artwork"
    data_dir = ROOT / "data"
    manifest = data_dir / "tracks.json"
    skipped = data_dir / "skipped-tracks.json"

    if not manifest.exists():
        raise SystemExit("Missing data/tracks.json. Run the importer first.")
    if not tracks_dir.exists():
        raise SystemExit("Missing tracks folder. Run the importer first.")

    manifest_json = json.loads(manifest.read_text(encoding="utf-8"))
    listed_sources = manifest_sources(manifest_json)
    missing_locally = [src for src in listed_sources if not (ROOT / src).exists()]
    local_tracks = sorted(path for path in tracks_dir.iterdir() if path.is_file())
    local_artwork = sorted(path for path in artwork_dir.iterdir() if path.is_file()) if artwork_dir.exists() else []
    remote_names = remote_track_names(args.server, args.remote_dir, identity=identity)
    missing = [path for path in local_tracks if path.name not in remote_names]

    print("")
    print(f"Manifest downloaded: {manifest_json.get('downloaded')}")
    print(f"Manifest skipped: {manifest_json.get('skipped')}")
    print(f"Local track files: {len(local_tracks)}")
    print(f"Local artwork files: {len(local_artwork)}")
    print(f"Remote track files: {len(remote_names)}")
    print(f"Missing remotely: {len(missing)}")
    print(f"Manifest entries missing locally: {len(missing_locally)}")

    if missing_locally:
        print("")
        print("These manifest entries are missing on this computer:")
        for src in missing_locally[:20]:
            print(f"  {src}")
        if len(missing_locally) > 20:
            print(f"  ... and {len(missing_locally) - 20} more")

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
    print("Uploading manifest files only. This is one scp connection.")
    upload_many([manifest, skipped], f"{args.server}:{args.remote_dir}/data/", identity=identity)

    if local_artwork:
      remote(args.server, f"mkdir -p {args.remote_dir}/artwork", identity=identity)
      print("")
      print(f"Uploading {len(local_artwork)} artwork file(s).")
      upload_many(local_artwork, f"{args.server}:{args.remote_dir}/artwork/", identity=identity)

    if missing:
        print("")
        print(f"Uploading {len(missing)} missing track file(s). This is one scp connection.")
        upload_many(missing, f"{args.server}:{args.remote_dir}/tracks/", identity=identity)
    else:
        print("No track files are missing remotely.")

    print("")
    print("Fixing nginx-readable permissions...")
    remote(args.server, f"chmod o+x /home/shlomia && chmod -R o+rX {args.remote_dir}/data {args.remote_dir}/tracks {args.remote_dir}/artwork 2>/dev/null || true", identity=identity)

    print("")
    print("Done. Git remains responsible for site/code files.")
    print("Safety policy: this script never deletes remote media. See AGENTS.md.")
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
