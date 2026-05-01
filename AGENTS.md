# Musicloud Agent Safety Rules

These rules are mandatory for any AI/coding agent working in this repository.

## Current Operating Status

- Work on site/code locally in `d:\src\musicloud`.
- The user handles git add/commit/push locally, then pulls on the server.
- Do not deploy code directly to the server unless the user explicitly asks.
- Use the live server only for read-only verification unless the user explicitly approves a remote change.
- The live site is `https://tubamobile.com/`.
- Mission: build and maintain Musicloud, a SoundCloud-style personal music site for Sazran, backed by imported SoundCloud tracks and locally hosted artwork/audio.
- Local API work has started in `musicloud_api.py`. It serves the site, exposes `/api/tracks`, stream/download endpoints, and user-facing upload/edit/delete endpoints.
- The Musicloud web user is treated as the library owner. Upload and delete are available from the UI without token language.
- Track delete is intentionally destructive: `DELETE /api/tracks/<id>` removes the manifest entry and deletes that track's local audio/artwork files when they are not shared by another track. The UI must warn before calling it.
- Run the local API-driven site on Windows with `start_musicloud_api.cmd`; default URL is `http://127.0.0.1:5174/`.
- On Linux/server, `./startsite.sh` creates/uses `.venv`, installs `requirements.txt`, and starts `musicloud_api.py` on `127.0.0.1:5174`; `./stopsite.sh` stops it. If venv support is missing, install `python3-venv`.
- Live server status as of the last check: `musicloud_api.py` is running locally on the server at `127.0.0.1:5174` and returns JSON there, but `https://tubamobile.com/api/health` still returns `index.html`. That means nginx still needs the `/api/` proxy block.
- Live upload support requires nginx proxying `/api/` to `127.0.0.1:5174` and `client_max_body_size`. Use `1G` as the preferred upload cap for songs/long WAVs unless the user explicitly wants another value; `5G` was judged too large. See `tools/nginx-tubamobile-api.md`.
- Administrator/deployment tooling should live in scripts under `tools/` or root-level command scripts, not in the public user flow.
- Latest local media verification: `data/tracks.json` lists 93 tracks, `data/skipped-tracks.json` lists 0 skipped tracks, and all 93 local audio files are present.
- Latest live media verification before adding the final 2 manual tracks: the live server had 91 matching files in `/home/shlomia/musicloud/tracks`, no missing live URLs, and no Windows-path filenames in the live `tracks/` folder. After git pull/media sync, re-verify live has 93 tracks.
- Latest artwork status: 53 SoundCloud artwork images were downloaded locally into ignored `artwork/` files and `data/tracks.json` now points at local `artwork/...jpg` paths. 40 tracks have no SoundCloud artwork and use generated CSS covers.
- Git should track JSON manifests and code:
  - `data/tracks.json`
  - `data/skipped-tracks.json`
  - site code/scripts/docs
- Git should ignore heavy binary media only:
  - audio files under `tracks/`
  - image files under `artwork/`
  - `.musicloud-soundcloud.json`
- `sync_musicloud_media.py` is for media-only sync and must never delete remote media.

## Destructive Operations

Do not run, write, or recommend destructive commands without showing the exact command and waiting for explicit approval.

Destructive commands include, but are not limited to:

- `rm -rf`
- `Remove-Item -Recurse`
- deleting or recreating remote folders
- overwriting remote media folders
- `git reset`
- `git checkout --`
- force pushes
- scripts that delete `tracks/`, `data/`, or deployment folders

## Deploy And Sync

Git is responsible for source-controlled site/code files.

Generated binary media is not deployed through git:

- audio files under `tracks/`
- image files under `artwork/`
- `.musicloud-soundcloud.json`

JSON manifests are source-controlled:

- `data/tracks.json`
- `data/skipped-tracks.json`

Media sync scripts must be non-destructive:

- default to verify/dry-run when practical
- compare local and remote files first
- upload only missing or explicitly selected files
- never delete remote `tracks/` or `data/` unless the user approves the exact delete command

## Required Workflow

For any deploy/sync task:

1. Inspect and report current local and remote state first.
2. State what will change.
3. Prefer a verify-only/dry-run command.
4. Wait for approval before any delete, overwrite, reset, or remote cleanup.

## Project Rule

No script may delete `tracks/` or `data/` on the server. Only upload missing files unless the user explicitly approves deletion of an exact path.

## UI Data Rule

Do not add fake placeholder artists, users, followers, or songs to the Musicloud UI. The app should render imported data from `data/tracks.json`; if no manifest is available, show an empty/import state instead of demo songs.
