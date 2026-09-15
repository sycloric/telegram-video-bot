from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.utils.settings import get_user_settings, update_user_setting
from bot.handlers.user_handlers import get_main_keyboard

router = Router()

EFFECTS = ["Classic", "Freeze + Zoom", "Freeze + Blur", "Snap", "Glitch", "Dark Transition", "Flash", "Zoom Out", "Cinematic", "Shake", "Pop", "Random"]
POSITIONS = ["Start", "25%", "Middle", "75%", "End", "Random", "Smart"]
ASPECT_RATIOS = ["Original", "16:9", "9:16", "4:3", "3:4", "1:1", "21:9", "4K"]
QUALITIES = ["Economy", "Balance", "Maximum"]

def get_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Переход / Эффект", callback_data="settings:effect")],
        [InlineKeyboardButton(text="📍 Позиция рекламы", callback_data="settings:position")],
        [InlineKeyboardButton(text="📐 Разрешение / Формат", callback_data="settings:aspect_ratio")],
        [InlineKeyboardButton(text="🎚 Качество", callback_data="settings:quality")],
        [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="back_main")]
    ])

def get_options_keyboard(setting_type: str, options: list, current_val: str):
    keyboard = []
    # group by 2
    row = []
    for opt in options:
        text = f"✅ {opt}" if opt == current_val else opt
        row.append(InlineKeyboardButton(text=text, callback_data=f"set_{setting_type}:{opt}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton(text="🔙 Назад к настройкам", callback_data="open_settings")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@router.callback_query(F.data == "open_settings")
async def cb_open_settings(callback: CallbackQuery):
    settings = get_user_settings(callback.message.chat.id)
    text = (
        "⚙️ **Текущие настройки:**\n\n"
        f"🎬 Эффект: {settings['effect']}\n"
        f"📍 Позиция: {settings['position']}\n"
        f"📐 Формат: {settings['aspect_ratio']}\n"
        f"🎚 Качество: {settings['quality']}\n\n"
        "Выберите параметр для изменения:"
    )
    await callback.message.edit_text(text, reply_markup=get_settings_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("settings:"))
async def cb_settings_menu(callback: CallbackQuery):
    setting_type = callback.data.split(":")[1]
    chat_id = callback.message.chat.id
    current_val = get_user_settings(chat_id).get(setting_type)
    
    if setting_type == "effect":
        kb = get_options_keyboard("effect", EFFECTS, current_val)
        await callback.message.edit_text("🎬 Выберите эффект перехода:", reply_markup=kb)
    elif setting_type == "position":
        kb = get_options_keyboard("position", POSITIONS, current_val)
        await callback.message.edit_text("📍 Выберите позицию рекламы:", reply_markup=kb)
    elif setting_type == "aspect_ratio":
        kb = get_options_keyboard("aspect_ratio", ASPECT_RATIOS, current_val)
        await callback.message.edit_text("📐 Выберите формат итогового видео:\n* При изменении формата пропорции сохраняются, добавляется красивое размытие фона (Blur Pad).", reply_markup=kb)
    elif setting_type == "quality":
        kb = get_options_keyboard("quality", QUALITIES, current_val)
        await callback.message.edit_text("🎚 Выберите качество экспорта:", reply_markup=kb)

@router.callback_query(F.data.startswith("set_"))
async def cb_set_value(callback: CallbackQuery):
    data = callback.data # set_effect:Classic
    parts = data.split(":", 1)
    if len(parts) == 2:
        setting_type = parts[0].replace("set_", "")
        value = parts[1]
        update_user_setting(callback.message.chat.id, setting_type, value)
        await callback.answer(f"✅ Сохранено: {value}")
        # Navigate back to settings root
        await cb_open_settings(callback)

