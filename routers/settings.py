from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm
import config as cfg

router = Router()


def settings_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🖋 Watermark",  callback_data="cfg_watermark")
    kb.button(text="📺 Channel",    callback_data="cfg_channel")
    kb.button(text="🎞 Quality",    callback_data="cfg_quality")
    kb.button(text="🔊 Audio",      callback_data="cfg_audio")
    kb.button(text="📋 Templates",  callback_data="cfg_templates")
    kb.button(text="📊 My Stats",   callback_data="cfg_stats")
    kb.button(text="❌ Close",       callback_data="cfg_close")
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def quality_kb():
    kb = InlineKeyboardBuilder()
    for q in ["480p", "720p", "1080p", "4K", "480p | 720p | 1080p"]:
        kb.button(text=q, callback_data=f"cfg_setquality|{q}")
    kb.button(text="🔙 Back", callback_data="cfg_open")
    kb.adjust(3, 1, 1)
    return kb.as_markup()


def audio_kb():
    kb = InlineKeyboardBuilder()
    for a in ["Hindi", "English", "Hindi | English", "Multi Audio"]:
        kb.button(text=a, callback_data=f"cfg_setaudio|{a}")
    kb.button(text="🔙 Back", callback_data="cfg_open")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


async def _show_settings(uid: int, target):
    """Works for both Message and CallbackQuery message."""
    await CosmicBotz.upsert_user(uid, "", "")
    s    = await CosmicBotz.get_user_settings(uid)
    user = await CosmicBotz.get_user(uid)
    plan = "⭐ Premium" if user and user.get("is_premium") else "Free"
    text = (
        f"⚙️ <b>Settings</b>  <code>[{plan}]</code>\n\n"
        f"🖋 Watermark:  <code>{s.get('watermark') or 'Not set'}</code>\n"
        f"📺 Channel:    <code>{s.get('channel_id') or 'Not set'}</code>\n"
        f"🎞 Quality:    <code>{s.get('quality', cfg.DEFAULT_QUALITY)}</code>\n"
        f"🔊 Audio:      <code>{s.get('audio', cfg.DEFAULT_AUDIO)}</code>\n"
        f"📋 Template:   <code>{s.get('active_template', 'default')}</code>"
    )
    if isinstance(target, Message):
        await target.answer(text, reply_markup=settings_kb())
    else:
        try:
            await target.edit_text(text, reply_markup=settings_kb())
        except Exception:
            await target.answer(text, reply_markup=settings_kb())


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await _show_settings(message.from_user.id, message)


@router.message(Command("setwatermark"))
async def cmd_setwatermark(message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_watermark"})
    await message.answer(
        "🖋 <b>Set Watermark</b>\n\n"
        "Send your watermark text (e.g. <code>@YourChannel</code>)\n"
        "Send <code>clear</code> to remove it."
    )


@router.message(Command("setchannel"))
async def cmd_setchannel(message: Message):
    await fsm.set(message.from_user.id, {"step": "cfg_channel"})
    await message.answer(
        "📺 <b>Set Channel</b>\n\n"
        "Send your channel username or numeric ID.\n"
        "Example: <code>@MyAnimeChannel</code>\n\n"
        "⚠️ Make sure the bot is <b>admin</b> in your channel first!"
    )


@router.callback_query(F.data.startswith("cfg_"))
async def cfg_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "cfg_open":
        await _show_settings(uid, cb.message)

    elif data == "cfg_watermark":
        await fsm.set(uid, {"step": "cfg_watermark"})
        await cb.message.edit_text(
            "🖋 <b>Set Watermark</b>\n\nSend your watermark text or <code>clear</code> to remove."
        )

    elif data == "cfg_channel":
        await fsm.set(uid, {"step": "cfg_channel"})
        await cb.message.edit_text(
            "📺 <b>Set Channel</b>\n\nSend <code>@channel</code> or numeric ID.\n"
            "⚠️ Bot must be admin in the channel!"
        )

    elif data == "cfg_quality":
        await cb.message.edit_text("🎞 <b>Select Default Quality:</b>", reply_markup=quality_kb())

    elif data == "cfg_audio":
        await cb.message.edit_text("🔊 <b>Select Default Audio:</b>", reply_markup=audio_kb())

    elif data.startswith("cfg_setquality|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"quality": val})
        await cb.answer("✅ Quality updated!", show_alert=True)
        await _show_settings(uid, cb.message)

    elif data.startswith("cfg_setaudio|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"audio": val})
        await cb.answer("✅ Audio updated!", show_alert=True)
        await _show_settings(uid, cb.message)

    elif data == "cfg_templates":
        from routers.templates import show_templates
        await show_templates(uid, cb.message)

    elif data == "cfg_stats":
        user  = await CosmicBotz.get_user(uid)
        posts = user.get("post_count", 0) if user else 0
        plan  = "⭐ Premium" if user and user.get("is_premium") else "Free"
        kb    = InlineKeyboardBuilder()
        kb.button(text="🔙 Back", callback_data="cfg_back")
        await cb.message.edit_text(
            f"📊 <b>My Stats</b>\n\nTotal Posts: <b>{posts}</b>\nPlan: <b>{plan}</b>",
            reply_markup=kb.as_markup(),
        )

    elif data in ("cfg_back", "cfg_open"):
        await _show_settings(uid, cb.message)

    elif data == "cfg_close":
        try:
            await cb.message.delete()
        except Exception:
            pass

# ── IMPORTANT: NO F.text handler here ─────────────────────────────────────────
# All text input (watermark, channel, template name/body, button name/url)
# is handled ONLY in content.py handle_text_input to avoid double-firing.
