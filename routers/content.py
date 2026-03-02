import io
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from fetchers.tmdb import TMDbFetcher
from fetchers.jikan import JikanFetcher
from fetchers.anilist import AniListFetcher
from formatter.engine import FormatEngine
from thumbnail.processor import build_thumbnail, process_custom_thumbnail
from utils.fsm import fsm
from utils.helpers import (
    extract_query, search_kb, thumbnail_kb, preview_kb,
    template_kb, add_button_start_kb, button_manage_kb,
)

logger = logging.getLogger(__name__)
router = Router()

_tmdb    = TMDbFetcher()
_jikan   = JikanFetcher()
_anilist = AniListFetcher()
_fmt     = FormatEngine()

FETCHERS = {
    "movie":  (_tmdb.search_movies,    _tmdb.get_movie,      "movie"),
    "tvshow": (_tmdb.search_tv,        _tmdb.get_tv,         "tv"),
    "anime":  (_jikan.search_anime,    _jikan.get_anime,     "anime"),
    "manhwa": (_anilist.search_manhwa, _anilist.get_manhwa,  "manhwa"),
}
EXAMPLES = {
    "movie": "Inception", "tvshow": "Breaking Bad",
    "anime": "Attack on Titan", "manhwa": "Solo Leveling",
}
PREFIX_TO_CAT = {"movie": "movie", "tv": "tvshow", "anime": "anime", "manhwa": "manhwa"}
CAT_TO_PREFIX = {"movie": "movie", "tvshow": "tv", "anime": "anime", "manhwa": "manhwa"}


def build_post_keyboard(buttons: list) -> InlineKeyboardMarkup | None:
    if not buttons:
        return None
    kb = InlineKeyboardBuilder()
    for btn in buttons:
        if btn.get("url"):
            kb.button(text=btn["text"], url=btn["url"])
        elif btn.get("callback_data"):
            kb.button(text=btn["text"], callback_data=btn["callback_data"])
    kb.adjust(2)
    return kb.as_markup()


# ── Preview builder ───────────────────────────────────────────────────────────

async def _build_preview_data(user_id: int):
    state = await fsm.get(user_id)
    if not state:
        return None
    meta         = state.get("meta", {})
    category     = state.get("category", "movie")
    custom_image = state.get("custom_image")
    settings     = await CosmicBotz.get_user_settings(user_id)
    watermark    = settings.get("watermark", "")
    tpl_body     = await CosmicBotz.get_active_template(user_id)

    caption = _fmt.render(category, meta, template=tpl_body, user_settings=settings)

    if custom_image:
        thumb = await process_custom_thumbnail(custom_image, watermark=watermark)
    else:
        thumb = await build_thumbnail(
            poster_url=meta.get("poster"),
            backdrop_url=meta.get("backdrop") or meta.get("banner"),
            watermark=watermark,
            meta={**meta, "_category": category},
        )

    prefix = CAT_TO_PREFIX[category]
    await fsm.update(user_id, {"caption": caption, "thumb": thumb, "step": "post"})
    return caption, thumb, prefix


async def _show_preview(cb: CallbackQuery):
    user_id = cb.from_user.id
    result  = await _build_preview_data(user_id)
    if not result:
        try:
            await cb.message.edit_text("❌ Session expired. Start again with /movie, /anime etc.")
        except Exception:
            await cb.message.answer("❌ Session expired. Start again with /movie, /anime etc.")
        return
    caption, thumb, prefix = result
    try:
        await cb.message.delete()
    except Exception:
        pass
    await cb.bot.send_photo(
        chat_id=cb.message.chat.id,
        photo=BufferedInputFile(thumb, filename="thumb.jpg"),
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


async def _show_preview_from_message(msg: Message, user_id: int):
    result = await _build_preview_data(user_id)
    if not result:
        await msg.edit_text("❌ Session expired. Start again.")
        return
    caption, thumb, prefix = result
    try:
        await msg.delete()
    except Exception:
        pass
    await msg.bot.send_photo(
        chat_id=msg.chat.id,
        photo=BufferedInputFile(thumb, filename="thumb.jpg"),
        caption=caption,
        reply_markup=preview_kb(prefix),
    )


# ── Search commands ───────────────────────────────────────────────────────────

async def _search(message: Message, category: str):
    query = extract_query(message.text)
    if not query:
        await message.answer(
            f"<b>Usage:</b> <code>/{category} title</code>\n"
            f"<b>Example:</b> <code>/{category} {EXAMPLES[category]}</code>"
        )
        return
    msg = await message.answer(f"🔍 Searching <b>{query}</b>...")
    search_fn, _, _ = FETCHERS[category]
    try:
        results = await search_fn(query)
    except Exception as e:
        logger.error(f"Search [{category}] error: {e}")
        results = []
    if not results:
        await msg.edit_text(
            f"❌ No results for <b>{query}</b>.\n"
            "Try a different spelling or shorter title."
        )
        return
    prefix = CAT_TO_PREFIX[category]
    await fsm.set(message.from_user.id, {"category": category, "step": "select"})
    await msg.edit_text(
        f"🔎 <b>{len(results)} results</b> for <b>{query}</b> — choose one:",
        reply_markup=search_kb(results, prefix),
    )


@router.message(Command("movie", "tvshow", "anime", "manhwa"))
async def cmd_category(message: Message):
    # Handle /command@BotUsername properly
    raw = message.text.lstrip("/").split()[0]
    category = raw.split("@")[0].lower()
    if category not in FETCHERS:
        return
    await _search(message, category)


# ── Select result ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_select_(\d+)$"))
async def cb_select(cb: CallbackQuery):
    await cb.answer()
    parts      = cb.data.split("_select_")
    raw_prefix = parts[0]
    item_id    = int(parts[1])
    category   = PREFIX_TO_CAT.get(raw_prefix)
    if not category:
        return

    _, detail_fn, _ = FETCHERS[category]
    await cb.message.edit_text("⏳ Fetching details...")
    try:
        meta = await detail_fn(item_id)
    except Exception as e:
        logger.error(f"Detail [{category}] {item_id}: {e}")
        meta = None

    if not meta:
        await cb.message.edit_text("❌ Could not fetch details. Please try again.")
        return

    await fsm.set(cb.from_user.id, {"category": category, "meta": meta, "step": "thumbnail"})
    await cb.message.edit_text(
        f"🖼 <b>{meta.get('title', 'Unknown')}</b> ready!\n\n"
        "📸 Send a <b>custom thumbnail</b> or tap <b>Skip</b> to use auto poster.",
        reply_markup=thumbnail_kb(CAT_TO_PREFIX[category]),
    )


# ── Thumbnail ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_thumb_skip$"))
async def cb_skip_thumb(cb: CallbackQuery):
    await cb.answer()
    await fsm.update(cb.from_user.id, {"step": "preview", "custom_image": None})
    await cb.message.edit_text("⏳ Building preview...")
    await _show_preview(cb)


@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    state   = await fsm.get(user_id)
    if not state or state.get("step") != "thumbnail":
        return
    wait = await message.answer("✅ Thumbnail received! Building preview...")
    try:
        file = await message.bot.get_file(message.photo[-1].file_id)
        buf  = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=buf)
        await fsm.update(user_id, {"step": "preview", "custom_image": buf.getvalue()})
        await _show_preview_from_message(wait, user_id)
    except Exception as e:
        logger.error(f"Photo download error: {e}")
        await wait.edit_text("❌ Failed to process image. Try again or use Skip.")


# ── Post to channel (direct, no buttons) ─────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_channel$"))
async def cb_post_channel(cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    state    = await fsm.get(user_id)
    if not state or not state.get("thumb"):
        await cb.answer("❌ Session expired. Generate again.", show_alert=True)
        return
    settings = await CosmicBotz.get_user_settings(user_id)
    channel  = settings.get("channel_id")
    if not channel:
        await cb.answer("⚠️ No channel set! Go to /settings → Channel.", show_alert=True)
        return
    try:
        await cb.bot.send_photo(
            chat_id=channel,
            photo=BufferedInputFile(state["thumb"], filename="thumb.jpg"),
            caption=state["caption"],
        )
        await CosmicBotz.increment_post_count(user_id)
        await fsm.clear(user_id)
        await cb.answer("✅ Posted to channel!", show_alert=True)
        try:
            await cb.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Post failed: {e}")
        await cb.answer(f"❌ Post failed: {e}", show_alert=True)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_direct$"))
async def cb_post_direct(cb: CallbackQuery):
    """Post from button manager without inline buttons."""
    await cb_post_channel(cb)


# ── Copy caption ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_post_copy$"))
async def cb_copy(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    await cb.message.answer(f"📋 <b>Caption:</b>\n\n{state.get('caption', '')}")
    await CosmicBotz.increment_post_count(cb.from_user.id)


# ── Template picker ───────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_change_tpl$"))
async def cb_change_tpl(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    templates = await CosmicBotz.list_user_templates(cb.from_user.id)
    prefix    = CAT_TO_PREFIX[state.get("category", "movie")]
    await cb.message.edit_caption(
        caption="📄 <b>Select a Template:</b>",
        reply_markup=template_kb(templates, prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_tpl_(.+)$"))
async def cb_tpl_pick(cb: CallbackQuery):
    await cb.answer()
    user_id  = cb.from_user.id
    tpl_name = cb.data.split("_tpl_", 1)[1]
    if tpl_name == "default":
        await CosmicBotz.update_user_settings(user_id, {"active_template": "default"})
    else:
        tpl = await CosmicBotz.get_template(user_id, tpl_name)
        if tpl:
            await CosmicBotz.update_user_settings(user_id, {"active_template": tpl_name})
        else:
            await cb.answer("Template not found.", show_alert=True)
            return
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_back_preview$"))
async def cb_back_preview(cb: CallbackQuery):
    await cb.answer()
    await _show_preview(cb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_redo_thumb$"))
async def cb_redo_thumb(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    await fsm.update(cb.from_user.id, {"step": "thumbnail"})
    prefix = CAT_TO_PREFIX[state.get("category", "movie")]
    await cb.message.edit_caption(
        caption="📸 Send a new thumbnail or tap Skip:",
        reply_markup=thumbnail_kb(prefix),
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_cancel$"))
async def cb_cancel(cb: CallbackQuery):
    await cb.answer("Cancelled.")
    await fsm.clear(cb.from_user.id)
    try:
        await cb.message.delete()
    except Exception:
        pass


# ── BUTTON FLOW ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_start$"))
async def cb_btn_start(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    buttons = state.get("buttons", [])
    prefix  = CAT_TO_PREFIX[state.get("category", "movie")]
    text = (
        "🔗 <b>Inline Buttons Manager</b>\n\n"
        "Add buttons that appear below your post in the channel.\n\n"
        + (
            "<b>Current buttons:</b>\n" + "\n".join(f"  {i+1}. {b['text']}" for i, b in enumerate(buttons))
            if buttons else "<i>No buttons added yet.</i>"
        )
    )
    kb = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    await cb.message.edit_caption(caption=text, reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_add$"))
async def cb_btn_add(cb: CallbackQuery):
    await cb.answer()
    state = await fsm.get(cb.from_user.id)
    if not state:
        return
    await fsm.update(cb.from_user.id, {"step": "btn_name"})
    await cb.message.edit_caption(
        caption=(
            "🏷 <b>Step 1 of 2 — Button Label</b>\n\n"
            "Send the <b>text</b> that will show on the button.\n\n"
            "<b>Examples:</b>\n"
            "▶️ Watch Now\n"
            "📖 Read Online\n"
            "🎬 Trailer\n"
            "⭐ Rate It\n"
            "🔔 Join Channel\n\n"
            "<i>Emojis, fancy text and symbols all allowed!</i>"
        ),
        reply_markup=None,
    )


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_del_(\d+)$"))
async def cb_btn_delete(cb: CallbackQuery):
    await cb.answer()
    uid     = cb.from_user.id
    idx     = int(cb.data.split("_btn_del_")[1])
    state   = await fsm.get(uid)
    if not state:
        return
    buttons = list(state.get("buttons", []))
    if 0 <= idx < len(buttons):
        removed = buttons.pop(idx)
        await fsm.update(uid, {"buttons": buttons})
        await cb.answer(f"🗑 Removed: {removed['text']}")
    prefix = CAT_TO_PREFIX[state.get("category", "movie")]
    text = (
        "🔗 <b>Inline Buttons Manager</b>\n\n"
        + (
            "<b>Current buttons:</b>\n" + "\n".join(f"  {i+1}. {b['text']}" for i, b in enumerate(buttons))
            if buttons else "<i>No buttons yet.</i>"
        )
    )
    kb = button_manage_kb(prefix, buttons) if buttons else add_button_start_kb(prefix)
    await cb.message.edit_caption(caption=text, reply_markup=kb)


@router.callback_query(F.data.regexp(r"^(movie|tv|anime|manhwa)_btn_done$"))
async def cb_btn_done(cb: CallbackQuery):
    await cb.answer()
    uid   = cb.from_user.id
    state = await fsm.get(uid)
    if not state or not state.get("thumb"):
        await cb.answer("❌ Session expired.", show_alert=True)
        return
    settings = await CosmicBotz.get_user_settings(uid)
    channel  = settings.get("channel_id")
    if not channel:
        await cb.answer("⚠️ No channel set! Use /settings first.", show_alert=True)
        return
    buttons = state.get("buttons", [])
    try:
        await cb.bot.send_photo(
            chat_id=channel,
            photo=BufferedInputFile(state["thumb"], filename="thumb.jpg"),
            caption=state["caption"],
            reply_markup=build_post_keyboard(buttons),
        )
        await CosmicBotz.increment_post_count(uid)
        await fsm.clear(uid)
        note = f" with {len(buttons)} button(s)" if buttons else ""
        await cb.answer(f"✅ Posted{note}!", show_alert=True)
        try:
            await cb.message.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Post with buttons failed: {e}")
        await cb.answer(f"❌ {e}", show_alert=True)


# ── SINGLE TEXT HANDLER — handles ALL user text input steps ──────────────────
# This is the ONLY F.text handler in the entire bot.
# settings.py and templates.py have NO text handlers — they set fsm step,
# then this handler picks it up.

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_input(message: Message):
    uid   = message.from_user.id
    state = await fsm.get(uid)
    if not state:
        return
    step = state.get("step", "")
    text = message.text.strip()

    # ── Button name ───────────────────────────────────────────────────────────
    if step == "btn_name":
        if len(text) > 64:
            await message.answer("⚠️ Button label too long (max 64 chars). Try again:")
            return
        await fsm.update(uid, {"step": "btn_url", "pending_btn_name": text})
        await message.answer(
            f"🔗 <b>Step 2 of 2 — Button URL</b>\n\n"
            f"Label: <b>{text}</b>\n\n"
            "Now send the <b>URL</b> for this button:\n\n"
            "<code>https://t.me/yourchannel</code>\n"
            "<code>https://youtube.com/watch?v=...</code>\n"
            "<code>https://mangadex.org/title/...</code>"
        )

    # ── Button URL ────────────────────────────────────────────────────────────
    elif step == "btn_url":
        if not (text.startswith("http://") or text.startswith("https://")):
            await message.answer(
                "⚠️ Must be a valid URL starting with <code>https://</code>\nTry again:"
            )
            return
        btn_name = state.get("pending_btn_name", "Button")
        buttons  = list(state.get("buttons", []))
        if len(buttons) >= 8:
            await message.answer("⚠️ Maximum 8 buttons allowed.")
            await fsm.update(uid, {"step": "post", "pending_btn_name": None})
            return
        buttons.append({"text": btn_name, "url": text})
        category = state.get("category", "movie")
        prefix   = CAT_TO_PREFIX[category]
        await fsm.update(uid, {"step": "post", "buttons": buttons, "pending_btn_name": None})
        btn_list = "\n".join(f"  {i+1}. {b['text']}" for i, b in enumerate(buttons))
        await message.answer(
            f"✅ <b>Button added! ({len(buttons)}/8)</b>\n\n"
            f"<b>Buttons:</b>\n{btn_list}",
            reply_markup=button_manage_kb(prefix, buttons),
        )

    # ── Watermark ─────────────────────────────────────────────────────────────
    elif step == "cfg_watermark":
        await CosmicBotz.upsert_user(uid, "", "")
        if text.lower() == "clear":
            await CosmicBotz.update_user_settings(uid, {"watermark": ""})
            await message.answer("✅ Watermark cleared.")
        else:
            await CosmicBotz.update_user_settings(uid, {"watermark": text})
            await message.answer(f"✅ Watermark set to <code>{text}</code>")
        await fsm.clear(uid)

    # ── Channel ───────────────────────────────────────────────────────────────
    elif step == "cfg_channel":
        if not (text.startswith("@") or text.lstrip("-").isdigit()):
            await message.answer(
                "❌ Use <code>@channel</code> format or a numeric chat ID. Try again:"
            )
            return
        await CosmicBotz.upsert_user(uid, "", "")
        await CosmicBotz.update_user_settings(uid, {"channel_id": text})
        await message.answer(
            f"✅ Channel linked: <code>{text}</code>\n"
            "Make sure the bot is admin in that channel!"
        )
        await fsm.clear(uid)

    # ── Template name ─────────────────────────────────────────────────────────
    elif step == "tpl_name":
        if " " in text or len(text) > 32:
            await message.answer("❌ No spaces, max 32 chars. Try again:")
            return
        await fsm.update(uid, {"step": "tpl_body", "tpl_name": text})
        await message.answer(
            f"✅ Name: <b>{text}</b>\n\n"
            "Now send the <b>template body</b>.\n"
            "Must include <code>{title}</code>.\n\n"
            "Available tokens: <code>{title}</code> <code>{year}</code> "
            "<code>{rating}</code> <code>{genres}</code> etc."
        )

    # ── Template body ─────────────────────────────────────────────────────────
    elif step == "tpl_body":
        if "{title}" not in text:
            await message.answer("⚠️ Template must contain <code>{title}</code>. Try again:")
            return
        name = state.get("tpl_name", "unnamed")
        await CosmicBotz.save_template(uid, name, text)
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await fsm.clear(uid)
        await message.answer(
            f"✅ <b>Template '{name}' saved and activated!</b>\n"
            "Use /templates to manage your templates."
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────
    elif step == "adm_broadcast":
        from routers.admin import do_broadcast
        await do_broadcast(message, text)
