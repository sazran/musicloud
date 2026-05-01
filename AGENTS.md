# Musicloud Agent Safety Rules

These rules are mandatory for any AI/coding agent working in this repository.

## Current Operating Status

- Work on site/code locally in `d:\src\musicloud`.
- The user handles git add/commit/push locally, then pulls on the server.
- Do not deploy code directly to the server unless the user explicitly asks.
- Use the live server only for read-only verification unless the user explicitly approves a remote change.
- The live site is `https://tubamobile.com/`.
- Latest media verification: `data/tracks.json` lists 91 imported SoundCloud tracks, the live server has all 91 matching files in `/home/shlomia/musicloud/tracks`, and there are no Windows-path filenames in the live `tracks/` folder.
- Latest artwork status: 53 SoundCloud artwork images were downloaded locally into ignored `artwork/` files and `data/tracks.json` now points at local `artwork/...jpg` paths. 38 tracks have no SoundCloud artwork and use generated CSS covers.
- Generated SoundCloud media is separate from git and lives in ignored local paths:
  - `tracks/`
  - `artwork/`
  - `data/tracks.json`
  - `data/skipped-tracks.json`
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

Generated media and import output are not deployed through git:

- `tracks/`
- `data/tracks.json`
- `data/skipped-tracks.json`
- `.musicloud-soundcloud.json`

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
