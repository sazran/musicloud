# SoundCloud Import

This importer uses SoundCloud's official API and only downloads tracks where SoundCloud exposes an official download URL for your authorized account.

Do not put your SoundCloud password in this project.

## Start Here

Run this from the project root:

```cmd
start_musicloud_import.cmd
```

That interactive Python script starts Musicloud, opens the SoundCloud app page, tells you the redirect URL to add, asks only for `client_id` and `client_secret`, runs OAuth, downloads official originals, and opens Musicloud again.

You can also run Python directly:

```cmd
py start_musicloud_import.py
```

If localhost redirect gets stuck, register a public redirect URL in SoundCloud and run:

```cmd
py start_musicloud_import.py --redirect-uri "https://tubamobile.com/"
```

After SoundCloud approval, paste the full redirected browser URL back into the script when it asks.

If SoundCloud finds your tracks but exposes zero download links, the script offers one official retry: enabling downloads on your own SoundCloud tracks, then trying again. It asks before changing that permission.

## Missing Pieces You Provide

Step 1 is creating or opening your SoundCloud developer app and adding this exact redirect URL:

```text
https://tubamobile.com/musicloud-soundcloud-callback/
```

Then copy your app values:

```text
client_id
client_secret
```

SoundCloud currently documents OAuth 2.1 with PKCE. The helper script opens the authorization page, catches the redirected URL locally, exchanges the code for an access token, and then sets `SOUNDCLOUD_ACCESS_TOKEN` for that terminal.

The guided Python script above is the supported path.

The helper opens SoundCloud in your browser. Log in there, approve the app, and SoundCloud redirects to the temporary local callback. After that, the same command downloads official originals into Musicloud.

You can also set the token yourself before running only the exporter:

```powershell
$env:SOUNDCLOUD_ACCESS_TOKEN = "paste_your_oauth_access_token_here"
```

The scripts will not ask for your SoundCloud account password. If the token variable is not set, the importer stops and tells you what to set.

You get that token by creating/using a SoundCloud developer app and completing OAuth for your own account. SoundCloud API access may require approval from SoundCloud.

Official docs:

- https://developers.soundcloud.com/docs/api/introduction
- https://developers.soundcloud.com/docs/api/guide
- https://help.soundcloud.com/hc/en-us/articles/115003446727-API-usage-policies

## Run

The Python importer handles OAuth and download together.

The script writes:

```text
tracks\...
data\tracks.json
```

Refresh the local Musicloud page after it finishes:

```text
http://127.0.0.1:5173/
```

## Local Files Without SoundCloud API
The local-file path was removed from the website. This project now guides the SoundCloud OAuth path only.

## What Gets Skipped

Tracks are skipped when SoundCloud does not expose `downloadable` and `download_url` through the official API.

The importer writes a report here:

```text
data\skipped-tracks.json
```
