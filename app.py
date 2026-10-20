"""FastAPI wrapper around the bookshelf poster generator."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

import make_sample as generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOG = logging.getLogger("bookshelf-service")

OUTPUT = generator.OUTPUT
DATA = generator.DATA
STATE_PATH = DATA / "state.json"
TOKEN_PATH = DATA / "public_token.txt"

CHECK_INTERVAL = max(300, int(os.environ.get("POLL_SECONDS", "43200")))
RETRY_INTERVAL = max(300, int(os.environ.get("RETRY_SECONDS", "1800")))

_service_lock = threading.Lock()
_generation_lock = threading.Lock()
_worker_thread: threading.Thread | None = None


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def public_token() -> str:
    token = os.environ.get("PUBLIC_TOKEN", "").strip()
    if token:
        return token
    if TOKEN_PATH.exists():
        token = TOKEN_PATH.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(30)
    TOKEN_PATH.write_text(token + "\n", encoding="utf-8")
    LOG.info("Generated PUBLIC_TOKEN in %s", TOKEN_PATH)
    return token


TOKEN = public_token()


def state() -> dict:
    value = read_json(STATE_PATH, {})
    return value if isinstance(value, dict) else {}


def update_state(**changes) -> dict:
    current = state()
    current.update(changes)
    write_json(STATE_PATH, current)
    return current


def has_output() -> bool:
    manifest = read_json(OUTPUT / "panorama.json", {})
    image = manifest.get("image")
    return bool(image and (OUTPUT / image).is_file())


def fingerprint(books: list[dict], current: dict) -> str:
    payload = {
        "current": current.get("id"),
        "cover": (current.get("media") or {}).get("coverPath"),
        "books": [
            {
                "id": book.get("library_item_id"),
                "title": book.get("title"),
                "author": book.get("author"),
            }
            for book in books
        ],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def generate_if_needed(force: bool = False) -> dict:
    if not _generation_lock.acquire(blocking=False):
        return {"started": False, "reason": "generation already running"}
    try:
        update_state(generation_started_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                     last_error=None)
        books, current = generator.load_books()
        fp = fingerprint(books, current)
        previous = state()
        if not force and previous.get("fingerprint") == fp and has_output():
            update_state(
                last_checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                featured=books[0]["title"],
                current_book_id=current.get("id"),
                last_error=None,
            )
            LOG.info("No change; keeping %s", previous.get("image", "existing poster"))
            return {"started": True, "generated": False, "fingerprint": fp}

        LOG.info("Generating poster for %s", books[0]["title"])
        books, current = generator.main()
        manifest = read_json(OUTPUT / "panorama.json", {})
        update_state(
            fingerprint=fp,
            generated_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            last_checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            featured=books[0]["title"],
            current_book_id=current.get("id"),
            image=manifest.get("image"),
            last_error=None,
        )
        LOG.info("Poster generated: %s", manifest.get("image"))
        return {"started": True, "generated": True, "fingerprint": fp}
    except Exception as error:  # noqa: BLE001 - service must keep serving old poster
        LOG.exception("Poster generation failed")
        update_state(
            last_error=str(error),
            last_checked_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )
        return {"started": False, "error": str(error)}
    finally:
        _generation_lock.release()


def check_in_background(force: bool = False) -> None:
    global _worker_thread
    with _service_lock:
        if _worker_thread and _worker_thread.is_alive():
            return
        _worker_thread = threading.Thread(
            target=generate_if_needed,
            kwargs={"force": force},
            name="bookshelf-generator",
            daemon=True,
        )
        _worker_thread.start()


def poll_loop() -> None:
    check_in_background()
    while True:
        delay = RETRY_INTERVAL if state().get("last_error") else CHECK_INTERVAL
        time.sleep(delay)
        while _worker_thread and _worker_thread.is_alive():
            time.sleep(5)
        check_in_background()


app = FastAPI(title="Fire TV Bookshelf Screensaver", docs_url=None, redoc_url=None)


@app.on_event("startup")
def startup() -> None:
    LOG.info("Public path token file: %s", TOKEN_PATH)
    LOG.info("Serving /s/<token>/panorama.json; output=%s", OUTPUT)
    threading.Thread(target=poll_loop, name="bookshelf-poller", daemon=True).start()


def require_token(token: str) -> None:
    if not secrets.compare_digest(token, TOKEN):
        raise HTTPException(status_code=404, detail="Not found")


@app.get("/healthz")
def healthz():
    data = state()
    return {
        "ok": True,
        "has_output": has_output(),
        "generated_at": data.get("generated_at"),
        "last_checked_at": data.get("last_checked_at"),
    }


@app.get("/s/{token}/panorama.json")
def panorama(token: str):
    require_token(token)
    path = OUTPUT / "panorama.json"
    if not path.is_file():
        raise HTTPException(status_code=503, detail="Poster is being prepared")
    return FileResponse(
        path,
        media_type="application/json",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/s/{token}/status")
def status(token: str):
    require_token(token)
    data = state()
    return JSONResponse({
        "ok": not data.get("last_error"),
        "generated_at": data.get("generated_at"),
        "last_checked_at": data.get("last_checked_at"),
        "featured": data.get("featured"),
        "image": data.get("image"),
        "last_error": data.get("last_error"),
    })


@app.post("/s/{token}/refresh")
def refresh(token: str):
    require_token(token)
    check_in_background(force=False)
    return {"started": True, "message": "Check requested"}


@app.get("/s/{token}/{filename}")
def image(token: str, filename: str):
    require_token(token)
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.(?:jpg|jpeg|png|webp)", filename):
        raise HTTPException(status_code=404, detail="Not found")
    path = OUTPUT / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable"
        if filename.startswith("poster-") else "no-store, max-age=0",
    }
    media_type = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media_type, headers=headers)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8787")))
