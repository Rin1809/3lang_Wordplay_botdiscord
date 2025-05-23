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

# --- Emoji & Icons ---
BOT_PLAYER_START_EMOJI = "<a:HanaCheer2:1375494213713789058>" # Emoji user yêu cầu
USER_PLAYER_START_EMOJI = "<a:HanaCheer2:1375494213713789058>"

GAME_VN_ICON = "🇻🇳"
GAME_JP_ICON = "🇯🇵"

GAME_START_ICON = "🚀"
WIN_ICON = "🎉" 
TIMEOUT_WIN_ICON = "🏆"
SHIRITORI_LOSS_WIN_ICON = "🥳" 
PLAYER_LOSS_ICON = "💔" 
STOP_ICON = "🛑"

CONFIG_ICON = "⚙️"
LEADERBOARD_ICON = "📊"
HELP_ICON = "ℹ️"
RULES_ICON = "📜" 

# Embed Colors
EMBED_COLOR_GAME_START = 0x5865F2 # Discord Blurple
EMBED_COLOR_WIN = 0xFFD700 # Gold
EMBED_COLOR_LOSS = 0xE74C3C # Red
EMBED_COLOR_STOP = 0xFFA500 # Orange
EMBED_COLOR_INFO = 0x3498DB # Blue
EMBED_COLOR_LEADERBOARD = 0xFFD700 # Gold
EMBED_COLOR_HELP = 0x1ABC9C # Teal
EMBED_COLOR_CONFIG = 0x7289DA # Discord Greyple