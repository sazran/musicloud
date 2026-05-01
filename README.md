# Musicloud

Run the API-driven local site:

```cmd
start_musicloud_api.cmd
```

Open the printed local URL.
Listeners can browse, play, search, and download. The owner signs in with email and password to upload, import, edit, and delete tracks. Delete shows a browser warning and then removes the manifest entry plus the local audio/artwork files for that track.

On first run, use the Sign in button to create the owner account.

On Linux/server, run:

```sh
./startsite.sh
```

The script creates `.venv` and installs Flask there. If Ubuntu reports venv support is missing, run `sudo apt install python3-venv`.

For live `tubamobile.com` upload support, see:

```sh
tools/nginx-tubamobile-api.md
```
