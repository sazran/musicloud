# Musicloud

Run the API-driven local site:

```cmd
start_musicloud_api.cmd
```

Open the printed local URL.
The website user can upload and delete tracks from the UI. Delete shows a browser warning and then removes the manifest entry plus the local audio/artwork files for that track.

On Linux/server, run:

```sh
./startsite.sh
```

The script creates `.venv` and installs Flask there. If Ubuntu reports venv support is missing, run `sudo apt install python3-venv`.

For live `tubamobile.com` upload support, see:

```sh
tools/nginx-tubamobile-api.md
```
