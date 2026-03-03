from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup
import config as cfg


# ── Utility ───────────────────────────────────────────────────────────────────

def extract_query(text: str) -> str:
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


# ── Keyboards ─────────────────────────────────────────────────────────────────

def search_kb(results: list, prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for r in results[:cfg.MAX_SEARCH_RESULTS]:
        label = f"{r.get('title', 'Unknown')} ({r.get('year', '?')})"
        kb.button(text=label[:64], callback_data=f"{prefix}_select_{r['id']}")
    kb.button(text="❌ Cancel", callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def thumbnail_kb(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Skip — Use Auto Poster", callback_data=f"{prefix}_thumb_skip")
    kb.button(text="❌ Cancel",                 callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def preview_kb(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Post to Channel",  callback_data=f"{prefix}_post_channel")
    kb.button(text="📋 Copy Caption",     callback_data=f"{prefix}_post_copy")
    kb.button(text="🔗 Add Buttons",      callback_data=f"{prefix}_btn_start")
    kb.button(text="🖼 Change Thumbnail", callback_data=f"{prefix}_redo_thumb")
    kb.button(text="📄 Change Template",  callback_data=f"{prefix}_change_tpl")
    kb.button(text="❌ Cancel",            callback_data=f"{prefix}_cancel")
    kb.adjust(2, 1, 2, 1)
    return kb.as_markup()


def template_kb(templates: list, prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⬜ Default", callback_data=f"{prefix}_tpl_default")
    for t in templates:
        kb.button(text=f"📄 {t['name'][:20]}", callback_data=f"{prefix}_tpl_{t['name']}")
    kb.button(text="🔙 Back", callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


def add_button_start_kb(prefix: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Button",       callback_data=f"{prefix}_btn_add")
    kb.button(text="⚙️ Default Buttons", callback_data=f"{prefix}_btn_defaults")
    kb.button(text="✅ Post Now",         callback_data=f"{prefix}_post_direct")
    kb.button(text="🔙 Back",             callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


def button_manage_kb(prefix: str, buttons: list) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for i, btn in enumerate(buttons):
        row_label = f"Row {btn.get('row', 0) + 1}"
        kb.button(text=f"🗑 {btn['text']} [{row_label}]", callback_data=f"{prefix}_btn_del_{i}")
    kb.button(text="➕ Add Button",       callback_data=f"{prefix}_btn_add")
    kb.button(text="⚙️ Default Buttons", callback_data=f"{prefix}_btn_defaults")
    kb.button(text="✅ Post Now",         callback_data=f"{prefix}_btn_done")
    kb.button(text="🔙 Back",             callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


def default_buttons_kb(prefix: str, category: str) -> InlineKeyboardMarkup:
    """Pre-built button sets the user can instantly apply."""
    kb = InlineKeyboardBuilder()
    kb.button(text="▶️ Watch Now + 📥 Download", callback_data=f"{prefix}_dflbtn_watch_dl")
    kb.button(text="▶️ Watch Now only",           callback_data=f"{prefix}_dflbtn_watch")
    kb.button(text="📥 Download only",            callback_data=f"{prefix}_dflbtn_dl")
    if category in ("anime", "manhwa"):
        kb.button(text="📖 Read Now + ⭐ Rate",   callback_data=f"{prefix}_dflbtn_read_rate")
    kb.button(text="🔔 Join + ▶️ Watch",          callback_data=f"{prefix}_dflbtn_join_watch")
    kb.button(text="🗑 Clear All Buttons",        callback_data=f"{prefix}_dflbtn_clear")
    kb.button(text="🔙 Back",                     callback_data=f"{prefix}_btn_start")
    kb.adjust(1)
    return kb.as_markup()