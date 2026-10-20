# Fire TV Bookshelf Screensaver

A small, self-hosted service that turns your most recent Audiobookshelf listens into a
hand-painted bookshelf poster for a Fire TV screensaver.

The generated image is a 21:9 panorama. On a 16:9 TV the Fire TV app shows a 16:9 window and
slowly pans across the extra width. The service polls Audiobookshelf every 12 hours and generates a
new poster only when the shelf actually changes.

## What it does

- Reads your current audiobook and the 19 most recently finished books from Audiobookshelf.
- Derives authors from the library folder path, because ABS/ID3 metadata often mixes in narrators
  and translators.
- Gives every spine a unique, genre/title-informed design recipe. A fixed catalog prevents four
  romances from all getting cherries and lace.
- Uses the current book's actual cover as the reference image.
- Calls GPT Image 2 to produce a 2528x1088 (21:9) watercolor/gouache poster.
- Serves the poster and a Fire TV `panorama.json` over HTTP.
- Keeps the last good poster if Audiobookshelf or OpenAI fails.
- Persists design assignments by Audiobookshelf item ID, so the shelf does not reshuffle when one
  book arrives.
- Supports optional per-book title/author/design overrides without editing Audiobookshelf tags.

## Requirements

- Docker with Compose.
- Audiobookshelf reachable from the container. This setup assumes ABS is the `audiobookshelf`
  container on the external Docker network `web`.
- An Audiobookshelf API key belonging to your user.
- An OpenAI API key with image generation access.
- A place to run the tunnel if you want HTTPS (Cloudflare Tunnel in this setup).

## Install

```powershell
git clone https://github.com/rickycatto2/fire_tv_bookshelf_screensaver.git
cd fire_tv_bookshelf_screensaver
Copy-Item .env.example .env
```

Fill in `.env`:

```dotenv
ABS_API_KEY=...
OPENAI_API_KEY=...
PUBLIC_TOKEN=a-long-random-string
```

Then:

```powershell
docker compose up -d --build
docker compose logs -f
```

The first check can take a minute or two because it fetches 20 items and one image. The service is
ready when `/healthz` is healthy. If you leave `PUBLIC_TOKEN` empty, the service generates one in
`data/public_token.txt`.

## URLs

The service listens on `127.0.0.1:8787` and requires a secret path token:

```text
http://127.0.0.1:8787/s/<PUBLIC_TOKEN>/panorama.json
http://127.0.0.1:8787/s/<PUBLIC_TOKEN>/poster-xxxxxxxxxxxx.jpg
```

For the Fire TV app, use the HTTPS hostname:

```text
https://bookshelf.pixelwood.co/s/<PUBLIC_TOKEN>/panorama.json
```

## Install and configure the Fire TV app

The helper script installs the APK, builds the token URL from `data/public_token.txt`, and
configures the app over ADB:

```powershell
.\scripts\install-firetv.ps1 `
  -Serial 192.168.1.50:5555 `
  -ApkPath .\dist\PanoramaScreensaver-1.0.0.apk
```

It also tries to set the Fire TV `screensaver_components` setting. If your Fire OS build blocks
that, choose **Settings → Display & Sounds → Screen Saver → Panorama Screensaver** manually.

The APK is also published as a GitHub release asset so it can be installed with Downloader.

The token is a capability. Anyone with the full URL can fetch the poster and trigger a no-op
refresh. Treat it like a password and do not commit it.

Endpoints:

| Endpoint | Purpose |
| --- | --- |
| `/healthz` | Liveness, no secrets |
| `/s/<token>/panorama.json` | Fire TV manifest, `no-store` |
| `/s/<token>/poster-*.jpg` | Immutable versioned poster |
| `/s/<token>/status` | Last generation/status, token-protected |
| `POST /s/<token>/refresh` | Check for changes now, token-protected |

Images are content-addressed in the filename, so Cloudflare can cache them forever. The manifest
is never cached.

## Cloudflare Tunnel

The hostname is served by a dedicated tunnel container, not by the existing Caddy or Windows
`cloudflared` services. This keeps the bookshelf service isolated from the other hostnames.

1. Create the tunnel once:

```powershell
cloudflared tunnel create bookshelf-screensaver
cloudflared tunnel route dns --overwrite-dns <TUNNEL_ID> bookshelf.pixelwood.co
```

2. Copy `cloudflared.example.yml` to `cloudflared.yml`, put in the tunnel ID, and run:

```powershell
docker run -d `
  --name cloudflared-bookshelf `
  --restart unless-stopped `
  --network web `
  -v "$env:USERPROFILE\.cloudflared\<TUNNEL_ID>.json:/etc/cloudflared/credentials.json:ro" `
  -v "${PWD}\cloudflared.yml:/etc/cloudflared/config.yml:ro" `
  cloudflare/cloudflared:latest tunnel --config /etc/cloudflared/config.yml run
```

The tunnel config points at `http://bookshelf-screensaver:8787` on the shared `web` network.
Credentials and `cloudflared.yml` are intentionally gitignored.

## Changing the look

The design recipes live in `make_sample.py` under `DESIGNS`. Each recipe has a palette, motif,
typography, and mood. Every active spine gets a different recipe.

To correct a bad folder name or a bad title without touching Audiobookshelf, create
`data/book_overrides.json` from `book_overrides.example.json`:

```json
{
  "library-item-id": {
    "title": "Corrected Title",
    "author": "Corrected Author",
    "design": "cat"
  }
}
```

Keys are ABS library item IDs. Design IDs come from `DESIGNS` in `make_sample.py`.

## 4K

The default profile is 1080p-friendly:

```dotenv
BOOKSHELF_IMAGE_WIDTH=2528
BOOKSHELF_IMAGE_HEIGHT=1088
BOOKSHELF_ASPECT_LABEL=21:9
```

For a 4K TV, use:

```dotenv
BOOKSHELF_IMAGE_WIDTH=3840
BOOKSHELF_IMAGE_HEIGHT=1648
```

Generation cost and model support are controlled by `BOOKSHELF_IMAGE_MODEL` and
`BOOKSHELF_IMAGE_QUALITY`.

## Scheduling and failure behavior

- Poll interval: `POLL_SECONDS` (default `43200` = 12 hours).
- At startup, it checks immediately.
- A failed check retries after `RETRY_SECONDS` (default 1800).
- The previous poster is served until a new generation succeeds.
- The design assignment map is written to `data/design_assignments.json`.

## Privacy

This repo is public. The generated poster, book data, `.env`, tunnel credentials, and output
images are all gitignored. Do not commit `data/`, `output/`, or `work/`.

## Development

Without Docker, install `requirements.txt`, set the environment variables, and run:

```powershell
python app.py
```

`make_sample.py` can still be used as a one-shot generator:

```powershell
python make_sample.py
```

## Verification

Tested with:

- Audiobookshelf 2.x API at `http://audiobookshelf:80` on Docker network `web`.
- GPT Image 2 at 2528x1088, high quality.
- A dedicated Cloudflare Tunnel at `https://bookshelf.pixelwood.co`.
- The existing Fire TV screensaver APK reading `panorama.json` and panning the 21:9 poster.
