import os
import glob
import re
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, PreCheckoutQuery
from media.processor import VideoProcessor
from bot.utils.logger import logger
from bot.config import AD_VIDEO_PATH
from bot.utils.settings import get_user_settings, update_user_setting
from media.downloader import download_tiktok

router = Router()

pending_videos = {}
pending_tiktoks = {}
processor_instance = None 

# Regex to detect TikTok URLs
TIKTOK_REGEX = re.compile(r'https?://(www\.)?(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)/.*')

def get_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Выбор рекламы", callback_data="select_ad")],
        [InlineKeyboardButton(text="⚙️ Настройки видео", callback_data="open_settings")],
        [InlineKeyboardButton(text="⭐ Поддержать бота", callback_data="support_bot")]
    ])

def get_tiktok_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать без рекламы", callback_data="tiktok_skip")],
        [InlineKeyboardButton(text="🎬 Вставить рекламу", callback_data="tiktok_ad")]
    ])

def get_ads_keyboard():
    ads = glob.glob(os.path.join("assets", "*.mp4"))
    keyboard = []
    for idx, ad in enumerate(ads, 1):
        filename = os.path.basename(ad)
        name = "Musor Drop" if idx == 1 else filename
        keyboard.append([InlineKeyboardButton(text=f"📄 {name}", callback_data=f"set_ad:{filename}")])
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_support_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="⭐ 10 звезд", callback_data="donate_10"), InlineKeyboardButton(text="⭐ 15 звезд", callback_data="donate_15")],
        [InlineKeyboardButton(text="⭐ 20 звезд", callback_data="donate_20"), InlineKeyboardButton(text="⭐ 25 звезд", callback_data="donate_25")],
        [InlineKeyboardButton(text="⭐ 50 звезд", callback_data="donate_50"), InlineKeyboardButton(text="⭐ 100 звезд", callback_data="donate_100")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

async def process_video_request(message: Message, bot: Bot):
    status_msg = await message.reply("⏳ Добавляю в очередь на обработку...")
    try:
        file = await bot.get_file(message.video.file_id)
        settings = get_user_settings(message.chat.id)
        selected_ad = settings.get("ad_path")
        if not selected_ad or not os.path.exists(selected_ad):
            selected_ad = AD_VIDEO_PATH
            
        await processor_instance.add_task(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            video_file_id=message.video.file_id,
            file_path=file.file_path,
            ad_video_path=selected_ad
        )
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        await status_msg.edit_text("❌ Ошибка при попытке скачать видео.")

def setup_handlers(dp, processor: VideoProcessor):
    global processor_instance
    processor_instance = processor
    
    @router.message(Command("start"))
    async def cmd_start(message: Message):
        text = "Привет, я видео-редактор с автоматической вставкой рекламы!\nОтправь мне видео или ссылку на TikTok, и я сделаю всю магию."
        await message.answer(text, reply_markup=get_main_keyboard())

    @router.message(F.text & F.text.regexp(TIKTOK_REGEX))
    async def handle_tiktok(message: Message, bot: Bot):
        status_msg = await message.reply("🔗 Получаю информацию о TikTok...\n⬇️ Скачиваю видео...")
        try:
            download_dir = os.path.join("temp", f"dl_{message.chat.id}_{message.message_id}")
            file_path = await download_tiktok(message.text, download_dir)
            
            pending_tiktoks[message.chat.id] = {
                "file_path": file_path,
                "status_msg_id": status_msg.message_id
            }
            
            await status_msg.edit_text("📥 Видео успешно скачано!\n\nЧто с ним сделать дальше?", reply_markup=get_tiktok_keyboard())
        except Exception as e:
            logger.error(f"TikTok download failed: {e}")
            await status_msg.edit_text(str(e))

    @router.callback_query(F.data.startswith("tiktok_"))
    async def cb_tiktok_action(callback: CallbackQuery, bot: Bot):
        action = callback.data.split("_")[1]
        chat_id = callback.message.chat.id
        
        tiktok_data = pending_tiktoks.pop(chat_id, None)
        if not tiktok_data:
            await callback.answer("Сессия устарела. Отправьте ссылку заново.", show_alert=True)
            return
            
        await callback.message.edit_text("⏳ Добавляю в очередь на обработку...")
        
        settings = get_user_settings(chat_id)
        selected_ad = settings.get("ad_path")
        if not selected_ad or not os.path.exists(selected_ad):
            selected_ad = AD_VIDEO_PATH
            
        skip_ad = (action == "skip")
        
        await processor_instance.add_task(
            chat_id=chat_id,
            message_id=tiktok_data["status_msg_id"],
            video_file_id="", # Local file has no ID
            file_path=tiktok_data["file_path"],
            ad_video_path=selected_ad,
            is_local=True,
            skip_ad=skip_ad
        )
        await callback.answer()

    @router.callback_query(F.data == "select_ad")
    async def cb_select_ad(callback: CallbackQuery):
        await callback.message.edit_text("Выберите рекламный ролик для вставки:", reply_markup=get_ads_keyboard())

    @router.callback_query(F.data.startswith("set_ad:"))
    async def cb_set_ad(callback: CallbackQuery):
        filename = callback.data.split(":", 1)[1]
        ad_path = os.path.join("assets", filename)
        if os.path.exists(ad_path):
            update_user_setting(callback.message.chat.id, "ad_path", ad_path)
            name = "Musor Drop" if "musordrop" in filename.lower() or filename == os.path.basename(glob.glob(os.path.join("assets", "*.mp4"))[0]) else filename
            await callback.answer(f"Выбрана реклама: {name}", show_alert=True)
            await callback.message.edit_text("Реклама успешно выбрана! Отправьте мне видео или ссылку на TikTok.", reply_markup=get_main_keyboard())
        else:
            await callback.answer("Файл не найден!", show_alert=True)

    @router.callback_query(F.data == "support_bot")
    async def cb_support_bot(callback: CallbackQuery):
        text = (
            "😔 Создатель этого бота нищий и едва может позволить себе оплачивать сервера...\n\n"
            "Но если вы поддержите его звездами ⭐, то этот замечательный бот "
            "будет работать 24/7, принимать самые тяжелые видео и радовать вас новыми фичами!\n\n"
            "Пожалуйста, выберите сумму поддержки:"
        )
        await callback.message.edit_text(text, reply_markup=get_support_keyboard())

    @router.callback_query(F.data == "back_main")
    async def cb_back_main(callback: CallbackQuery):
        text = "Главное меню. Отправьте видео для обработки или ссылку на TikTok."
        await callback.message.edit_text(text, reply_markup=get_main_keyboard())

    @router.callback_query(F.data.startswith("donate_"))
    async def cb_donate(callback: CallbackQuery, bot: Bot):
        amount = int(callback.data.split("_")[1])
        prices = [LabeledPrice(label=f"Поддержка бота", amount=amount)]
        
        await bot.send_invoice(
            chat_id=callback.message.chat.id,
            title="Поддержка разработчика 💖",
            description=f"Отправить {amount} ⭐ на поддержку серверов и развития бота.",
            payload=f"donate_{amount}",
            provider_token="",
            currency="XTR",
            prices=prices
        )
        await callback.answer()

    @router.pre_checkout_query()
    async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery, bot: Bot):
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

    @router.message(F.successful_payment)
    async def successful_payment_handler(message: Message):
        amount = message.successful_payment.total_amount
        await message.answer(f"🎉 Огромное спасибо за поддержку в размере {amount} ⭐! Вы помогаете проекту жить и развиваться!")

    @router.message(F.video)
    async def handle_video(message: Message, bot: Bot):
        video = message.video
        if video.file_size and video.file_size > 20 * 1024 * 1024:
            await message.reply("❌ Я не могу скачать это видео. Телеграм бот может скачивать файлы только до 20 МБ.")
            return
            
        await process_video_request(message, bot)

    dp.include_router(router)
