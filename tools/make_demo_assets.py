"""Create the README hero image and animated GIF.

By default this draws a fictional demo shelf so forks can build the README
without a personal library. Pass --poster to use a real generated poster:

    python tools/make_demo_assets.py --poster output/current.jpg
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
WORK = ROOT / "work"
DOCS.mkdir(parents=True, exist_ok=True)
WORK.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 2528, 1088
SHELF_Y = 902

BOOKS = [
    ("The Lantern Atlas", "Mara Voss", "fantasy"),
    ("The Quiet Ledger", "Peter Hale", "business"),
    ("Salt and Static", "Nia Calder", "literary"),
    ("A Field Guide to Small Gods", "Ivo Mercer", "fantasy"),
    ("The Last Ferry Home", "June Alcott", "thriller"),
    ("Rounding Error", "Helen Park", "technology"),
    ("The Orchard at Midnight", "Tessa Wren", "magical"),
    ("Paper Moons", "Camille Ortiz", "romance"),
    ("The Glass Orchard", "Elias North", "literary"),
    ("Signal Fires", "Priya Sen", "science"),
    ("The Understudy", "Rowan Bell", "mystery"),
    ("Bright Things", "Maeve Quinn", "contemporary"),
    ("The Cartographer's Wife", "Ada Finch", "historical"),
    ("Small Hours", "Theo March", "memoir"),
    ("The Blue Hour", "Lila Crane", "literary"),
    ("A Theory of Everything Else", "Simon Vale", "science"),
    ("The Ember Season", "Cora Wynn", "fantasy"),
    ("The Longest Tuesday", "Benji Cole", "humor"),
    ("The Salt House", "Ingrid Shaw", "historical"),
    ("The Memory Thief", "Anika Rao", "speculative"),
]

PALETTES = [
    ((26, 54, 63), (238, 197, 119), (244, 241, 222)),
    ((84, 42, 32), (198, 145, 89), (245, 229, 199)),
    ((55, 40, 76), (178, 128, 171), (240, 220, 214)),
    ((25, 65, 49), (179, 190, 119), (236, 232, 209)),
    ((111, 45, 45), (216, 154, 104), (244, 224, 196)),
    ((35, 55, 86), (140, 171, 196), (236, 236, 228)),
    ((73, 60, 33), (201, 172, 103), (246, 235, 208)),
    ((104, 52, 77), (224, 154, 158), (247, 225, 219)),
    ((45, 67, 62), (180, 196, 167), (242, 236, 220)),
    ((28, 66, 77), (150, 190, 187), (240, 235, 219)),
    ((60, 42, 56), (199, 161, 133), (242, 226, 207)),
    ((92, 66, 43), (206, 174, 129), (246, 235, 215)),
    ((54, 58, 44), (174, 169, 115), (238, 233, 211)),
    ((71, 48, 37), (195, 159, 120), (245, 231, 212)),
    ((37, 50, 77), (149, 163, 196), (236, 236, 226)),
    ((46, 70, 87), (156, 190, 196), (239, 236, 222)),
    ((75, 38, 45), (214, 151, 122), (244, 224, 209)),
    ((88, 72, 28), (208, 183, 107), (246, 237, 214)),
    ((43, 67, 57), (168, 191, 157), (241, 235, 220)),
    ((58, 39, 75), (181, 148, 191), (242, 228, 219)),
]

ORNAMENTS = ["star", "leaf", "moon", "circle", "key", "wave", "flower", "sun"]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ["georgiab.ttf", "georgia.ttf", "timesbd.ttf", "times.ttf"] if bold else \
            ["georgia.ttf", "times.ttf", "segoeui.ttf"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def lighten(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel + (255 - channel) * amount))) for channel in color)


def darken(color: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(channel * (1 - amount)))) for channel in color)


def make_cover() -> Image.Image:
    width, height = 600, 900
    image = Image.new("RGB", (width, height), (18, 42, 47))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)],
                  fill=(int(18 + 30 * t), int(48 + 34 * t), int(55 + 24 * t)))
    cx, cy, radius = width // 2, 380, 128
    for step in range(24, 0, -1):
        r = radius + step * 3
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(210, 172, 98), width=1)
    draw.ellipse([cx - 82, cy - 82, cx + 82, cy + 82], fill=(228, 197, 133))
    draw.ellipse([cx - 48, cy - 48, cx + 48, cy + 48], fill=(64, 108, 104))
    for angle in range(0, 360, 45):
        radians = math.radians(angle)
        draw.line([
            (cx + math.cos(radians) * 55, cy + math.sin(radians) * 55),
            (cx + math.cos(radians) * 108, cy + math.sin(radians) * 108),
        ], fill=(245, 221, 173), width=2)
    draw.rectangle([42, 640, width - 42, 840], fill=(239, 228, 204))
    title_font = font(54, bold=True)
    author_font = font(26)
    draw.multiline_text((70, 662), "THE LANTERN\nATLAS", font=title_font,
                        fill=(24, 48, 50), spacing=8)
    draw.text((72, 797), "MARA VOSS", font=author_font, fill=(92, 74, 48))
    draw.rectangle([10, 10, width - 10, height - 10], outline=(198, 158, 94), width=2)
    return image


def ornament(draw: ImageDraw.ImageDraw, x: float, y: float, size: float,
             kind: str, color: tuple[int, int, int]) -> None:
    s = size
    if kind == "star":
        points = []
        for i in range(10):
            angle = -math.pi / 2 + i * math.pi / 5
            r = s if i % 2 == 0 else s * 0.42
            points.append((x + math.cos(angle) * r, y + math.sin(angle) * r))
        draw.polygon(points, fill=color)
    elif kind == "leaf":
        draw.ellipse([x - s, y - s * 0.45, x + s, y + s * 0.45], fill=color)
        draw.line([(x - s, y), (x + s, y)], fill=darken(color, 0.25), width=2)
    elif kind == "moon":
        draw.ellipse([x - s, y - s, x + s, y + s], fill=color)
        draw.ellipse([x - s * 0.45, y - s, x + s * 1.45, y + s], fill=(0, 0, 0, 0))
    elif kind == "key":
        draw.ellipse([x - s * 0.55, y - s * 0.55, x + s * 0.55, y + s * 0.55],
                     outline=color, width=3)
        draw.line([(x, y + s * 0.45), (x, y + s * 1.5)], fill=color, width=3)
        draw.line([(x, y + s * 1.2), (x + s * 0.45, y + s * 1.2)], fill=color, width=3)
    elif kind == "wave":
        for offset in (0, s * 0.45):
            points = [(x + i * s / 4, y + offset + math.sin(i * 1.4) * s * 0.18)
                      for i in range(9)]
            draw.line(points, fill=color, width=3)
    elif kind == "flower":
        for i in range(5):
            angle = i * 2 * math.pi / 5
            px, py = x + math.cos(angle) * s * 0.55, y + math.sin(angle) * s * 0.55
            draw.ellipse([px - s * 0.38, py - s * 0.38, px + s * 0.38, py + s * 0.38],
                         fill=color)
        draw.ellipse([x - s * 0.2, y - s * 0.2, x + s * 0.2, y + s * 0.2],
                     fill=darken(color, 0.25))
    elif kind == "sun":
        draw.ellipse([x - s * 0.55, y - s * 0.55, x + s * 0.55, y + s * 0.55],
                     fill=color)
        for i in range(8):
            angle = i * math.pi / 4
            draw.line([(x + math.cos(angle) * s * 0.7, y + math.sin(angle) * s * 0.7),
                       (x + math.cos(angle) * s, y + math.sin(angle) * s)],
                      fill=color, width=2)
    else:
        draw.ellipse([x - s * 0.65, y - s * 0.65, x + s * 0.65, y + s * 0.65],
                     outline=color, width=3)


def draw_spine(base: Image.Image, x: int, top: int, width: int, height: int,
               title: str, author: str, palette: tuple[tuple[int, int, int], ...],
               ornament_name: str) -> None:
    body, accent, paper = palette
    draw = ImageDraw.Draw(base)
    lean = 5 if (hash(title) % 7 == 0) else 0
    if lean:
        top += lean
        height -= lean
    bottom = top + height
    draw.rounded_rectangle([x + 4, top + 6, x + width + 4, bottom + 6], radius=5,
                           fill=(104, 89, 73))
    draw.rounded_rectangle([x, top, x + width, bottom], radius=5, fill=body)
    for offset in range(0, width, 3):
        t = offset / max(1, width)
        color = lighten(body, 0.08 * (1 - t)) if offset < width // 3 else \
            darken(body, 0.10 * (t - 0.33))
        draw.line([(x + offset, top + 2), (x + offset, bottom - 2)], fill=color)
    draw.line([(x + 3, top + 16), (x + width - 3, top + 16)],
              fill=lighten(accent, 0.1), width=3)
    draw.line([(x + 3, bottom - 22), (x + width - 3, bottom - 22)],
              fill=darken(accent, 0.1), width=2)
    draw.rounded_rectangle([x, top, x + width, bottom], radius=5,
                           outline=darken(body, 0.35), width=2)
    draw.line([(x + 4, top + 18), (x + 4, bottom - 25)],
              fill=lighten(accent, 0.25), width=2)

    text_layer = Image.new("RGBA", (height, width), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    title_size = 30
    title_font = font(title_size, bold=True)
    while title_font.getlength(title) > height - 100 and title_size > 14:
        title_size -= 2
        title_font = font(title_size, bold=True)
    author_font = font(max(12, title_size - 10), bold=False)
    text_draw.text((28, width * 0.42), title, font=title_font, fill=paper)
    author_text = author.upper()
    text_draw.text((height - author_font.getlength(author_text) - 24, width * 0.52),
                   author_text, font=author_font, fill=lighten(paper, 0.05))
    rotated = text_layer.rotate(-90, expand=True, resample=Image.Resampling.BICUBIC)
    base.paste(rotated, (x, top), rotated)
    ornament(draw, x + width / 2, top + 50, 15, ornament_name, accent)
    ornament(draw, x + width / 2, bottom - 60, 11,
             ORNAMENTS[(hash(title) + 3) % len(ORNAMENTS)], darken(accent, 0.1))


def render_poster() -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), (243, 236, 219))
    noise = Image.effect_noise((WIDTH, HEIGHT), 20).convert("L")
    paper = Image.new("RGB", (WIDTH, HEIGHT), (243, 236, 219))
    paper = Image.composite(Image.new("RGB", (WIDTH, HEIGHT), (236, 226, 205)), paper,
                            noise.point(lambda p: 36 if p > 138 else 0))
    image = Image.blend(image, paper, 0.48)
    draw = ImageDraw.Draw(image)

    for y in range(SHELF_Y, SHELF_Y + 30):
        t = (y - SHELF_Y) / 30
        draw.line([(20, y), (WIDTH - 20, y)],
                  fill=(int(117 - 38 * t), int(81 - 27 * t), int(51 - 17 * t)))
    draw.line([(20, SHELF_Y), (WIDTH - 20, SHELF_Y)], fill=(169, 124, 77), width=2)
    draw.line([(20, SHELF_Y + 30), (WIDTH - 20, SHELF_Y + 30)],
              fill=(55, 34, 22), width=3)
    for offset in (7, 15, 23):
        points = [(x, SHELF_Y + offset + math.sin(x * 0.004 + offset) * 3)
                  for x in range(20, WIDTH - 20, 24)]
        draw.line(points, fill=(93, 60, 38), width=1)

    cover = make_cover()
    cover_w, cover_h = 380, 570
    cover = cover.resize((cover_w, cover_h), Image.Resampling.LANCZOS)
    cover_top = SHELF_Y - cover_h - 8
    draw.rounded_rectangle([62, cover_top + 6, 86 + cover_w, SHELF_Y + 4], radius=8,
                           fill=(96, 78, 60))
    image.paste(cover, (70, cover_top))
    draw.rectangle([70, cover_top, 70 + cover_w, cover_top + cover_h],
                   outline=(92, 69, 42), width=2)

    spines = BOOKS[1:]
    left, right = 520, WIDTH - 55
    gap = 6
    widths = [88 + (hash(title) % 30) for title, _, _ in spines]
    total = sum(widths) + gap * (len(widths) - 1)
    scale = (right - left) / total
    widths = [max(64, int(w * scale)) for w in widths]
    while sum(widths) + gap * (len(widths) - 1) > right - left:
        widths[widths.index(max(widths))] -= 2
    cursor = left
    for index, ((title, author, _), width) in enumerate(zip(spines, widths)):
        height = 500 + (hash(title) % 180)
        top = SHELF_Y - height - 4
        palette = PALETTES[(index + 1) % len(PALETTES)]
        draw_spine(image, cursor, top, width, height, title, author, palette,
                   ORNAMENTS[(index * 3) % len(ORNAMENTS)])
        cursor += width + gap

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i in range(0, 110, 4):
        od.rectangle([i, i, WIDTH - i, HEIGHT - i], outline=(65, 48, 31, 2))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")

    out = DOCS / "demo-poster.jpg"
    image.save(out, "JPEG", quality=91, optimize=True, progressive=True)
    print(f"Wrote {out} ({image.size[0]}x{image.size[1]})")
    return image


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1],
                                           radius=radius, fill=255)
    return mask


def make_room() -> tuple[Image.Image, tuple[int, int, int, int]]:
    width, height = 1280, 720
    image = Image.new("RGB", (width, height), (224, 216, 203))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / height
        draw.line([(0, y), (width, y)],
                  fill=(int(229 - 18 * t), int(219 - 16 * t), int(203 - 13 * t)))
    noise = Image.effect_noise((width, height), 18).convert("L")
    texture = Image.new("RGB", (width, height), (238, 230, 217))
    image = Image.composite(texture, image, noise.point(lambda p: 20 if p > 142 else 0))
    draw = ImageDraw.Draw(image)

    draw.rectangle([58, 225, 218, 390], fill=(249, 243, 231), outline=(154, 131, 98), width=2)
    draw.rectangle([68, 235, 208, 380], outline=(177, 154, 121), width=1)
    draw.arc([95, 265, 180, 350], 200, 340, fill=(121, 141, 127), width=5)

    screen_x, screen_y, screen_w, screen_h = 256, 104, 768, 432
    tv_x, tv_y, tv_w, tv_h = screen_x - 16, screen_y - 16, screen_w + 32, screen_h + 32

    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([tv_x - 30, tv_y - 24, tv_x + tv_w + 30, tv_y + tv_h + 24],
                         radius=28, fill=(255, 225, 182, 42))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    image = Image.alpha_composite(image.convert("RGBA"), glow).convert("RGB")

    shadow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([tv_x + 8, tv_y + 14, tv_x + tv_w + 10, tv_y + tv_h + 18],
                         radius=18, fill=(28, 22, 18, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(16))
    image = Image.alpha_composite(image.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([tv_x, tv_y, tv_x + tv_w, tv_y + tv_h], radius=12,
                           fill=(18, 18, 20), outline=(8, 8, 10), width=2)
    draw.rounded_rectangle([tv_x + 3, tv_y + 3, tv_x + tv_w - 3, tv_y + 12], radius=6,
                           fill=(47, 47, 51))
    draw.ellipse([tv_x + tv_w // 2 - 3, tv_y + tv_h - 9, tv_x + tv_w // 2 + 3,
                  tv_y + tv_h - 3], fill=(79, 79, 84))

    draw.rectangle([190, 604, 1090, 632], fill=(76, 50, 35))
    draw.rectangle([190, 632, 1090, 643], fill=(52, 33, 24))
    for leg_x in (230, 1035):
        draw.rectangle([leg_x, 643, leg_x + 18, 700], fill=(55, 36, 27))
    draw.rounded_rectangle([362, 579, 918, 603], radius=8, fill=(34, 34, 37))
    for i in range(5):
        draw.ellipse([382 + i * 9, 587, 388 + i * 9, 593], fill=(68, 68, 72))

    pot = [1115, 548, 1190, 632]
    draw.polygon([(pot[0], pot[1]), (pot[2], pot[1]), (pot[2] - 8, pot[3]),
                  (pot[0] + 8, pot[3])], fill=(127, 87, 61))
    draw.rectangle([pot[0] - 4, pot[1] - 10, pot[2] + 4, pot[1] + 6], fill=(102, 70, 49))
    for angle, leaf_len in ((-72, 96), (-48, 118), (-20, 104), (8, 120), (35, 100), (62, 84)):
        radians = math.radians(angle)
        x2 = 1152 + math.cos(radians) * leaf_len
        y2 = 546 + math.sin(radians) * leaf_len
        draw.line([(1152, 546), (x2, y2)], fill=(49, 82, 55), width=7)
        draw.ellipse([x2 - 14, y2 - 8, x2 + 14, y2 + 8], fill=(61, 101, 67))
    return image, (screen_x, screen_y, screen_w, screen_h)


def make_hero(poster: Image.Image, room: Image.Image,
              screen: tuple[int, int, int, int]) -> None:
    screen_x, screen_y, screen_w, screen_h = screen
    mask = rounded_mask((screen_w, screen_h), 3)
    source_w, source_h = 1920, 1080
    max_left = poster.width - source_w
    top = (poster.height - source_h) // 2

    frames = []
    steps = 24
    for index in range(steps):
        t = index / (steps - 1)
        progress = 1 - abs(2 * t - 1)
        left = int(round(max_left * progress))
        crop = poster.crop((left, top, left + source_w, top + source_h))
        crop = crop.resize((screen_w, screen_h), Image.Resampling.LANCZOS)
        frame = room.copy()
        frame.paste(crop, (screen_x, screen_y), mask)
        frames.append(frame)

    frames[0].save(DOCS / "hero.jpg", "JPEG", quality=90, optimize=True,
                   progressive=True)
    gif_frames = [frame.resize((960, 540), Image.Resampling.LANCZOS) for frame in frames]
    hero_path = DOCS / "hero.gif"
    gif_frames[0].save(hero_path, save_all=True, append_images=gif_frames[1:], duration=220,
                       loop=0, optimize=True, disposal=2)
    print(f"Wrote {hero_path} ({hero_path.stat().st_size // 1024} KiB)")


def load_poster(path: Path) -> Image.Image:
    image = Image.open(path).convert("RGB")
    if image.size != (WIDTH, HEIGHT):
        # The service always writes this size; accept close variants for forks.
        ratio = WIDTH / HEIGHT
        source_ratio = image.width / image.height
        if abs(source_ratio - ratio) > 0.005:
            if source_ratio > ratio:
                new_width = int(round(image.height * ratio))
                left = (image.width - new_width) // 2
                image = image.crop((left, 0, left + new_width, image.height))
            else:
                new_height = int(round(image.width / ratio))
                top = (image.height - new_height) // 2
                image = image.crop((0, top, image.width, top + new_height))
        image = image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    print(f"Using real poster {path} ({image.size[0]}x{image.size[1]})")
    return image


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poster", type=Path, default=None,
                        help="Use a real generated 21:9 poster instead of the demo shelf")
    args = parser.parse_args()
    poster = load_poster(args.poster) if args.poster else render_poster()
    room, screen = make_room()
    make_hero(poster, room, screen)


if __name__ == "__main__":
    main()
