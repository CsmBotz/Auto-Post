from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm
import config as cfg

router = Router()

_ALL_CMDS = [
    "start", "help", "movie", "tvshow", "anime", "manhwa",
    "settings", "setwatermark", "setchannel", "stats",
    "setformat", "myformat", "templates",
    "admin", "broadcast", "ban", "unban",
    "addpremium", "revokepremium", "userinfo", "globalstats",
]


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


async def _send_settings(user_id: int, target):
    s    = await CosmicBotz.get_user_settings(user_id)
    user = await CosmicBotz.get_user(user_id)
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
        await target.edit_text(text, reply_markup=settings_kb())


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    await _send_settings(message.from_user.id, message)


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
        "Send your channel username or ID.\n"
        "Example: <code>@MyAnimeChannel</code>\n\n"
        "⚠️ Make sure this bot is <b>admin</b> in your channel first!"
    )


@router.callback_query(F.data.startswith("cfg_"))
async def cfg_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "cfg_open":
        await _send_settings(uid, cb.message)
    elif data == "cfg_watermark":
        await fsm.set(uid, {"step": "cfg_watermark"})
        await cb.message.edit_text(
            "🖋 <b>Set Watermark</b>\n\nSend watermark text or <code>clear</code> to remove."
        )
    elif data == "cfg_channel":
        await fsm.set(uid, {"step": "cfg_channel"})
        await cb.message.edit_text(
            "📺 <b>Set Channel</b>\n\nSend <code>@channel</code> or numeric ID.\n⚠️ Bot must be admin!"
        )
    elif data == "cfg_quality":
        await cb.message.edit_text("🎞 <b>Select Default Quality:</b>", reply_markup=quality_kb())
    elif data == "cfg_audio":
        await cb.message.edit_text("🔊 <b>Select Default Audio:</b>", reply_markup=audio_kb())
    elif data.startswith("cfg_setquality|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"quality": val})
        await cb.answer("✅ Quality set!", show_alert=True)
        await _send_settings(uid, cb.message)
    elif data.startswith("cfg_setaudio|"):
        val = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"audio": val})
        await cb.answer("✅ Audio set!", show_alert=True)
        await _send_settings(uid, cb.message)
    elif data == "cfg_templates":
        from routers.templates import show_templates
        await show_templates(uid, cb.message)
    elif data == "cfg_stats":
        user  = await CosmicBotz.get_user(uid)
        posts = user.get("post_count", 0) if user else 0
        plan  = "⭐ Premium" if user and user.get("is_premium") else "Free"
        kb = InlineKeyboardBuilder()
        kb.button(text="🔙 Back", callback_data="cfg_back")
        await cb.message.edit_text(
            f"📊 <b>My Stats</b>\n\nTotal Posts: <b>{posts}</b>\nPlan: <b>{plan}</b>",
            reply_markup=kb.as_markup(),
        )
    elif data == "cfg_back":
        await _send_settings(uid, cb.message)
    elif data == "cfg_close":
        await cb.message.delete()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message):
    uid   = message.from_user.id
    state = await fsm.get(uid)
    if not state:
        return
    step = state.get("step", "")
    text = message.text.strip()

    if step == "cfg_watermark":
        if text.lower() == "clear":
            await CosmicBotz.update_user_settings(uid, {"watermark": ""})
            await message.answer("✅ Watermark cleared.")
        else:
            await CosmicBotz.update_user_settings(uid, {"watermark": text})
            await message.answer(f"✅ Watermark set to <code>{text}</code>")
        await fsm.clear(uid)

    elif step == "cfg_channel":
        if not (text.startswith("@") or text.lstrip("-").isdigit()):
            await message.answer("❌ Use <code>@channel</code> format or a numeric chat ID.")
            return
        await CosmicBotz.update_user_settings(uid, {"channel_id": text})
        await message.answer(f"✅ Channel linked: <code>{text}</code>\nMake sure the bot is admin there!")
        await fsm.clear(uid)

    elif step == "tpl_name":
        if " " in text or len(text) > 32:
            await message.answer("❌ Name must be ≤ 32 chars with no spaces. Try again:")
            return
        await fsm.update(uid, {"step": "tpl_body", "tpl_name": text})
        await message.answer(
            f"✅ Name: <b>{text}</b>\n\n"
            "Now send the <b>template body</b>.\n"
            "Use tokens like <code>{title}</code>, <code>{imdb_rating}</code> etc.\n"
            "Must include <code>{title}</code>."
        )

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
            "Use /templates to manage all your templates."
        )

    elif step == "adm_broadcast":
        from routers.admin import do_broadcast
        await do_broadcast(message, text)
