import asyncio
import json
from bot.utils.logger import logger
from bot.config import FFPROBE_PATH
from media.ffmpeg import FFmpegError

async def probe_video(file_path: str) -> dict:
    cmd = [
        FFPROBE_PATH,
        '-v', 'error',
        '-show_entries', 'format=duration:stream=width,height,codec_type',
        '-of', 'json',
        file_path
    ]
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFprobe failed: {stderr.decode()}")
            raise FFmpegError("Failed to probe video.")
            
        data = json.loads(stdout.decode())
        duration = float(data['format'].get('duration', 0))
        has_audio = False
        has_video = False
        width = 0
        height = 0
        
        for stream in data.get('streams', []):
            if stream['codec_type'] == 'video':
                has_video = True
                width = int(stream.get('width', 0))
                height = int(stream.get('height', 0))
            elif stream['codec_type'] == 'audio':
                has_audio = True
                
        return {
            "duration": duration,
            "has_audio": has_audio,
            "has_video": has_video,
            "width": width,
            "height": height
        }
    except Exception as e:
        logger.error(f"Error in probe_video: {e}")
        raise FFmpegError(f"Probe error: {e}")

