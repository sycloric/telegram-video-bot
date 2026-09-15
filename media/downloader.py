import asyncio
import os
import uuid
from bot.utils.logger import logger

async def download_tiktok(url: str, output_dir: str) -> str:
    """
    Downloads a TikTok video using yt-dlp.
    Returns the path to the downloaded file.
    Raises Exception if failed.
    """
    os.makedirs(output_dir, exist_ok=True)
    output_template = os.path.join(output_dir, f"tiktok_{uuid.uuid4().hex[:8]}.%(ext)s")
    
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '-f', 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '-o', output_template,
        url
    ]
    
    logger.info(f"Downloading TikTok: {url}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        logger.error(f"yt-dlp failed: {err_msg}")
        raise Exception(f"Не удалось скачать видео. Возможно, оно приватное или удалено.\n\nДетали:\n{err_msg[:200]}")
    
    # Find the downloaded file
    for file in os.listdir(output_dir):
        if file.startswith("tiktok_") and file.endswith(".mp4"):
            return os.path.join(output_dir, file)
            
    raise Exception("Файл скачан, но не найден в папке (возможно, неверный формат).")

