"""
Thumbnail Processor — Streaming platform dark style (Anime Metrix reference)
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


def _draw_logo_watermark(canvas: Image.Image, text: str) -> Image.Image:
    """Logo-style watermark top-right — channel name in bold with accent bar."""
    if not text:
        return canvas
    W, H  = canvas.size
    font  = _font(28)
    ov    = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od    = ImageDraw.Draw(ov)
    bbox  = od.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 18, 10
    x = W - tw - px * 2 - 12
    y = 14
    # Red accent bar on left of logo
    od.rectangle([x, y, x + 4, y + th + py * 2], fill=(220, 30, 30, 240))
    # Dark semi-transparent bg
    od.rectangle([x + 4, y, x + tw + px * 2 + 4, y + th + py * 2], fill=(10, 10, 10, 200))
    # Text
    od.text((x + px + 4, y + py), text, font=font, fill=(255, 255, 255, 255))
    return Image.alpha_composite(canvas.convert("RGBA"), ov)


def _draw_genre_tags(draw: ImageDraw.Draw, genres: str, gx: int, gy: int, max_w: int):
    """Genre tags top area — plain text separated, like reference."""
    if not genres:
        return
    items = [g.strip() for g in genres.split(",") if g.strip()][:4]
    font  = _font(22, bold=False)
    x     = gx
    for i, g in enumerate(items):
        gw = int(draw.textlength(g, font=font))
        if x + gw > gx + max_w:
            break
        draw.text((x, gy), g, font=font, fill=(210, 210, 210, 200))
        x += gw
        if i < len(items) - 1:
            draw.text((x, gy), "   •   ", font=font, fill=(150, 150, 150, 160))
            x += int(draw.textlength("   •   ", font=font))


def _build_card(
    poster: Image.Image,
    backdrop: Optional[Image.Image],
    watermark: str,
    meta: dict,
) -> Image.Image:
    W, H = _SIZE

    # ── Very dark base ────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (W, H), (14, 14, 20, 255))

    # Full blurred backdrop — very dark
    bg = (backdrop or poster).convert("RGBA").resize((W, H), Image.LANCZOS)
    bg = bg.filter(ImageFilter.GaussianBlur(8))
    bg = ImageEnhance.Brightness(bg).enhance(0.22)
    canvas.paste(bg.convert("RGBA"), (0, 0))

    # Character art — right side, larger, slightly visible
    char_img = poster.convert("RGBA")
    char_h   = int(H * 1.05)
    char_w   = int(char_h * char_img.width / char_img.height)
    char_img = char_img.resize((char_w, char_h), Image.LANCZOS)
    # Position right side, slightly cut off at bottom
    char_x = W - char_w + int(char_w * 0.08)
    char_y = -int(H * 0.04)
    # Fade left edge of character
    fade = Image.new("RGBA", char_img.size, (0, 0, 0, 0))
    fade_w = int(char_w * 0.45)
    for i in range(fade_w):
        alpha = int(255 * (i / fade_w) ** 1.6)
        for yy in range(char_img.height):
            r2, g2, b2, a2 = char_img.getpixel((i, yy))
            char_img.putpixel((i, yy), (r2, g2, b2, min(a2, alpha)))
    # Fade bottom edge
    fade_bot = int(char_h * 0.18)
    for j in range(fade_bot):
        alpha = int(255 * (j / fade_bot))
        yy    = char_h - fade_bot + j
        if yy < char_h:
            for xi in range(char_w):
                r2, g2, b2, a2 = char_img.getpixel((xi, yy))
                char_img.putpixel((xi, yy), (r2, g2, b2, min(a2, alpha)))
    if char_x < W and char_y < H:
        canvas.paste(char_img, (char_x, char_y), char_img)

    # Left dark gradient so text is always readable
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd   = ImageDraw.Draw(grad)
    for i in range(W):
        # Strong on left, fades out toward right
        alpha = max(0, int(200 - (i / W) * 220))
        gd.line([(i, 0), (i, H)], fill=(8, 8, 14, alpha))
    canvas = Image.alpha_composite(canvas, grad)

    draw = ImageDraw.Draw(canvas)

    title    = meta.get("title", "").upper()
    year     = str(meta.get("year", ""))
    rating   = meta.get("imdb_rating") or meta.get("rating", "")
    status   = meta.get("status", "")
    episodes = str(meta.get("episodes", ""))
    seasons  = str(meta.get("seasons", ""))
    genres   = meta.get("genres", "")
    overview = meta.get("overview") or meta.get("synopsis", "")
    category = meta.get("_category", "")
    runtime  = meta.get("runtime", "")

    left_x  = 60
    title_y = 160
    text_w  = int(W * 0.48)

    # ── Genre tags — top area ─────────────────────────────────────────────────
    _draw_genre_tags(draw, genres, left_x, 100, text_w)

    # ── Title — large bold white ──────────────────────────────────────────────
    tf    = _font(68)
    tlines = _wrap(title, tf, draw, text_w)[:3]
    y      = title_y
    for ln in tlines:
        draw.text((left_x, y), ln, font=tf, fill=(255, 255, 255, 255))
        y += 78

    y += 16

    # ── Description ───────────────────────────────────────────────────────────
    if overview:
        df = _font(24, bold=False)
        for ln in _wrap(overview, df, draw, text_w)[:3]:
            draw.text((left_x, y), ln, font=df, fill=(190, 190, 200, 210))
            y += 32
    y += 24

    # ── Two buttons — DOWNLOAD (outline) + WATCH NOW (red filled) ─────────────
    btn_font = _font(22)
    btn_h    = 48
    btn_gap  = 14

    # DOWNLOAD button — outline style
    dl_label = "DOWNLOAD"
    dl_w     = int(draw.textlength(dl_label, font=btn_font)) + 48
    draw.rectangle([left_x, y, left_x + dl_w, y + btn_h], outline=(200, 200, 200, 200), width=2)
    dl_tx = left_x + (dl_w - int(draw.textlength(dl_label, font=btn_font))) // 2
    draw.text((dl_tx, y + 12), dl_label, font=btn_font, fill=(220, 220, 220, 240))

    # WATCH NOW button — red filled
    wn_label = "WATCH NOW"
    wn_x     = left_x + dl_w + btn_gap
    wn_w     = int(draw.textlength(wn_label, font=btn_font)) + 48
    draw.rectangle([wn_x, y, wn_x + wn_w, y + btn_h], fill=(210, 25, 25, 255))
    wn_tx = wn_x + (wn_w - int(draw.textlength(wn_label, font=btn_font))) // 2
    draw.text((wn_tx, y + 12), wn_label, font=btn_font, fill=(255, 255, 255, 255))

    # ── Episode info card — bottom right ─────────────────────────────────────
    card_w, card_h = 340, 120
    card_x = W - card_w - 36
    card_y = H - card_h - 36

    # Card bg
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    cd   = ImageDraw.Draw(card)
    cd.rounded_rectangle([0, 0, card_w, card_h], radius=12, fill=(20, 20, 28, 220))
    cd.rounded_rectangle([0, 0, card_w, card_h], radius=12, outline=(60, 60, 80, 180), width=1)

    # Thumbnail placeholder inside card
    thumb_w, thumb_h = 90, card_h - 20
    thumb_x = card_w - thumb_w - 10
    thumb_y = 10
    if backdrop or poster:
        th_img = (backdrop or poster).convert("RGBA").resize((thumb_w, thumb_h), Image.LANCZOS)
        th_mask = Image.new("L", (thumb_w, thumb_h), 0)
        ImageDraw.Draw(th_mask).rounded_rectangle([0, 0, thumb_w, thumb_h], radius=8, fill=255)
        card.paste(th_img, (thumb_x, thumb_y), th_mask)

    # Episode text
    ep_num  = f"Episode - {episodes.zfill(2) if episodes not in ('?','N/A','None','') else '01'}"
    ep_font = _font(26)
    cd.text((14, 16), ep_num, font=ep_font, fill=(255, 255, 255, 255))

    if seasons and seasons not in ("N/A", "None", ""):
        cd.text((14, 50), f"Season - {seasons.zfill(2)}", font=_font(20, bold=False), fill=(180, 180, 190, 220))

    rt_text = runtime if runtime and runtime not in ("N/A", "") else ("24m" if category == "anime" else "")
    if rt_text:
        cd.text((14, 76), f"Duration - {rt_text}", font=_font(20, bold=False), fill=(180, 180, 190, 220))

    canvas.paste(card, (card_x, card_y), card)

    # ── Logo watermark ────────────────────────────────────────────────────────
    canvas = _draw_logo_watermark(canvas, watermark)

    return canvas.convert("RGB")


async def build_thumbnail(
    poster_url: Optional[str],
    backdrop_url: Optional[str] = None,
    watermark: str = "",
    meta: dict = {},
) -> bytes:
    os.makedirs("temp", exist_ok=True)
    poster   = (await _fetch(poster_url)) if poster_url else None
    if poster is None:
        poster = Image.new("RGBA", (400, 600), (30, 30, 42, 255))
        ImageDraw.Draw(poster).text((60, 280), "No Image", fill=(120, 120, 140), font=_font(28))
    backdrop = (await _fetch(backdrop_url)) if backdrop_url else None
    card     = _build_card(poster, backdrop, watermark, meta)
    buf      = io.BytesIO()
    card.save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()


async def process_custom_thumbnail(photo_bytes: bytes, watermark: str = "") -> bytes:
    img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA").resize(_SIZE, Image.LANCZOS)
    canvas = _draw_logo_watermark(img.convert("RGBA"), watermark)
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=93, optimize=True)
    return buf.getvalue()