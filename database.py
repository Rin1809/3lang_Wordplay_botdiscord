# Noitu/database.py
import asyncpg
import traceback
from . import config as bot_cfg

async def init_db(database_url: str, default_prefix: str, default_timeout: int, default_min_players: int, default_language: str): 
    if not database_url:
        print("LỖI: DATABASE_URL ko tìm thấy. Check .env or config.py")
        return None
    try:
        pool = await asyncpg.create_pool(database_url)
        async with pool.acquire() as connection:
            # Guild Configs
            await connection.execute(f'''
                CREATE TABLE IF NOT EXISTS guild_configs (
                    guild_id BIGINT PRIMARY KEY,
                    command_prefix VARCHAR(5) DEFAULT '{default_prefix}',
                    timeout_seconds INTEGER DEFAULT {default_timeout},
                    min_players_for_timeout INTEGER DEFAULT {default_min_players},
                    game_language VARCHAR(2) DEFAULT '{default_language}' 
                );
            ''') 

            # Leaderboard Stats
            await connection.execute('''
                CREATE TABLE IF NOT EXISTS leaderboard_stats (
                    user_id BIGINT NOT NULL,
                    guild_id BIGINT NOT NULL,
                    name VARCHAR(100),
                    wins INTEGER DEFAULT 0,
                    correct_moves INTEGER DEFAULT 0,
                    wrong_word_link INTEGER DEFAULT 0,
                    invalid_wiktionary INTEGER DEFAULT 0,
                    used_word_error INTEGER DEFAULT 0,
                    wrong_turn INTEGER DEFAULT 0,
                    current_win_streak INTEGER DEFAULT 0,
                    max_win_streak INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                );
            ''')
        print("DB connected, tables initialized.")
        return pool
    except Exception as e:
        print(f"Lỗi kết nối/khởi tạo DB: {e}")
        traceback.print_exc()
        return None

async def get_guild_config(db_pool: asyncpg.Pool, guild_id: int):
    if not db_pool: return None # Guard clause
    async with db_pool.acquire() as connection:
        # Thêm game_language vào câu SELECT
        row = await connection.fetchrow("SELECT command_prefix, timeout_seconds, min_players_for_timeout, game_language FROM guild_configs WHERE guild_id = $1", guild_id)
        if row:
            return dict(row)
        
        # Tạo config mặc định nếu chưa có, dùng giá trị từ bot_cfg
        await connection.execute(
            "INSERT INTO guild_configs (guild_id, command_prefix, timeout_seconds, min_players_for_timeout, game_language) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (guild_id) DO NOTHING", # Thêm game_language
            guild_id, bot_cfg.DEFAULT_COMMAND_PREFIX, bot_cfg.DEFAULT_TIMEOUT_SECONDS, bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT, bot_cfg.DEFAULT_GAME_LANGUAGE # Thêm giá trị default
        )
        # Lấy lại để đảm bảo trả về config (kể cả mới tạo)
        row_after_insert = await connection.fetchrow("SELECT command_prefix, timeout_seconds, min_players_for_timeout, game_language FROM guild_configs WHERE guild_id = $1", guild_id)
        if row_after_insert:
            return dict(row_after_insert)
        
        # Fallback cuối cùng (ít khi xảy ra)
        return {
            "command_prefix": bot_cfg.DEFAULT_COMMAND_PREFIX, 
            "timeout_seconds": bot_cfg.DEFAULT_TIMEOUT_SECONDS, 
            "min_players_for_timeout": bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT,
            "game_language": bot_cfg.DEFAULT_GAME_LANGUAGE # Thêm game_language
        }


async def set_guild_config_value(db_pool: asyncpg.Pool, guild_id: int, key: str, value):
    if not db_pool: return False
    allowed_keys = ["command_prefix", "timeout_seconds", "min_players_for_timeout", "game_language"] # Thêm game_language
    if key not in allowed_keys: return False
    async with db_pool.acquire() as connection:
        # Đảm bảo entry tồn tại trước khi update, dùng giá trị từ bot_cfg
        await connection.execute(
            "INSERT INTO guild_configs (guild_id, command_prefix, timeout_seconds, min_players_for_timeout, game_language) VALUES ($1, $2, $3, $4, $5) ON CONFLICT (guild_id) DO NOTHING", # Thêm game_language
            guild_id, bot_cfg.DEFAULT_COMMAND_PREFIX, bot_cfg.DEFAULT_TIMEOUT_SECONDS, bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT, bot_cfg.DEFAULT_GAME_LANGUAGE # Thêm giá trị default
        )
        await connection.execute(f"UPDATE guild_configs SET {key} = $1 WHERE guild_id = $2", value, guild_id)
    return True

async def get_user_stats_entry(db_pool: asyncpg.Pool, user_id: int, guild_id: int, username: str = "Unknown User"):
    if not db_pool: return None
    async with db_pool.acquire() as connection:
        stats = await connection.fetchrow(
            "SELECT * FROM leaderboard_stats WHERE user_id = $1 AND guild_id = $2",
            user_id, guild_id
        )
        if not stats: # Nếu user chưa có -> tạo mới
            await connection.execute(
                """
                INSERT INTO leaderboard_stats (user_id, guild_id, name)
                VALUES ($1, $2, $3);
                """, user_id, guild_id, username
            )
            stats = await connection.fetchrow( # Lấy lại entry vừa tạo
                 "SELECT * FROM leaderboard_stats WHERE user_id = $1 AND guild_id = $2", user_id, guild_id
            )
        # Cập nhật tên user nếu có thay đổi
        if stats and username and stats['name'] != username and username != "Unknown User":
            await connection.execute(
                "UPDATE leaderboard_stats SET name = $1 WHERE user_id = $2 AND guild_id = $3",
                username, user_id, guild_id
            )
            stats = await connection.fetchrow( # Lấy lại để có tên mới nhất
                 "SELECT * FROM leaderboard_stats WHERE user_id = $1 AND guild_id = $2", user_id, guild_id
            )
        return dict(stats) if stats else None


async def update_stat(db_pool: asyncpg.Pool, bot_user_id: int, user_id: int, guild_id: int, stat_key: str, username: str, increment: int = 1):
    if user_id == bot_user_id or not db_pool: return # Ko theo dõi stat của bot

    # Đảm bảo entry tồn tại và tên user là mới nhất
    stats = await get_user_stats_entry(db_pool, user_id, guild_id, username)
    if not stats:
        print(f"Không thể lấy/tạo entry cho user {user_id} guild {guild_id} để cập nhật stat.")
        return

    async with db_pool.acquire() as connection:
        if stat_key == "wins":
            await connection.execute(
                """
                UPDATE leaderboard_stats
                SET wins = wins + $1,
                    current_win_streak = current_win_streak + 1,
                    max_win_streak = GREATEST(max_win_streak, current_win_streak + 1)
                WHERE user_id = $2 AND guild_id = $3;
                """, increment, user_id, guild_id
            )
        elif stat_key in ["wrong_word_link", "invalid_wiktionary", "used_word_error", "wrong_turn"]:
            # Các lỗi này reset win streak
            await connection.execute(
                f"""
                UPDATE leaderboard_stats
                SET {stat_key} = {stat_key} + $1,
                    current_win_streak = 0
                WHERE user_id = $2 AND guild_id = $3;
                """, increment, user_id, guild_id
            )
        else: # Cho các stat khác như 'correct_moves'
            await connection.execute(
                f"UPDATE leaderboard_stats SET {stat_key} = {stat_key} + $1 WHERE user_id = $2 AND guild_id = $3",
                increment, user_id, guild_id
            )

async def reset_win_streak_for_user(db_pool: asyncpg.Pool, user_id: int, guild_id: int):
    if not db_pool: return
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE leaderboard_stats SET current_win_streak = 0 WHERE user_id = $1 AND guild_id = $2", user_id, guild_id)