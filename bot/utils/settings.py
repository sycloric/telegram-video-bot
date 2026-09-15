import sqlite3
import os
from typing import Dict, Any
from bot.utils.logger import logger

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "user_settings.db")

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                chat_id INTEGER PRIMARY KEY,
                ad_path TEXT,
                effect TEXT DEFAULT 'Classic',
                position TEXT DEFAULT 'Middle',
                aspect_ratio TEXT DEFAULT 'Original',
                quality TEXT DEFAULT 'Balance'
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error initializing DB: {e}")

def get_user_settings(chat_id: int) -> Dict[str, Any]:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user_settings WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        else:
            return {
                "chat_id": chat_id,
                "ad_path": None, # Will fallback to AD_VIDEO_PATH
                "effect": "Classic",
                "position": "Middle",
                "aspect_ratio": "Original",
                "quality": "Balance"
            }
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return {"effect": "Classic", "position": "Middle", "aspect_ratio": "Original", "quality": "Balance", "ad_path": None}

def update_user_setting(chat_id: int, key: str, value: Any):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Upsert logic
        cursor.execute("SELECT 1 FROM user_settings WHERE chat_id = ?", (chat_id,))
        exists = cursor.fetchone()
        
        if exists:
            # We can use parameterized dynamic column name safely if we validate it
            valid_keys = ['ad_path', 'effect', 'position', 'aspect_ratio', 'quality']
            if key in valid_keys:
                cursor.execute(f"UPDATE user_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        else:
            valid_keys = ['chat_id', 'ad_path', 'effect', 'position', 'aspect_ratio', 'quality']
            if key in valid_keys:
                cursor.execute(f"INSERT INTO user_settings (chat_id, {key}) VALUES (?, ?)", (chat_id, value))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error updating setting: {e}")

init_db()

