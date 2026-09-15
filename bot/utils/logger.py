import logging
import sys
from bot.config import LOG_LEVEL

def setup_logger():
    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    logger = logging.getLogger("telegram_video_bot")
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

logger = setup_logger()

