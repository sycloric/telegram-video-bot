import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
AD_VIDEO_PATH = os.getenv("AD_VIDEO_PATH", "assets/advertisement.mp4")
FREEZE_DURATION = float(os.getenv("FREEZE_DURATION", "1.0"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
MIN_VIDEO_DURATION = float(os.getenv("MIN_VIDEO_DURATION", "5.0"))
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")

CHROMA_KEY_COLOR = os.getenv("CHROMA_KEY_COLOR", "0x00ff00")
CHROMA_SIMILARITY = float(os.getenv("CHROMA_SIMILARITY", "0.25"))
CHROMA_BLEND = float(os.getenv("CHROMA_BLEND", "0.1"))
AD_SCALE = float(os.getenv("AD_SCALE", "1.0"))
AD_POSITION_X = os.getenv("AD_POSITION_X", "center")
AD_POSITION_Y = os.getenv("AD_POSITION_Y", "center")

