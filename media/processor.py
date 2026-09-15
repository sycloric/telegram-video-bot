import asyncio
import os
import shutil
import uuid
from aiogram import Bot
from bot.utils.logger import logger
from bot.config import AD_VIDEO_PATH, FREEZE_DURATION, MIN_VIDEO_DURATION
from media.probe import probe_video
from media.ffmpeg_builder import process_advanced_video
from bot.utils.settings import get_user_settings

class VideoProcessor:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.queue = asyncio.Queue()
        self.is_running = False
        self._worker_task = None

    async def start(self):
        self.is_running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Video processor queue started.")
        
    async def stop(self):
        self.is_running = False
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("Video processor queue stopped.")
        
    async def add_task(self, chat_id: int, message_id: int, video_file_id: str, file_path: str, ad_video_path: str = AD_VIDEO_PATH, is_local: bool = False, skip_ad: bool = False):
        await self.queue.put({
            "chat_id": chat_id,
            "message_id": message_id,
            "video_file_id": video_file_id,
            "file_path": file_path,
            "ad_video_path": ad_video_path,
            "is_local": is_local,
            "skip_ad": skip_ad
        })
        logger.info(f"Task added to queue for chat {chat_id}. Queue size: {self.queue.qsize()}")
        
    async def _worker(self):
        while self.is_running:
            try:
                task = await self.queue.get()
                await self._handle_task(task)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in video processor worker: {e}")

    async def _handle_task(self, task: dict):
        chat_id = task["chat_id"]
        message_id = task["message_id"]
        file_path = task["file_path"]
        video_file_id = task["video_file_id"]
        ad_video_path = task.get("ad_video_path", AD_VIDEO_PATH)
        is_local = task.get("is_local", False)
        skip_ad = task.get("skip_ad", False)
        
        task_id = uuid.uuid4().hex[:8]
        temp_dir = os.path.join("temp", f"task_{task_id}")
        os.makedirs(temp_dir, exist_ok=True)
        
        input_path = os.path.join(temp_dir, "input.mp4")
        output_path = os.path.join(temp_dir, "result.mp4")
        
        # Load user settings for this task
        settings = get_user_settings(chat_id)
        
        try:
            # 1. Get video
            if is_local:
                await self.bot.edit_message_text("🎬 Подготавливаю видео...", chat_id=chat_id, message_id=message_id)
                shutil.move(file_path, input_path)
            else:
                await self.bot.edit_message_text("⏳ Загружаю видео...", chat_id=chat_id, message_id=message_id)
                await self.bot.download_file(file_path, input_path)
                
            if skip_ad:
                await self.bot.edit_message_text("📤 Отправляю готовое видео...", chat_id=chat_id, message_id=message_id)
                from aiogram.types import FSInputFile
                video_file = FSInputFile(input_path)
                await self.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption="✅ Ваше видео скачано без рекламы.",
                    supports_streaming=True
                )
                await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info("Video sent without ad.")
                return
            
            # 2. Probe input video
            await self.bot.edit_message_text("⏳ Анализирую видео...", chat_id=chat_id, message_id=message_id)
            input_info = await probe_video(input_path)
            
            if input_info["duration"] < MIN_VIDEO_DURATION:
                await self.bot.edit_message_text(f"❌ Видео слишком короткое для вставки. Минимум {MIN_VIDEO_DURATION} сек.", chat_id=chat_id, message_id=message_id)
                return
                
            # 3. Probe Ad video
            if not os.path.exists(ad_video_path):
                logger.error(f"Ad video not found at {ad_video_path}")
                await self.bot.edit_message_text("❌ Базовый рекламный ролик не найден. Обратитесь к админу.", chat_id=chat_id, message_id=message_id)
                return
                
            ad_info = await probe_video(ad_video_path)
            
            # 4. Process Video with Builder
            await self.bot.edit_message_text(f"🎬 Идет монтаж...\nЭффект: {settings.get('effect')}\nФормат: {settings.get('aspect_ratio')}\nЭто займет какое-то время.", chat_id=chat_id, message_id=message_id)
            
            await process_advanced_video(
                input_path=input_path, 
                ad_path=ad_video_path, 
                output_path=output_path, 
                settings=settings,
                input_info=input_info, 
                ad_info=ad_info,
                freeze_duration=FREEZE_DURATION
            )
            
            # 5. Send result
            await self.bot.edit_message_text("✅ Обработка завершена! Отправляю видео...", chat_id=chat_id, message_id=message_id)
            from aiogram.types import FSInputFile
            video_file = FSInputFile(output_path)
            await self.bot.send_video(
                chat_id=chat_id,
                video=video_file,
                caption="✅ Готово! Реклама вставлена.",
                supports_streaming=True
            )
            await self.bot.delete_message(chat_id=chat_id, message_id=message_id)
            logger.info("Video processed successfully.")
            
        except FFmpegError as e:
            logger.error(f"Task {task_id} failed with FFmpegError: {e}")
            await self.bot.edit_message_text("❌ Во время обработки произошла ошибка FFmpeg.", chat_id=chat_id, message_id=message_id)
        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            await self.bot.edit_message_text("❌ Во время обработки произошла ошибка. Попробуйте ещё раз.", chat_id=chat_id, message_id=message_id)
        finally:
            # Cleanup
            logger.info(f"Cleaning up task {task_id}")
            if os.path.exists(input_path):
                os.remove(input_path)
            if os.path.exists(output_path):
                os.remove(output_path)
            freeze_img = os.path.join(temp_dir, "freeze.png")
            if os.path.exists(freeze_img):
                os.remove(freeze_img)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)

