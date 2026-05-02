import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_SERVER = "shlomia@tubamobile.com"
DEFAULT_REMOTE_DIR = "/home/shlomia/musicloud"
DEFAULT_IDENTITY = Path.home() / ".ssh" / "musicloud_deploy_ed25519"
KOOLU_TRACK = ROOT / "tracks" / "Koolu-565106316.wav"
WAVEFORMS = ROOT / "data" / "waveforms.json"


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


def local_file_info(path):
    stat = path.stat()
    return {"name": path.name, "size": stat.st_size, "mtime": int(stat.st_mtime)}


def remote_file_info(server, remote_path, identity=None):
    result = remote(
        server,
        f"if [ -f '{remote_path}' ]; then stat -c '%n\t%s\t%Y' '{remote_path}'; else echo 'missing\t0\t0'; fi",
        identity=identity,
        capture=True,
    )
    parts = result.stdout.strip().split("\t")
    if not parts or parts[0] == "missing":
        return {"name": remote_path, "size": 0, "mtime": 0, "missing": True}
    return {"name": parts[0], "size": int(parts[1]), "mtime": int(parts[2]), "missing": False}


def print_pair(label, local_path, remote_info):
    local = local_file_info(local_path)
    print("")
    print(label)
    print(f"  local:  {local_path.relative_to(ROOT).as_posix()} size={local['size']} mtime={local['mtime']}")
    if remote_info.get("missing"):
        print(f"  remote: missing")
    else:
        print(f"  remote: {remote_info['name']} size={remote_info['size']} mtime={remote_info['mtime']}")


def main():
    parser = argparse.ArgumentParser(description="Verify or upload the replacement Koolu track and waveform cache.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument("--remote-dir", default=DEFAULT_REMOTE_DIR)
    parser.add_argument(
        "--identity",
        default=str(DEFAULT_IDENTITY) if DEFAULT_IDENTITY.exists() else "",
        help="SSH private key to use for server auth",
    )
    parser.add_argument("--upload", action="store_true", help="Upload/overwrite the exact Koolu file and waveform cache.")
    args = parser.parse_args()
    identity = Path(os.path.expandvars(args.identity)).expanduser() if args.identity else None

    if not KOOLU_TRACK.exists():
        raise SystemExit(f"Missing {KOOLU_TRACK.relative_to(ROOT).as_posix()}")
    if not WAVEFORMS.exists():
        raise SystemExit("Missing data/waveforms.json. Run: python build_waveforms.py")

    remote_track = f"{args.remote_dir}/tracks/{KOOLU_TRACK.name}"
    remote_waveforms = f"{args.remote_dir}/data/{WAVEFORMS.name}"

    remote(args.server, f"mkdir -p '{args.remote_dir}/tracks' '{args.remote_dir}/data'", identity=identity)
    track_remote_info = remote_file_info(args.server, remote_track, identity=identity)
    waveforms_remote_info = remote_file_info(args.server, remote_waveforms, identity=identity)

    print_pair("Koolu audio", KOOLU_TRACK, track_remote_info)
    print_pair("Waveform cache", WAVEFORMS, waveforms_remote_info)

    if not args.upload:
        print("")
        print("Verify-only mode. No remote files were changed.")
        print("To upload the replacement, run:")
        print("  update_koolu_on_server.cmd --upload")
        return 0

    print("")
    print("Uploading exact files. This overwrites only:")
    print(f"  {remote_track}")
    print(f"  {remote_waveforms}")
    run([*scp_base(identity), str(KOOLU_TRACK.relative_to(ROOT)), f"{args.server}:{remote_track}"])
    run([*scp_base(identity), str(WAVEFORMS.relative_to(ROOT)), f"{args.server}:{remote_waveforms}"])
    remote(
        args.server,
        f"chmod o+x /home/shlomia && chmod o+r '{remote_track}' '{remote_waveforms}'",
        identity=identity,
    )
    print("")
    print("Done. No remote files were deleted.")
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
