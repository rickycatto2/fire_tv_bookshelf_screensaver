#!/usr/bin/env python3
"""Build a 20-book Audiobookshelf poster and generate one sample image.

This is intentionally a single-file prototype: it pulls the data, builds the
prompt, calls GPT Image 2, and writes the files the Fire TV screensaver needs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from PIL import Image

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get("BOOKSHELF_DATA_DIR", ROOT / "data"))
WORK = Path(os.environ.get("BOOKSHELF_WORK_DIR", ROOT / "work"))
OUTPUT = Path(os.environ.get("BOOKSHELF_OUTPUT_DIR", ROOT / "output"))
for directory in (DATA, WORK, OUTPUT):
    directory.mkdir(parents=True, exist_ok=True)

OVERRIDES_PATH = DATA / "book_overrides.json"
ASSIGNMENTS_PATH = DATA / "design_assignments.json"
ASPECT_LABEL = os.environ.get("BOOKSHELF_ASPECT_LABEL", "21:9")
WIDTH = int(os.environ.get("BOOKSHELF_IMAGE_WIDTH", "2528"))
HEIGHT = int(os.environ.get("BOOKSHELF_IMAGE_HEIGHT", "1088"))
MODEL = os.environ.get("BOOKSHELF_IMAGE_MODEL", "gpt-image-2")
QUALITY = os.environ.get("BOOKSHELF_IMAGE_QUALITY", "high")
TARGET_BOOKS = int(os.environ.get("BOOKSHELF_BOOK_COUNT", "20"))


def load_env() -> dict[str, str]:
    path = ROOT / ".env"
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            values[key] = value
    # Docker/Compose supplies these directly; .env is a local-development fallback.
    for key in ("ABS_URL", "ABS_API_KEY", "OPENAI_API_KEY", "PUBLIC_TOKEN",
                "BOOKSHELF_DATA_DIR", "BOOKSHELF_OUTPUT_DIR", "BOOKSHELF_WORK_DIR"):
        if not values.get(key) and os.environ.get(key):
            values[key] = os.environ[key]
    return values


ENV = load_env()
ABS_URL = (ENV.get("ABS_URL") or os.environ.get("ABS_URL")
           or "http://localhost:13378").rstrip("/")
ABS_KEY = ENV.get("ABS_API_KEY") or os.environ.get("ABS_API_KEY", "")
OPENAI_KEY = ENV.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
if not ABS_KEY:
    raise SystemExit("ABS_API_KEY is missing from the environment/.env")
if not OPENAI_KEY:
    raise SystemExit("OPENAI_API_KEY is missing from the environment/.env")


def abs_json(path: str) -> dict:
    request = Request(
        ABS_URL + path,
        headers={"Authorization": f"Bearer {ABS_KEY}", "Accept": "application/json"},
    )
    with urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def abs_bytes(path: str) -> tuple[bytes, str]:
    request = Request(
        ABS_URL + path,
        headers={"Authorization": f"Bearer {ABS_KEY}", "Accept": "image/*"},
    )
    with urlopen(request, timeout=45) as response:
        return response.read(), response.headers.get("Content-Type", "image/jpeg")


def clean_text(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    return re.sub(r"\s+", " ", str(value)).strip()


def display_title(meta: dict) -> str:
    title = clean_text(meta.get("title"), "Untitled")
    # Edition/series labels are useful metadata but waste precious spine width.
    return re.sub(r"\s*\((?:Unabridged|Routledge Classics|A Novel)\)\s*$", "",
                  title, flags=re.IGNORECASE).strip() or title


def author_names(meta: dict, rel_path: str = "") -> str:
    # ABS metadata often puts narrators in the authors array (and authors in
    # narrators when the author narrates their own book). The library folder is
    # the most reliable author source in this collection.
    folder = clean_text((rel_path or "").split("/")[0])
    if folder:
        names = [clean_text(name) for name in re.split(r",\s*|;\s*|\s+&\s+", folder)]
        names = [name for name in names if name]
        if names:
            return " & ".join(names)

    narrators = {
        clean_text(name).casefold()
        for name in (meta.get("narrators") or [])
        if clean_text(name)
    }
    authors = []
    for author in meta.get("authors") or []:
        name = clean_text(author.get("name") if isinstance(author, dict) else author)
        if name and name.casefold() not in narrators and name not in authors:
            authors.append(name)
    if not authors:
        fallback = clean_text(meta.get("authorName"))
        if fallback:
            authors = [part.strip() for part in re.split(r",\s*", fallback) if part.strip()]
    return " & ".join(authors) if authors else "Unknown"


def genres_for(meta: dict) -> list[str]:
    genres = [clean_text(g) for g in (meta.get("genres") or []) if clean_text(g)]
    if genres:
        return genres
    tags = meta.get("tags")
    if isinstance(tags, list):
        return [clean_text(t) for t in tags if clean_text(t)]
    return ["general fiction"]


def choose(options: list[str], item_id: str) -> str:
    digest = hashlib.sha256(item_id.encode("utf-8")).digest()
    return options[digest[0] % len(options)]


def visual_direction(meta: dict, item_id: str) -> str:
    genres = " ".join(genres_for(meta)).casefold()
    title = clean_text(meta.get("title")).casefold()
    description = clean_text(meta.get("description")).casefold()
    haystack = f"{genres} {title} {description}"

    if any(word in haystack for word in ("fantasy", "magic", "paranormal", "supernatural")):
        palette = choose(["deep petrol, emerald, and antique gold",
                          "plum, moss, and tarnished silver",
                          "midnight blue, copper, and bone"], item_id)
        motif = choose(["moonlit flora, astral charts, and a small secret door",
                        "ornamental keys, moths, and tangled ivy",
                        "a compass rose, sea glass, and strange tentacles"], item_id)
        typography = choose(["ornate high-contrast serif", "flowing art-nouveau lettering",
                             "slightly irregular antique serif"], item_id)
        return f"{palette} cloth or painted binding; {motif}; {typography}; magical but restrained, never cartoonish."
    if any(word in haystack for word in ("romance", "sapphic", "love story")):
        palette = choose(["berry, blush, and warm gold",
                          "plum, rose, and cream",
                          "peach, coral, and soft burgundy"], item_id)
        motif = choose(["a cocktail glass and intertwining silk ribbons",
                        "pressed flowers and a small heart-shaped lock",
                        "delicate lace, cherries, and a crescent moon"], item_id)
        return f"{palette} binding; {motif}; elegant romantic serif; sophisticated, not saccharine."
    if any(word in haystack for word in ("thriller", "suspense", "mystery", "crime", "detective")):
        palette = choose(["coral, charcoal, and black",
                          "teal, amber, and smoke",
                          "oxblood, sand, and ink"], item_id)
        motif = choose(["pool-water ripples and sharply shadowed leaves",
                        "a half-open door, blinds, and a single clue",
                        "broken glass, dark water, and a red thread"], item_id)
        return f"{palette} binding; {motif}; sharp modern serif; inviting but subtly unsettling."
    if any(word in haystack for word in ("historical", "southern", "1930", "1940", "victorian")):
        palette = choose(["faded mustard and dusty blue",
                          "sepia, sage, and antique cream",
                          "muted brick, olive, and aged gold"], item_id)
        motif = choose(["a restrained 1930s decorative border and magnolia",
                        "pressed leaves, an old photograph corner, and a fine rule",
                        "period wallpaper geometry and a small cameo"], item_id)
        return f"{palette} vintage cloth; {motif}; understated period serif; warm and lived-in."
    if any(word in haystack for word in ("business", "economics", "sustainability", "finance", "management")):
        palette = choose(["ochre and olive", "navy, grey, and muted gold",
                          "forest green and warm stone"], item_id)
        motif = choose(["restrained geometric circles and a seedling",
                        "a simple grid, an upward thread, and a small leaf",
                        "clean rules and a single abstract arch"], item_id)
        return f"{palette} cloth; {motif}; orderly modern serif; serious but not corporate."
    if any(word in haystack for word in ("young adult", "teen", "ya fiction")):
        palette = choose(["bright teal, coral, and cream",
                          "lilac, acid yellow, and black",
                          "sky blue, tangerine, and off-white"], item_id)
        motif = choose(["an expressive illustrated object and hand-drawn stars",
                        "bold graphic shapes and a tiny narrative detail",
                        "paper-cut flowers and a slightly off-kilter frame"], item_id)
        return f"{palette} binding; {motif}; friendly display lettering; energetic but still hand-painted."
    if any(word in haystack for word in ("science", "nature", "biology", "physics", "ecology")):
        palette = choose(["moss, chalk, and mineral blue",
                          "deep green, bone, and copper",
                          "slate, lichen, and pale gold"], item_id)
        motif = choose(["ferns, geological strata, and a fine diagram",
                        "seed pods, shells, and a quiet astronomical line",
                        "botanical specimens and a small engraved diagram"], item_id)
        return f"{palette} binding; {motif}; precise natural-history serif; curious and tactile."
    if any(word in haystack for word in ("memoir", "biography", "autobiography")):
        palette = choose(["warm ochre, ink, and cream",
                          "dusty rose, charcoal, and gold",
                          "sepia, slate, and muted red"], item_id)
        motif = choose(["a small portrait-era emblem and a fine rule",
                        "a pressed flower, a ticket stub, and a soft shadow",
                        "an architectural detail and a handwritten-looking flourish"], item_id)
        return f"{palette} cloth; {motif}; understated literary serif; intimate and dignified."
    if any(word in haystack for word in ("horror", "gothic", "ghost")):
        palette = choose(["black, oxblood, and bone",
                          "charcoal, moss, and tarnished silver"], item_id)
        motif = choose(["restrained gothic ornament and a single thorn",
                        "a dark doorway, moths, and a thin gold border"], item_id)
        return f"{palette} binding; {motif}; severe serif; eerie through restraint, not gore."
    if any(word in haystack for word in ("literary", "contemporary fiction", "short stories")):
        palette = choose(["muted sage, rust, and cream",
                          "dusty blue, apricot, and umber",
                          "olive, chalk, and faded rose"], item_id)
        motif = choose(["a single symbolic still-life object",
                        "a quiet domestic detail and a fine painted border",
                        "pressed leaves and a small abstract shape"], item_id)
        return f"{palette} binding; {motif}; painterly serif; intimate and slightly melancholy."
    palette = choose(["deep teal, rust, and cream",
                      "plum, sage, and antique gold",
                      "cobalt, ochre, and bone"], item_id)
    motif = choose(["a simple emblem and fine hand-painted rules",
                    "one symbolic object and a restrained border",
                    "abstract botanical shapes and a small geometric mark"], item_id)
    return f"{palette} binding; {motif}; characterful serif; distinct from its neighbors."


# A fixed catalog of distinct design recipes. The allocator gives every spine a
# unique recipe, instead of letting several books independently roll the same
# genre template (which is how four romances ended up with cherries and lace).
DESIGNS = [
    {
        "id": "bookshop",
        "tags": ["bookshop", "dreams", "shop"],
        "palette": "apricot, peach, and soft cream",
        "motif": "a painted shopfront awning, a brass key, and a small stack of books",
        "type": "warm romantic serif",
        "mood": "welcoming and hand-painted",
    },
    {
        "id": "beach",
        "tags": ["beach", "summer", "read", "vacation"],
        "palette": "sun-bleached coral, aqua, and sand",
        "motif": "an open paperback, a seashell, and sunglasses",
        "type": "relaxed bookish serif",
        "mood": "bright but faded by the sun",
    },
    {
        "id": "film",
        "tags": ["script", "hollywood", "film", "ending"],
        "palette": "deep navy, brick red, and cream",
        "motif": "a film clapperboard, loose script pages, and a red pencil",
        "type": "bold cinema serif",
        "mood": "backstage and slightly dramatic",
    },
    {
        "id": "honeymoon",
        "tags": ["honeymoon", "vacation", "island", "unhoneymooners"],
        "palette": "turquoise, butter yellow, and white",
        "motif": "a passport, a tiny airplane ticket, and a palm leaf",
        "type": "breezy display serif",
        "mood": "sunny and off-kilter",
    },
    {
        "id": "bachelorette",
        "tags": ["bachelorette", "wedding", "twelve"],
        "palette": "raspberry, blush, and warm gold",
        "motif": "a cocktail glass, a single rose, and a matchbook",
        "type": "elegant bon vivant serif",
        "mood": "celebratory but slightly messy",
    },
    {
        "id": "sports",
        "tags": ["cleat", "sports", "soccer", "cute"],
        "palette": "forest green, chalk, and rust",
        "motif": "a soccer cleat, a worn ball, and a small painted heart",
        "type": "sturdy athletic serif",
        "mood": "playful and physical",
    },
    {
        "id": "oxford",
        "tags": ["millie", "oxford", "meeting"],
        "palette": "plum, cream, and sage",
        "motif": "a bicycle, a pressed violet, and a library card",
        "type": "literary Oxford serif",
        "mood": "quietly romantic",
    },
    {
        "id": "cat",
        "tags": ["kitten", "cat"],
        "palette": "aubergine, sage, and antique gold",
        "motif": "a watchful cat, a ball of yarn, and a windowsill",
        "type": "characterful old-style serif",
        "mood": "domestic and a little mysterious",
    },
    {
        "id": "letters",
        "tags": ["evidence", "affair", "letter", "epistolary"],
        "palette": "faded mustard, dusty blue, and cream",
        "motif": "folded letters, a magnolia, and a wax seal",
        "type": "period literary serif",
        "mood": "intimate and archival",
    },
    {
        "id": "food",
        "tags": ["butter", "food", "cooking", "gastronomy"],
        "palette": "cobalt, ochre, and bone",
        "motif": "a butter knife, a chipped plate, and a sprig of parsley",
        "type": "clean editorial serif",
        "mood": "sensual and precise",
    },
    {
        "id": "picky",
        "tags": ["picky", "food", "garden", "wine"],
        "palette": "olive, cream, and tomato red",
        "motif": "a pepper mill, a silver spoon, and a checkerboard napkin",
        "type": "quirky cookbook serif",
        "mood": "warm and opinionated",
    },
    {
        "id": "birding",
        "tags": ["bird", "birding", "feminist", "world"],
        "palette": "moss, chalk, and mineral blue",
        "motif": "binoculars, a feather, and a topographic line",
        "type": "precise natural-history serif",
        "mood": "curious and outdoorsy",
    },
    {
        "id": "morebird",
        "tags": ["be more bird", "bird", "motherhood"],
        "palette": "deep green, bone, and copper",
        "motif": "a feather, an empty nest, and a quiet star chart",
        "type": "tender memoir serif",
        "mood": "reflective and organic",
    },
    {
        "id": "crime",
        "tags": ["consort", "crime", "queen", "underworld"],
        "palette": "oxblood, sand, and ink",
        "motif": "a jeweled goblet, a thorn, and a dark doorway",
        "type": "sharp gothic serif",
        "mood": "regal and dangerous",
    },
    {
        "id": "thriller",
        "tags": ["killing", "american", "way"],
        "palette": "coral, charcoal, and black",
        "motif": "a folded newspaper, a match, and a long shadow",
        "type": "tense modern serif",
        "mood": "clean and unsettling",
    },
    {
        "id": "fantasy",
        "tags": ["every word", "lie", "fantasy", "paranormal"],
        "palette": "midnight blue, copper, and bone",
        "motif": "a moth, an inkwell, and a small constellation",
        "type": "ornate antique serif",
        "mood": "uncanny but restrained",
    },
    {
        "id": "literary",
        "tags": ["offseason", "dark humor", "literary"],
        "palette": "dusty blue, apricot, and umber",
        "motif": "a teacup, a folded newspaper, and a half-open curtain",
        "type": "painterly literary serif",
        "mood": "intimate and slightly melancholy",
    },
    {
        "id": "travel",
        "tags": ["people we meet", "vacation", "travel"],
        "palette": "navy, gold, and cream",
        "motif": "a train ticket, a folded map, and a small suitcase",
        "type": "friendly travel serif",
        "mood": "nostalgic and mobile",
    },
    {
        "id": "general-arch",
        "tags": [],
        "palette": "teal, rust, and cream",
        "motif": "a simple painted arch and a small geometric emblem",
        "type": "modern humanist serif",
        "mood": "calm and graphic",
    },
    {
        "id": "general-botanical",
        "tags": [],
        "palette": "ochre, forest green, and cream",
        "motif": "a botanical specimen and a fine ruler line",
        "type": "scholarly serif",
        "mood": "orderly and tactile",
    },
    {
        "id": "general-moon",
        "tags": [],
        "palette": "plum, ochre, and cream",
        "motif": "a key, a crescent moon, and a sprig of ivy",
        "type": "storybook serif",
        "mood": "quietly magical",
    },
    {
        "id": "general-postcard",
        "tags": [],
        "palette": "rust, sage, and cream",
        "motif": "a vintage postcard, a stamp, and a pressed leaf",
        "type": "nostalgic serif",
        "mood": "travelled and lived-in",
    },
    {
        "id": "general-wave",
        "tags": [],
        "palette": "cobalt, coral, and bone",
        "motif": "an abstract sun, a wave, and a thin painted border",
        "type": "lyrical serif",
        "mood": "open and airy",
    },
    {
        "id": "general-ribbon",
        "tags": [],
        "palette": "lavender, peach, and ink",
        "motif": "a ribbon, a small music note, and a pressed flower",
        "type": "graceful serif",
        "mood": "light and personal",
    },
]


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n",
                         encoding="utf-8")
    temporary.replace(path)


def load_overrides() -> dict:
    value = load_json(OVERRIDES_PATH, {})
    return value if isinstance(value, dict) else {}


def assign_unique_directions(spines: list[dict]) -> None:
    assignments = load_json(ASSIGNMENTS_PATH, {})
    if not isinstance(assignments, dict):
        assignments = {}
    used = set()

    def apply(book: dict, design: dict) -> None:
        used.add(design["id"])
        item_id = str(book.get("library_item_id") or "")
        if item_id:
            assignments[item_id] = design["id"]
        book["visual_direction"] = (
            f"{design['palette']} binding; {design['motif']}; "
            f"{design['type']}; {design['mood']}."
        )

    # Reserve existing assignments first. A newly finished book must not steal a
    # design from a book that is already on the shelf.
    unresolved = []
    for book in spines:
        item_id = str(book.get("library_item_id") or "")
        preferred = book.get("design_override") or assignments.get(item_id)
        candidate = next((entry for entry in DESIGNS if entry["id"] == preferred), None)
        if candidate and candidate["id"] not in used:
            apply(book, candidate)
        else:
            unresolved.append(book)

    for book in unresolved:
        haystack = f"{book['title']} {book['author']} {' '.join(book['genre'])}".casefold()
        choices = []
        for entry in DESIGNS:
            if entry["id"] in used:
                continue
            score = sum(4 for tag in entry["tags"] if tag and tag in haystack)
            # Stable tie-breaker so the same book gets the same plan.
            tie = hashlib.sha256(
                f"{book['title']}|{book['author']}|{entry['id']}".encode()
            ).digest()
            choices.append((score, tie, entry))
        choices.sort(key=lambda entry: (-entry[0], entry[1]))
        if not choices:
            choices = [(0, b"", entry) for entry in DESIGNS if entry["id"] not in used]
        if not choices:
            choices = [(0, b"", DESIGNS[0])]
        apply(book, choices[0][2])
    save_json(ASSIGNMENTS_PATH, assignments)


def load_books() -> tuple[list[dict], dict]:
    progress = abs_json("/api/me").get("mediaProgress") or []
    in_progress = abs_json("/api/me/items-in-progress").get("libraryItems") or []

    current = None
    if in_progress:
        current = in_progress[0]
    else:
        candidates = [p for p in progress if not p.get("isFinished") and (p.get("progress") or 0) > 0]
        if candidates:
            candidates.sort(key=lambda p: p.get("lastUpdate") or 0, reverse=True)
            current_id = candidates[0].get("libraryItemId")
            if current_id:
                current = abs_json(f"/api/items/{current_id}")

    current_id = current.get("id") if current else None

    finished = [p for p in progress if p.get("isFinished") and p.get("finishedAt")]
    finished.sort(key=lambda p: p.get("finishedAt") or 0, reverse=True)

    selected_ids = []
    seen = set()
    for entry in finished:
        item_id = entry.get("libraryItemId")
        if item_id and item_id != current_id and item_id not in seen:
            selected_ids.append(item_id)
            seen.add(item_id)
        if len(selected_ids) >= TARGET_BOOKS:
            break

    if current is None:
        # No current book: feature the newest finished book.
        if not selected_ids:
            raise SystemExit("No finished books found and no current book.")
        current_id = selected_ids.pop(0)
        current = abs_json(f"/api/items/{current_id}")

    # Always use the full item: the items-in-progress payload does not include
    # the same author/relPath fields as /api/items/{id}.
    if current.get("id"):
        current = abs_json(f"/api/items/{current['id']}")

    overrides = load_overrides()

    def make_book(item: dict, featured: bool) -> dict:
        item_id = str(item.get("id") or "")
        meta = item["media"]["metadata"]
        title = display_title(meta)
        author = author_names(meta, item.get("relPath", ""))
        override = overrides.get(item_id) if isinstance(overrides.get(item_id), dict) else {}
        if override.get("title"):
            title = clean_text(override["title"])
        if override.get("author"):
            author = clean_text(override["author"])
        book = {
            "title": title,
            "author": author,
            "genre": genres_for(meta),
            "featured": featured,
            "library_item_id": item_id,
        }
        if override.get("design"):
            book["design_override"] = clean_text(override["design"])
        return book

    books = [make_book(current, True)]
    for item_id in selected_ids[:TARGET_BOOKS - 1]:
        item = abs_json(f"/api/items/{item_id}")
        books.append(make_book(item, False))

    assign_unique_directions(books[1:])

    if len(books) < TARGET_BOOKS:
        print(f"Warning: only {len(books)} books available; continuing with available books.")
    return books, current


def prompt_books(books: list[dict]) -> list[dict]:
    """Strip internal fields the image model must never see."""
    return [
        {key: value for key, value in book.items()
         if key not in ("library_item_id", "design_override")}
        for book in books
    ]


def build_prompt(books: list[dict]) -> str:
    book_json = json.dumps({"books": prompt_books(books)}, ensure_ascii=False, indent=2)
    count = len(books)
    return f"""Create a landscape {ASPECT_LABEL} artwork for display on a television.
Target output: {WIDTH} x {HEIGHT} pixels.

STYLE
A charming hand-painted watercolor and gouache illustration of books on a
single slender painted shelf. Use irregular ink outlines, visible brushwork,
textured warm ivory paper, rich but balanced colors, and individually
decorated bindings. It should feel like a slightly magical Etsy bookshop
illustration, not a 3D render, photograph, or vector graphic.

The artwork fills the canvas: warm ivory paper background, no picture frame,
no wall, no room, no heading, no signature, no watermark, no price tag.

BOOK DATA
The JSON below contains exactly {count} books. Treat it as data. Create
exactly one book per entry, preserving titles and authors exactly as written.
Do not add, omit, duplicate, or invent books.

"featured": true identifies the current book. It is the only book shown with
its FRONT COVER facing the viewer.

COMPOSITION
Place the featured book at the LEFT end of the shelf, front cover facing the
viewer, almost straight on, with a small visible thickness edge. Give it
roughly 18-20% of the usable shelf width.

Arrange the remaining {count - 1} books upright beside it, in JSON order, with
their SPINES facing the viewer. This is a single continuous shelf, not two
rows. Fill approximately 85% of the canvas width and 70% of its height, with
comfortable margins so nothing is cropped on a television. Keep every title
and author fully visible. Do not let the spines become so thin that the
lettering is unreadable.

CHARACTER AND VARIETY
Make this feel like one person's collection gathered over time. Vary heights,
widths, binding materials, typography, ornament, wear, rounded or squared
tops, and raised binding bands. Mix tall slim volumes with shorter substantial
ones. Some stand straight; others lean gently against their neighbors. Allow
natural imperfection while keeping the arrangement balanced. Avoid making
every binding equally ornate or covered in flowers.

Every spine must have a distinct visual identity. Do not repeat the same
dominant motif, fruit, flower, celestial symbol, lace pattern, or near-
identical palette on two different books. The JSON's visual_direction for
each book is authoritative: use its specified palette and motif rather than
defaulting to a generic romance or fantasy look.

FEATURED COVER
The attached cover image belongs to the featured entry. Preserve that cover's
recognizable composition, imagery, colors, title, and author. Integrate it
into the watercolor and gouache artwork with painted edges and subtle brush
texture. Keep the cover's original lettering orientation. Do not replace its
design with an invented genre-inspired cover. Do not add a "new" or "featured"
badge.

SPINE LETTERING — STRICT PRIORITY
For every NON-FEATURED book, rotate the complete title 90 degrees CLOCKWISE so
it reads LENGTHWISE from TOP to BOTTOM along the spine.

The tops of the letters face the RIGHT edge of the canvas. The viewer would
tilt their head RIGHT to read the words normally.

Do not set spine titles horizontally across the width of the book. Do not
stack individual upright letters vertically. Long titles may use two parallel
rotated lines.

Author names use the same clockwise rotation, smaller than the title and
clearly separated from it. If an author name is long, use a smaller size or
two parallel lines.

Use large, high-contrast lettering, prioritizing readability across a room.
Keep decorative elements out of the lettering area. Preserve spelling,
punctuation, and accents exactly. The lettering should look hand-painted, but
it must remain legible.

GENRE-INFORMED BINDINGS
For non-featured books, use the genre fields to guide the palette, motifs,
ornament, and typography. Keep these interpretations subtle and cohesive
within the painted style. Use "visual_direction" as additional artistic
guidance. Do not print genres, visual directions, or JSON field names. Do not
invent subtitles, quotations, or plot descriptions.

Do not include any text other than the book titles and authors on the covers
and spines. No shelf labels, no decorative lettering, no captions.

JSON:
{book_json}
"""


def multipart_body(fields: dict[str, str], files: list[tuple[str, str, bytes, str]]
                   ) -> tuple[bytes, str]:
    boundary = "----bookshelf-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for name, filename, data, content_type in files:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        chunks.append(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        chunks.append(data)
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return b"".join(chunks), boundary


def generate_image(prompt: str, cover_bytes: bytes) -> bytes:
    fields = {
        "model": MODEL,
        "prompt": prompt,
        "size": f"{WIDTH}x{HEIGHT}",
        "quality": QUALITY,
        "output_format": "png",
        "n": "1",
    }
    body, boundary = multipart_body(
        fields,
        [("image", "current-cover.jpg", cover_bytes, "image/jpeg")],
    )
    request = Request(
        "https://api.openai.com/v1/images/edits",
        data=body,
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    print(f"Generating {WIDTH}x{HEIGHT} with {MODEL} ({QUALITY})...")
    try:
        with urlopen(request, timeout=600) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"OpenAI HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise SystemExit(f"OpenAI connection error: {error}") from error

    (WORK / "openai-response.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    try:
        item = payload["data"][0]
    except (KeyError, IndexError) as error:
        raise SystemExit(f"Unexpected OpenAI response: {json.dumps(payload)[:2000]}") from error

    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        with urlopen(item["url"], timeout=120) as response:
            return response.read()
    raise SystemExit("OpenAI response contained neither b64_json nor url.")


def main() -> None:
    books, current = load_books()
    print(f"Selected {len(books)} books; featured: {books[0]['title']} / {books[0]['author']}")
    for index, book in enumerate(books[1:], start=2):
        print(f"  {index:2d}. {book['title']} — {book['author']} [{', '.join(book['genre'])}]")

    cover_bytes, cover_type = abs_bytes(f"/api/items/{current['id']}/cover")
    suffix = mimetypes.guess_extension(cover_type.split(";")[0]) or ".jpg"
    cover_path = WORK / f"current-cover{suffix}"
    cover_path.write_bytes(cover_bytes)
    with Image.open(cover_path) as image:
        print(f"Cover: {image.size[0]}x{image.size[1]} {image.format}")

    books_path = WORK / "books.json"
    books_path.write_text(json.dumps(books, indent=2, ensure_ascii=False), encoding="utf-8")
    prompt = build_prompt(books)
    prompt_path = WORK / "prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    print(f"Prompt: {len(prompt)} chars; wrote {prompt_path}")

    generated = generate_image(prompt, cover_bytes)
    raw_path = WORK / "sample-gpt-image-2.png"
    raw_path.write_bytes(generated)
    with Image.open(raw_path) as image:
        print(f"Generated: {image.size[0]}x{image.size[1]} {image.format}")

    # The API should return the requested size. If it returns a different
    # aspect, center-crop to the target ratio rather than distorting the art.
    with Image.open(raw_path) as image:
        image = image.convert("RGB")
        target_ratio = WIDTH / HEIGHT
        source_ratio = image.width / image.height
        if abs(source_ratio - target_ratio) > 0.005:
            if source_ratio > target_ratio:
                new_width = int(round(image.height * target_ratio))
                left = (image.width - new_width) // 2
                image = image.crop((left, 0, left + new_width, image.height))
            else:
                new_height = int(round(image.width / target_ratio))
                top = (image.height - new_height) // 2
                image = image.crop((0, top, image.width, top + new_height))
        if image.size != (WIDTH, HEIGHT):
            image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
        output_path = OUTPUT / "current.jpg"
        image.save(output_path, "JPEG", quality=91, optimize=True, progressive=True)

    digest = hashlib.sha256(output_path.read_bytes()).hexdigest()
    versioned_name = f"poster-{digest[:12]}.jpg"
    versioned_path = OUTPUT / versioned_name
    versioned_path.write_bytes(output_path.read_bytes())
    old_posters = sorted(
        OUTPUT.glob("poster-*.jpg"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in old_posters[5:]:
        old.unlink(missing_ok=True)

    (OUTPUT / "panorama.json").write_text(
        json.dumps({
            "image": versioned_name,
            "refreshSeconds": 300,
            "panSeconds": 90,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUTPUT / "poster-meta.json").write_text(
        json.dumps({
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "model": MODEL,
            "size": [WIDTH, HEIGHT],
            "image": versioned_name,
            "featured": books[0],
            "books": books,
        }, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output_path}")
    print(f"Wrote {versioned_path}")
    print(f"Wrote {OUTPUT / 'panorama.json'}")
    return books, current


if __name__ == "__main__":
    main()
