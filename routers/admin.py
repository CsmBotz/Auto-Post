import asyncio
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from utils.fsm import fsm
import config as cfg

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in cfg.ADMIN_IDS


def admin_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Stats",     callback_data="adm_stats")
    kb.button(text="📢 Broadcast", callback_data="adm_broadcast")
    kb.button(text="❌ Close",      callback_data="adm_close")
    kb.adjust(2, 1)
    return kb.as_markup()


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return
    tu = await CosmicBotz.total_users()
    tp = await CosmicBotz.total_posts()
    await message.answer(
        f"👑 <b>Admin Panel</b>\n\n"
        f"👥 Total Users: <b>{tu}</b>\n"
        f"📤 Total Posts: <b>{tp}</b>",
        reply_markup=admin_kb(),
    )


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return
    await fsm.set(message.from_user.id, {"step": "adm_broadcast"})
    await message.answer("📢 Send the message to broadcast to all users:")


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /ban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.ban_user(uid)
    await message.answer(f"⛔ User <code>{uid}</code> banned.")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /unban <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.unban_user(uid)
    await message.answer(f"✅ User <code>{uid}</code> unbanned.")


@router.message(Command("addpremium"))
async def cmd_addpremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /addpremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, True)
    await message.answer(f"⭐ <code>{uid}</code> upgraded to Premium.")
    try:
        await message.bot.send_message(uid, "🎉 <b>You've been upgraded to ⭐ Premium!</b>")
    except Exception:
        pass


@router.message(Command("revokepremium"))
async def cmd_revokepremium(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].isdigit():
        await message.answer("Usage: /revokepremium <code>user_id</code>")
        return
    uid = int(args[0])
    await CosmicBotz.set_premium(uid, False)
    await message.answer(f"✅ Premium revoked for <code>{uid}</code>.")


@router.message(Command("userinfo"))
async def cmd_userinfo(message: Message):
    if not is_admin(message.from_user.id):
        return
    args = message.text.split()[1:]
    if not args or not args[0].lstrip("-").isdigit():
        await message.answer("Usage: /userinfo <code>user_id</code>")
        return
    uid  = int(args[0])
    user = await CosmicBotz.get_user(uid)
    if not user:
        await message.answer("❌ User not found in DB.")
        return
    await message.answer(
        f"👤 <b>User Info</b>\n\n"
        f"ID:       <code>{uid}</code>\n"
        f"Name:     {user.get('full_name', 'N/A')}\n"
        f"Username: @{user.get('username', 'N/A')}\n"
        f"Posts:    <b>{user.get('post_count', 0)}</b>\n"
        f"Premium:  {'⭐ Yes' if user.get('is_premium') else 'No'}\n"
        f"Banned:   {'⛔ Yes' if user.get('is_banned') else 'No'}"
    )


@router.message(Command("globalstats"))
async def cmd_globalstats(message: Message):
    if not is_admin(message.from_user.id):
        return
    tu = await CosmicBotz.total_users()
    tp = await CosmicBotz.total_posts()
    await message.answer(
        f"📊 <b>Global Stats</b>\n\n"
        f"👥 Total Users: <b>{tu}</b>\n"
        f"📤 Total Posts: <b>{tp}</b>"
    )


async def do_broadcast(message: Message, text: str):
    """Called from content.py handle_text_input when step=adm_broadcast."""
    await fsm.clear(message.from_user.id)
    user_ids = await CosmicBotz.get_all_user_ids()
    status   = await message.answer(f"📤 Broadcasting to <b>{len(user_ids)}</b> users...")
    ok = fail = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(uid, f"📢 <b>Announcement</b>\n\n{text}")
            ok += 1
        except Exception:
            fail += 1
        # Rate limit: Telegram allows ~30 msgs/sec, be safe at 25
        if ok % 25 == 0:
            await asyncio.sleep(1)
    await status.edit_text(
        f"✅ Broadcast done!\n✔ Sent: <b>{ok}</b>  ✘ Failed: <b>{fail}</b>"
    )


@router.callback_query(F.data.startswith("adm_"))
async def adm_callback(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Admin only.", show_alert=True)
        return
    await cb.answer()
    data = cb.data

    if data == "adm_stats":
        tu = await CosmicBotz.total_users()
        tp = await CosmicBotz.total_posts()
        await cb.message.edit_text(
            f"📊 <b>Stats</b>\n\nUsers: <b>{tu}</b>\nPosts: <b>{tp}</b>",
            reply_markup=admin_kb(),
        )
    elif data == "adm_broadcast":
        await fsm.set(cb.from_user.id, {"step": "adm_broadcast"})
        await cb.message.edit_text("📢 Send the broadcast message now:")
    elif data == "adm_close":
        try:
            await cb.message.delete()
        except Exception:
            pass
