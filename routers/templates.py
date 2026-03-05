from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from formatter.engine import sc
from utils.fsm import fsm

router = Router()


@router.message(Command("setformat"))
async def cmd_setformat(message: Message):
    await fsm.set(message.from_user.id, {"step": "tpl_name"})
    await message.answer(
        f"📝 <b>{sc('Template Builder')}</b>\n\n"
        f"<b>{sc('Tokens — All categories:')}</b>\n"
        "<code>{title}</code> <code>{year}</code> <code>{rating}</code> "
        "<code>{genres}</code> <code>{hashtags}</code>\n\n"
        f"<b>{sc('Movie / TV:')}</b>\n"
        "<code>{overview}</code> <code>{runtime}</code> <code>{imdb_rating}</code> "
        "<code>{imdb_votes}</code> <code>{content_rating}</code> "
        "<code>{quality}</code> <code>{audio}</code>\n\n"
        f"<b>{sc('TV only:')}</b> <code>{{seasons}}</code> <code>{{episodes}}</code> <code>{{network}}</code>\n\n"
        f"<b>{sc('Anime:')}</b> <code>{{synopsis}}</code> <code>{{episodes}}</code> "
        "<code>{studio}</code> <code>{aired}</code>\n\n"
        f"<b>{sc('Manhwa:')}</b> <code>{{synopsis}}</code> <code>{{chapters}}</code> <code>{{published}}</code>\n\n"
        f"➡️ {sc('Send a')} <b>{sc('name')}</b> {sc('for this template (no spaces, max 32 chars):')}"
    )


@router.message(Command("myformat"))
async def cmd_myformat(message: Message):
    uid  = message.from_user.id
    s    = await CosmicBotz.get_user_settings(uid)
    name = s.get("active_template", "default")
    if name == "default":
        await message.answer(
            f"📋 {sc('Using')} <b>{sc('Default Template')}</b>.\n"
            f"{sc('Use /setformat to create a custom one!')}"
        )
        return
    tpl = await CosmicBotz.get_template(uid, name)
    if not tpl:
        await CosmicBotz.update_user_settings(uid, {"active_template": "default"})
        await message.answer(
            f"❌ {sc('Active template missing from DB — reset to default.')}"
        )
        return
    await message.answer(
        f"📋 <b>{sc('Active:')} {name}</b>\n\n<code>{tpl['body'][:3500]}</code>"
    )


@router.message(Command("templates"))
async def cmd_templates(message: Message):
    await show_templates(message.from_user.id, message)


async def show_templates(user_id: int, target):
    templates = await CosmicBotz.list_user_templates(user_id)
    s         = await CosmicBotz.get_user_settings(user_id)
    active    = s.get("active_template", "default")
    kb        = InlineKeyboardBuilder()

    if not templates:
        text = (
            f"📋 <b>{sc('My Templates')}</b>\n\n"
            f"{sc('No custom templates yet.')}\n"
            f"{sc('Use /setformat to create one!')}"
        )
        kb.button(text="➕ New Template", callback_data="tpl_new")
    else:
        text = f"📋 <b>{sc('My Templates')}</b>  ({sc('active:')} <code>{active}</code>)\n\n"
        for i, t in enumerate(templates):
            mark = "✅" if t["name"] == active else "📄"
            text += f"{mark} <code>{t['name'][:20]}</code>\n"
            kb.button(text="👁 View",   callback_data=f"tpl_v:{i}")
            kb.button(text="✅ Use",    callback_data=f"tpl_u:{i}")
            kb.button(text="🗑 Delete", callback_data=f"tpl_d:{i}")
        kb.adjust(3)
        kb.button(text="➕ New Template", callback_data="tpl_new")

    try:
        if isinstance(target, Message):
            await target.answer(text, reply_markup=kb.as_markup())
        else:
            await target.edit_text(text, reply_markup=kb.as_markup())
    except Exception:
        pass


@router.callback_query(F.data.startswith("tpl_"))
async def tpl_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    if data == "tpl_new":
        await fsm.set(uid, {"step": "tpl_name"})
        try:
            await cb.message.edit_text(
                f"📝 {sc('Send a')} <b>{sc('name')}</b> {sc('for the new template (no spaces, max 32 chars):')}"
            )
        except Exception:
            pass
        return

    if data == "tpl_back":
        await show_templates(uid, cb.message)
        return

    if ":" not in data:
        return

    action, idx_str = data.split(":", 1)
    try:
        idx = int(idx_str)
    except ValueError:
        return

    templates = await CosmicBotz.list_user_templates(uid)
    if idx >= len(templates):
        await cb.answer(sc("Template not found — list may have changed."), show_alert=True)
        await show_templates(uid, cb.message)
        return

    t    = templates[idx]
    name = t["name"]

    if action == "tpl_v":
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Activate", callback_data=f"tpl_u:{idx}")
        kb.button(text="🔙 Back",     callback_data="tpl_back")
        body = t["body"][:3500]
        try:
            await cb.message.edit_text(
                f"📋 <b>{name}</b>\n\n<code>{body}</code>",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    elif action == "tpl_u":
        await CosmicBotz.update_user_settings(uid, {"active_template": name})
        await cb.answer(f"✅ '{name}' {sc('activated!')}", show_alert=True)
        await show_templates(uid, cb.message)

    elif action == "tpl_d":
        await CosmicBotz.delete_template(uid, name)
        s = await CosmicBotz.get_user_settings(uid)
        if s.get("active_template") == name:
            await CosmicBotz.update_user_settings(uid, {"active_template": "default"})
        await cb.answer(f"🗑 '{name}' {sc('deleted.')}", show_alert=True)
        await show_templates(uid, cb.message)
