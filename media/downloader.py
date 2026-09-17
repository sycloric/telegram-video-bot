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
    video_id = uuid.uuid4().hex[:8]
    output_template = os.path.join(output_dir, f"tiktok_{video_id}.%(ext)s")
    
    cmd = [
        'yt-dlp',
        '--no-playlist',
        '-f', 'bestvideo+bestaudio/best',
        '--merge-output-format', 'mp4',
        '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
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
        raise Exception(f"Не удалось скачать видео. Возможно, приватное или недоступно.\n\nОшибка:\n{err_msg[:200]}")
    
    # Find the downloaded file
    prefix = f"tiktok_{video_id}"
    for file in os.listdir(output_dir):
        if file.startswith(prefix) and file.endswith(".mp4"):
            return os.path.join(output_dir, file)
            
    raise Exception("Не удалось найти скачанный файл (возможно, проблема с форматом).")
