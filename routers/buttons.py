"""
Button Sets — save/load/manage named button layouts (like templates).
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.db import CosmicBotz
from formatter.engine import sc
from utils.fsm import fsm

router = Router()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _layout_text(buttons: list) -> str:
    rows: dict = {}
    for btn in buttons:
        rows.setdefault(btn.get("row", 0), []).append(btn["text"])
    return (
        "\n".join(
            f"  {sc('Row')} {r+1}: " + "  |  ".join(rows[r])
            for r in sorted(rows.keys())
        )
        or f"  <i>{sc('Empty')}</i>"
    )


def _set_preview_text(name: str, buttons: list) -> str:
    return (
        f"✏️ <b>{sc('Editing:')} {name}</b>\n\n"
        f"<b>{sc('Layout:')}</b>\n{_layout_text(buttons)}\n\n"
        f"{sc('Add buttons or save when done.')}"
    )


def _edit_set_kb(name: str, buttons: list):
    kb = InlineKeyboardBuilder()
    for i, btn in enumerate(buttons):
        row_label = f"R{btn.get('row', 0) + 1}"
        kb.button(text=f"🗑 {btn['text']} [{row_label}]", callback_data=f"bset_rmbtn:{i}")
    kb.button(text="➕ Add Button", callback_data="bset_addbtn")
    kb.button(text="💾 Save Set",   callback_data="bset_save")
    kb.button(text="🔙 Cancel",     callback_data="bset_back")
    kb.adjust(1)
    return kb.as_markup()


# ── Show button sets ──────────────────────────────────────────────────────────

async def show_button_sets(user_id: int, target):
    sets   = await CosmicBotz.list_button_sets(user_id)
    s      = await CosmicBotz.get_user_settings(user_id)
    active = s.get("active_btn_set", "")
    kb     = InlineKeyboardBuilder()

    if not sets:
        text = (
            f"🔗 <b>{sc('Button Sets')}</b>\n\n"
            f"{sc('No saved button sets yet.')}\n\n"
            f"{sc('Button sets let you save button layouts and reuse them on every post —')}\n"
            f"{sc('just like caption templates.')}\n\n"
            f"{sc('Use /newbtnset to create one.')}"
        )
        kb.button(text="➕ Create Button Set", callback_data="bset_new")
    else:
        text = (
            f"🔗 <b>{sc('Button Sets')}</b>  "
            f"({sc('active:')} <code>{active or sc('none')}</code>)\n\n"
        )
        for i, bs in enumerate(sets):
            mark  = "✅" if bs["name"] == active else "🔗"
            count = len(bs.get("buttons", []))
            text += f"{mark} <code>{bs['name']}</code>  <i>({count} {sc('buttons')})</i>\n"
            kb.button(text="👁 View",   callback_data=f"bset_v:{i}")
            kb.button(text="✅ Use",    callback_data=f"bset_u:{i}")
            kb.button(text="🗑 Delete", callback_data=f"bset_d:{i}")
        kb.adjust(3)
        kb.button(text="➕ Create Button Set", callback_data="bset_new")

    if isinstance(target, Message):
        await target.answer(text, reply_markup=kb.as_markup())
    else:
        try:
            await target.edit_text(text, reply_markup=kb.as_markup())
        except Exception:
            pass


# ── Commands ──────────────────────────────────────────────────────────────────

@router.message(Command("buttonsets", "btnsets"))
async def cmd_button_sets(message: Message):
    await show_button_sets(message.from_user.id, message)


@router.message(Command("newbtnset"))
async def cmd_new_btn_set(message: Message):
    await fsm.set(message.from_user.id, {"step": "bset_name"})
    await message.answer(
        f"🔗 <b>{sc('Create Button Set')}</b>\n\n"
        f"{sc('First, send a')} <b>{sc('name')}</b> {sc('for this set.')}\n"
        f"{sc('Example:')} <code>WatchLinks</code>  <code>MyChannel</code>  <code>Streaming</code>\n\n"
        f"<i>{sc('No spaces, max 32 chars.')}</i>"
    )


# ── Callbacks ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("bset_"))
async def bset_callback(cb: CallbackQuery):
    await cb.answer()
    uid  = cb.from_user.id
    data = cb.data

    # ── Simple actions ────────────────────────────────────────────────────────

    if data == "bset_new":
        await fsm.set(uid, {"step": "bset_name"})
        try:
            await cb.message.edit_text(
                f"🔗 <b>{sc('Create Button Set')}</b>\n\n"
                f"{sc('Send a')} <b>{sc('name')}</b> {sc('for this set (no spaces, max 32 chars):')}"
            )
        except Exception:
            pass
        return

    if data == "bset_back":
        await show_button_sets(uid, cb.message)
        return

    if data == "bset_addbtn":
        state = await fsm.get(uid)
        if not state:
            return
        await fsm.update(uid, {"step": "bset_btn_name"})
        try:
            await cb.message.edit_text(
                f"🏷 <b>{sc('Button Label')}</b>\n\n"
                f"{sc('Send the button text:')}\n\n"
                "▶️ Watch Now\n📥 Download\n🔔 Join Channel\n📖 Read Online"
            )
        except Exception:
            pass
        return

    if data == "bset_save":
        state = await fsm.get(uid)
        if not state:
            return
        name  = state.get("bset_name", "")
        btns  = state.get("bset_buttons", [])
        await CosmicBotz.save_button_set(uid, name, btns)
        await fsm.clear(uid)
        await cb.answer(f"✅ '{name}' {sc('saved!')}", show_alert=True)
        await show_button_sets(uid, cb.message)
        return

    # ── Index-based actions ───────────────────────────────────────────────────

    if ":" not in data:
        return

    action, idx_str = data.split(":", 1)
    try:
        idx = int(idx_str)
    except ValueError:
        return

    # bset_row — row picker during creation/editing
    if action == "bset_row":
        row   = idx
        state = await fsm.get(uid)
        if not state:
            return
        btns = list(state.get("bset_buttons", []))
        btns.append({
            "text": state.get("bset_pending_name", "Button"),
            "url":  state.get("bset_pending_url", ""),
            "row":  row,
        })
        name = state.get("bset_name", "")
        await fsm.update(uid, {
            "bset_buttons":      btns,
            "bset_pending_name": None,
            "bset_pending_url":  None,
        })
        kb = InlineKeyboardBuilder()
        kb.button(text="➕ Add Another Button", callback_data="bset_addbtn")
        kb.button(text="💾 Save Set",           callback_data="bset_save")
        kb.button(text=f"🗑 Remove Last",       callback_data=f"bset_rmbtn:{len(btns)-1}")
        kb.adjust(1)
        try:
            await cb.message.edit_text(
                f"✅ <b>{sc('Button added!')}</b>\n\n"
                f"<b>{name} — {sc('Layout:')}</b>\n{_layout_text(btns)}\n\n"
                f"{sc('Add more or save?')}",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass
        return

    # bset_rmbtn — remove button during editing
    if action == "bset_rmbtn":
        state = await fsm.get(uid)
        if not state:
            return
        btns = list(state.get("bset_buttons", []))
        if 0 <= idx < len(btns):
            removed = btns.pop(idx)
            await fsm.update(uid, {"bset_buttons": btns})
            await cb.answer(f"🗑 {sc('Removed:')} {removed['text']}")
        name = state.get("bset_name", "")
        try:
            await cb.message.edit_text(
                _set_preview_text(name, btns),
                reply_markup=_edit_set_kb(name, btns),
            )
        except Exception:
            pass
        return

    # Remaining actions need the sets list
    sets = await CosmicBotz.list_button_sets(uid)
    if idx >= len(sets):
        await cb.answer(sc("Not found — list changed."), show_alert=True)
        await show_button_sets(uid, cb.message)
        return

    bs   = sets[idx]
    name = bs["name"]
    btns = bs.get("buttons", [])

    if action == "bset_v":
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Activate", callback_data=f"bset_u:{idx}")
        kb.button(text="✏️ Edit",     callback_data=f"bset_e:{idx}")
        kb.button(text="🗑 Delete",   callback_data=f"bset_d:{idx}")
        kb.button(text="🔙 Back",     callback_data="bset_back")
        kb.adjust(2, 2)
        try:
            await cb.message.edit_text(
                f"🔗 <b>{name}</b>\n\n"
                f"<b>{sc('Layout:')}</b>\n{_layout_text(btns)}\n\n"
                f"<b>{sc('Total:')}</b> {len(btns)} {sc('button(s)')}",
                reply_markup=kb.as_markup(),
            )
        except Exception:
            pass

    elif action == "bset_u":
        await CosmicBotz.update_user_settings(uid, {"active_btn_set": name})
        await cb.answer(f"✅ '{name}' {sc('is now active!')}", show_alert=True)
        await show_button_sets(uid, cb.message)

    elif action == "bset_d":
        await CosmicBotz.delete_button_set(uid, name)
        s = await CosmicBotz.get_user_settings(uid)
        if s.get("active_btn_set") == name:
            await CosmicBotz.update_user_settings(uid, {"active_btn_set": ""})
        await cb.answer(f"🗑 '{name}' {sc('deleted.')}", show_alert=True)
        await show_button_sets(uid, cb.message)

    elif action == "bset_e":
        await fsm.set(uid, {
            "step":         "bset_edit",
            "bset_name":    name,
            "bset_buttons": list(btns),
        })
        try:
            await cb.message.edit_text(
                _set_preview_text(name, btns),
                reply_markup=_edit_set_kb(name, btns),
            )
        except Exception:
            pass
