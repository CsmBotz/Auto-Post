from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm

router = Router()


@router.message(Command("setformat"))
async def cmd_setformat(message: Message):
    await fsm.set(message.from_user.id, {"step": "tpl_name"})
    await message.answer(
        "📝 <b>Template Builder</b>\n\n"
        "<b>Tokens — All categories:</b>\n"
        "<code>{title}</code> <code>{year}</code> <code>{rating}</code> <code>{genres}</code> <code>{hashtags}</code>\n\n"
        "<b>Movie / TV:</b>\n"
        "<code>{overview}</code> <code>{runtime}</code> <code>{imdb_rating}</code> <code>{imdb_votes}</code>\n"
        "<code>{content_rating}</code> <code>{quality}</code> <code>{audio}</code>\n\n"
        "<b>TV only:</b> <code>{seasons}</code> <code>{episodes}</code> <code>{network}</code>\n\n"
        "<b>Anime:</b> <code>{synopsis}</code> <code>{episodes}</code> <code>{studio}</code> <code>{aired}</code>\n\n"
        "<b>Manhwa:</b> <code>{synopsis}</code> <code>{chapters}</code> <code>{published}</code>\n\n"
        "Send a <b>name</b> for this template (no spaces, max 32 chars):"
    )


@router.message(Command("myformat"))
async def cmd_myformat(message: Message):
    uid  = message.from_user.id
    s    = await CosmicBotz.get_user_settings(uid)
    name = s.get("active_template", "default")
    if name == "default":
        await message.answer("📋 Using <b>Default Template</b>.\nUse /setformat to create a custom one!")
        return
    tpl = await CosmicBotz.get_template(uid, name)
    if not tpl:
        await message.answer("❌ Active template not found in DB.")
        return
    await message.answer(f"📋 <b>Active: {name}</b>\n\n<code>{tpl['body']}</code>")


@router.message(Command("templates"))
async def cmd_templates(message: Message):
    await show_templates(message.from_user.id, message)


async def show_templates(user_id: int, target):
    templates = await CosmicBotz.list_user_templates(user_id)
    s      = await CosmicBotz.get_user_settings(user_id)
    active = s.get("active_template", "default")
    kb     = InlineKeyboardBuilder()

    if not templates:
        text = "📋 <b>My Templates</b>\n\nNo custom templates yet.\nUse /setformat to create one!"
        kb.button(text="➕ New Template", callback_data="tpl_new")
    else:
        text = f"📋 <b>My Templates</b>  (active: <code>{active}</code>)\n\n"
        for t in templates:
            mark = "✅" if t["name"] == active else "📄"
            text += f"{mark} <code>{t['name']}</code>\n"
            kb.button(text="👁 View",   callback_data=f"tpl_view|{t['name']}")
            kb.button(text="✅ Use",    callback_data=f"tpl_use|{t['name']}")
            kb.button(text="🗑 Delete", callback_data=f"tpl_del|{t['name']}")
            kb.adjust(3)
        kb.button(text="➕ New Template", callback_data="tpl_new")

    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb.as_markup())
    else:
        await target.edit_text(text, reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("tpl_"))
async def tpl_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "tpl_new":
        await fsm.set(uid, {"step": "tpl_name"})
        await cb.message.edit_text("📝 Send a <b>name</b> for the new template (no spaces, max 32 chars):")

    elif data.startswith("tpl_view|"):
        name = data.split("|", 1)[1]
        tpl  = await CosmicBotz.get_template(uid, name)
        if tpl:
            kb = InlineKeyboardBuilder()
            kb.button(text="✅ Activate", callback_data=f"tpl_use|{name}")
            kb.button(text="🔙 Back",     callback_data="tpl_back")
            await cb.message.edit_text(
                f"📋 <b>{name}</b>\n\n<code>{tpl['body']}</code>",
                reply_markup=kb.as_markup(),
            )

    elif data.startswith("tpl_use|"):
        name = data.split("|", 1)[1]
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await cb.answer(f"✅ '{name}' activated!", show_alert=True)
        await show_templates(uid, cb.message)

    elif data.startswith("tpl_del|"):
        name = data.split("|", 1)[1]
        await CosmicBotz.delete_template(uid, name)
        s = await CosmicBotz.get_user_settings(uid)
        if s.get("active_template") == name:
            await CosmicBotz.update_user_settings(uid, {"active_template": "default"})
        await cb.answer(f"🗑 Deleted '{name}'", show_alert=True)
        await show_templates(uid, cb.message)

    elif data == "tpl_back":
        await show_templates(uid, cb.message)
