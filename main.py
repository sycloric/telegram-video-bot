import asyncio
import sys
from aiogram import Bot, Dispatcher
from bot.config import BOT_TOKEN
from bot.utils.logger import logger
from bot.handlers import user_handlers, settings_handlers
from media.processor import VideoProcessor

import os
from aiohttp import web

async def ping_handler(request):
    return web.Response(text="Bot is running!")

async def start_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get('/', ping_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dummy web server started on port {port}")

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set in .env")
        sys.exit(1)
        
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    processor = VideoProcessor(bot)
    await processor.start()
    
    user_handlers.setup_handlers(dp, processor)
    dp.include_router(settings_handlers.router)
    
    # Start dummy server if we are on Render (PORT env var is present)
    if os.environ.get("RENDER") or os.environ.get("PORT"):
        await start_dummy_server()
    
    logger.info("Starting bot...")
    try:
        # Drop pending updates
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await processor.stop()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")

