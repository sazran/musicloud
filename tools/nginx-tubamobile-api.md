# Tubamobile API Upload Setup

The live upload path needs two things:

- `musicloud_api.py` running on the server at `127.0.0.1:5174`
- nginx proxying `/api/` to that API and allowing large audio uploads

## 1. Pull Code On Server

From `/home/shlomia/musicloud`:

```sh
git pull
./stopsite.sh
./startsite.sh
curl -I http://127.0.0.1:5174/api/health
```

`./startsite.sh` creates `.venv` and installs `requirements.txt` there. If Ubuntu says venv is missing, run:

```sh
sudo apt install python3-venv
./startsite.sh
```

The `curl` should return JSON headers from Flask, not the static `index.html`.

## 2. Edit Nginx Site

Open:

```sh
sudo nano /etc/nginx/sites-available/tubamobile
```

Inside the `server_name tubamobile.com;` server block, add or update this before the normal static `location /`:

```nginx
client_max_body_size 1G;

location = /api {
    return 308 /api/;
}

location /api/ {
    proxy_pass http://127.0.0.1:5174/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_request_buffering off;
    proxy_read_timeout 3600;
    proxy_send_timeout 3600;
}
```

Keep the existing static `location /` for the website files.

## 3. Reload And Verify

```sh
sudo nginx -t
sudo systemctl reload nginx
curl -I https://tubamobile.com/api/health
curl https://tubamobile.com/api/health
```

Expected:

- `Content-Type: application/json`
- JSON like `{"ok":true,...}`

If `/api/health` returns HTML, nginx is still serving the static site instead of the API.

## Notes

- HTTP 413 means nginx or Flask rejected the upload size.
- nginx should use `client_max_body_size 1G;`.
- Flask defaults to `MUSICLOUD_MAX_UPLOAD_BYTES=1073741824`, which is 1GB.
- `./startsite.sh` now starts the API server, not a static file server.
