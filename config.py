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

# URLs Wiktionary
VIETNAMESE_WIKTIONARY_API_URL = "https://vi.wiktionary.org/w/api.php"
JAPANESE_WIKTIONARY_API_URL = "https://ja.wiktionary.org/w/api.php"


WRONG_TURN_REACTION = "⚠️"
CORRECT_REACTION = "✅"
ERROR_REACTION = "❌"
SHIRITORI_LOSS_REACTION = "🛑" # For 'ん' rule
DELETE_WRONG_TURN_MESSAGE_AFTER = 10


APPLICATION_ID = None