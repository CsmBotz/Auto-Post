"""
Thumbnail Processor — White card style (light bg, dark text, colored right panel)
matching the reference image layout but keeping poster on left.
"""
import io
import os
import logging
import aiohttp
from typing import Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

logger = logging.getLogger(__name__)

_FONT_BOLD = "assets/fonts/DejaVuSans-Bold.ttf"
_FONT_REG  = "assets/fonts/DejaVuSans.ttf"
_SIZE      = (1280, 720)


async def _fetch(url: str) -> Optional[Image.Image]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception as e:
        logger.error(f"Image fetch failed: {e}")
    return None


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    path = _FONT_BOLD if bold else _FONT_REG
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        try:
            return ImageFont.truetype(_FONT_BOLD, size)
        except Exception:
            return ImageFont.load_default()


def _wrap(text: str, font, draw, max_w: int) -> list:
    words = text.split()
    lines, line = [], []
    for w in words:
        if draw.textlength(" ".join(line + [w]), font=font) > max_w:
            if line:
                lines.append(" ".join(line))
            line = [w]
        else:
            line.append(w)
    if line:
        lines.append(" ".join(line))
    return lines


def _watermark(img: Image.Image, text: str) -> Image.Image:
    """Outline pill — top right, white border, white text (visible on both light/dark)."""
    if not text:
        return img
    img  = img.convert("RGBA")
    W, H = img.size
    font = _font(26)
    ov   = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od   = ImageDraw.Draw(ov)
    bbox = od.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    m  = 14
    x  = W - tw - m * 2 - 12
    y  = 12
    # Semi-dark pill so text is readable on white background too
    od.rounded_rectangle(
        [x, y, x + tw + m * 2, y + th + m * 2],
        radius=10,
        fill=(0, 0, 0, 140),
        outline=(255, 255, 255, 220),
        width=2,
    )
    od.text((x + m, y + m), text, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(img, ov).convert("RGB")


def _watch_button(canvas: Image.Image, category: str) -> Image.Image:
    """Outline pill button bottom-right."""
    label = "Read Now" if category == "manhwa" else "Watch Now"
    W, H  = canvas.size
    font  = _font(26)
    ov    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od    = ImageDraw.Draw(ov)
    bbox  = od.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 28, 12
    bw = tw + px * 2
    bh = th + py * 2
    x  = W - bw - 32
    y  = H - bh - 32
    od.rounded_rectangle(
        [x, y, x + bw, y + bh],
        radius=bh // 2,
        fill=(0, 0, 0, 160),
        outline=(255, 255, 255, 200),
        width=2,
    )
    od.text((x + px, y + py), label, font=font, fill=(255, 255, 255, 245))
    return Image.alpha_composite(canvas.convert("RGBA"), ov).convert("RGBA")


def _build_card(poster: Image.Image, backdrop: Optional[Image.Image], watermark: str, meta: dict) -> Image.Image:
    W, H = _SIZE

    # ── WHITE card background ─────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (248, 248, 252, 255))

    # Very subtle blurred backdrop tint on the right half only
    bg_src = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg_src = bg_src.filter(ImageFilter.GaussianBlur(50))
    bg_src = ImageEnhance.Brightness(bg_src).enhance(1.8)
    bg_src = ImageEnhance.Color(bg_src).enhance(0.15)
    # Paste only the right 60% and fade it in
    right_x = int(W * 0.38)
    right_crop = bg_src.crop((right_x, 0, W, H)).convert("RGBA")
    # Apply a left-to-right alpha fade so it blends into white
    fade_w = 220
    for i in range(fade_w):
        alpha = int(255 * (i / fade_w))
        for yy in range(H):
            if i < right_crop.width:
                r, g, b, a = right_crop.getpixel((i, yy))
                right_crop.putpixel((i, yy), (r, g, b, min(a, alpha)))
    canvas.paste(right_crop, (right_x, 0), right_crop)

    # ── Poster shadow ─────────────────────────────────────────────────────────
    ph = int(H * 0.84)
    pw = int(ph * 2 / 3)
    px, py = 48, (H - ph) // 2

    sh = Image.new("RGBA", (pw + 40, ph + 40), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([8, 8, pw + 32, ph + 32], radius=18, fill=(0, 0, 0, 60))
    sh = sh.filter(ImageFilter.GaussianBlur(16))
    canvas.paste(sh, (px - 10, py - 2), sh)

    # ── Poster ────────────────────────────────────────────────────────────────
    pr   = poster.convert("RGBA").resize((pw, ph), Image.LANCZOS)
    mask = Image.new("L", (pw, ph), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw, ph], radius=14, fill=255)
    canvas.paste(pr, (px, py), mask)

    # ── Gold accent line ──────────────────────────────────────────────────────
    ax = px + pw + 26
    draw = ImageDraw.Draw(canvas)
    draw.line([(ax, py + 12), (ax, py + ph - 12)], fill=(210, 160, 20, 230), width=4)

    # ── Info panel ────────────────────────────────────────────────────────────
    rx = ax + 28
    ry = py + 18
    rw = W - rx - 40

    title    = meta.get("title", "")
    year     = str(meta.get("year", ""))
    rating   = meta.get("imdb_rating") or meta.get("rating", "")
    status   = meta.get("status", "")
    episodes = str(meta.get("episodes", ""))
    seasons  = str(meta.get("seasons", ""))
    genres   = meta.get("genres", "")
    overview = meta.get("overview") or meta.get("synopsis", "")
    category = meta.get("_category", "")

    y = ry

    # Title — large, very dark
    tf = _font(50)
    for ln in _wrap(title, tf, draw, rw)[:2]:
        draw.text((rx, y), ln, font=tf, fill=(18, 18, 22, 255))
        y += 58
    y += 4

    # Separator
    draw.line([(rx, y), (rx + rw, y)], fill=(180, 180, 190, 160), width=1)
    y += 14

    # Year + Rating on same line
    ix = rx
    if year:
        draw.text((ix, y), f"📅 {year}", font=_font(26, bold=False), fill=(90, 90, 100, 230))
        ix += int(draw.textlength(f"📅 {year}", font=_font(26, bold=False))) + 28
    if rating and str(rating) not in ("N/A", "0", "", "0%"):
        draw.text((ix, y), f"⭐ {rating}", font=_font(26), fill=(190, 130, 0, 255))
    y += 38

    # Status — green
    if status and status not in ("N/A", ""):
        draw.text((rx, y), f"📡 {status}", font=_font(24, bold=False), fill=(20, 130, 60, 240))
        y += 34

    # Episodes / Seasons
    if episodes and episodes not in ("N/A", "?", "None", ""):
        draw.text((rx, y), f"🎬 Episodes: {episodes}", font=_font(23, bold=False), fill=(60, 60, 70, 210))
        y += 30
    if seasons and seasons not in ("N/A", "None", ""):
        draw.text((rx, y), f"📺 Seasons: {seasons}", font=_font(23, bold=False), fill=(60, 60, 70, 210))
        y += 30

    y += 8

    # Genre pills — dark fill like reference image
    if genres:
        gx        = rx
        pill_font = _font(20, bold=False)
        for g in [g.strip() for g in genres.split(",") if g.strip()][:4]:
            gw = int(draw.textlength(g, font=pill_font)) + 22
            if gx + gw > rx + rw:
                break
            pill = Image.new("RGBA", (gw, 32), (0, 0, 0, 0))
            pd   = ImageDraw.Draw(pill)
            pd.rounded_rectangle([0, 0, gw, 32], radius=8, fill=(30, 22, 8, 220))
            pd.text((11, 6), g, font=pill_font, fill=(220, 175, 50, 255))
            canvas.paste(pill, (gx, y), pill)
            gx += gw + 8
        y += 42

    y += 4

    # Description — 3 lines, medium grey on white
    if overview:
        df = _font(21, bold=False)
        for ln in _wrap(overview, df, draw, rw)[:3]:
            draw.text((rx, y), ln, font=df, fill=(80, 80, 90, 200))
            y += 27

    # Watch Now / Read Now
    canvas = _watch_button(canvas, category)

    return _watermark(canvas.convert("RGB"), watermark)


async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    meta: dict = {},
) -> bytes:
    os.makedirs("temp", exist_ok=True)
    poster   = (await _fetch(poster_url)) if poster_url else None
    if poster is None:
        poster = Image.new("RGBA", (400, 600), (220, 220, 228, 255))
        ImageDraw.Draw(poster).text((80, 280), "No Image", fill=(140, 140, 150), font=_font(28))
    backdrop = (await _fetch(backdrop_url)) if backdrop_url else None
    card     = _build_card(poster, backdrop, watermark, meta)
    buf      = io.BytesIO()
    card.save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(photo_bytes: bytes, watermark: str = "") -> bytes:
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize(_SIZE, Image.LANCZOS)
    img = _watermark(img, watermark)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()
