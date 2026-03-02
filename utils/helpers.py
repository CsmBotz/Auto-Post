from aiogram.utils.keyboard import InlineKeyboardBuilder
import config as cfg


def extract_query(text: str) -> str:
    parts = text.split(None, 1)
    return parts[1].strip() if len(parts) > 1 else ""


def search_kb(results: list, prefix: str):
    kb = InlineKeyboardBuilder()
    for r in results[:cfg.MAX_SEARCH_RESULTS]:
        label = f"{r.get('title', 'Unknown')} ({r.get('year', '?')})"
        kb.button(text=label[:64], callback_data=f"{prefix}_select_{r['id']}")
    kb.button(text="❌ Cancel", callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def thumbnail_kb(prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Skip — Use Auto Poster", callback_data=f"{prefix}_thumb_skip")
    kb.button(text="❌ Cancel",                 callback_data=f"{prefix}_cancel")
    kb.adjust(1)
    return kb.as_markup()


def preview_kb(prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="📤 Post to Channel",  callback_data=f"{prefix}_post_channel")
    kb.button(text="📋 Copy Caption",     callback_data=f"{prefix}_post_copy")
    kb.button(text="🔗 Add Buttons",      callback_data=f"{prefix}_btn_start")
    kb.button(text="🖼 Change Thumbnail", callback_data=f"{prefix}_redo_thumb")
    kb.button(text="📄 Change Template",  callback_data=f"{prefix}_change_tpl")
    kb.button(text="❌ Cancel",            callback_data=f"{prefix}_cancel")
    kb.adjust(2, 1, 2, 1)
    return kb.as_markup()


def template_kb(templates: list, prefix: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="⬜ Default", callback_data=f"{prefix}_tpl_default")
    for t in templates:
        kb.button(text=f"📄 {t['name']}", callback_data=f"{prefix}_tpl_{t['name']}")
    kb.button(text="🔙 Back", callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


def add_button_start_kb(prefix: str):
    """Shown when no buttons added yet."""
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Button",  callback_data=f"{prefix}_btn_add")
    kb.button(text="✅ Post Now",    callback_data=f"{prefix}_post_direct")
    kb.button(text="🔙 Back",        callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()


def button_manage_kb(prefix: str, buttons: list):
    """Shown after at least one button is added."""
    kb = InlineKeyboardBuilder()
    for i, btn in enumerate(buttons):
        kb.button(text=f"🗑 {btn['text']}", callback_data=f"{prefix}_btn_del_{i}")
    kb.button(text="➕ Add Another", callback_data=f"{prefix}_btn_add")
    kb.button(text="✅ Post Now",    callback_data=f"{prefix}_btn_done")
    kb.button(text="🔙 Back",        callback_data=f"{prefix}_back_preview")
    kb.adjust(1)
    return kb.as_markup()
