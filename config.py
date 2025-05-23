# Noitu/config.py
import os
import dotenv

# --- TẢI BIẾN MÔI TRƯỜNG ---
dotenv.load_dotenv()

# --- CẤU HÌNH ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Default global fallbacks nếu DB config ko tìm thấy
DEFAULT_COMMAND_PREFIX = "!"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MIN_PLAYERS_FOR_TIMEOUT = 2

WRONG_TURN_REACTION = "⚠️"
CORRECT_REACTION = "✅"
ERROR_REACTION = "❌"
DELETE_WRONG_TURN_MESSAGE_AFTER = 10


APPLICATION_ID = None 