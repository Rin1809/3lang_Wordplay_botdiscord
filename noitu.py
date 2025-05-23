# Noitu/noitu.py (Main Bot File)

import discord
from discord.ext import commands
import asyncio
import aiohttp
import traceback
import os # path

# Import các module cục bộ
from . import config as bot_cfg
from . import database

# --- LẤY PREFIX ĐỘNG ---
async def get_prefix(bot_instance: commands.Bot, message: discord.Message):
    if not message.guild: # DM -> prefix mặc định
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)

    # DB chưa sẵn sàng -> fallback
    if not bot_instance.db_pool:
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)

    # Lấy config guild từ DB
    guild_config_data = await database.get_guild_config(bot_instance.db_pool, message.guild.id)

    prefix_to_use = bot_cfg.DEFAULT_COMMAND_PREFIX # Fallback nếu ko có config
    if guild_config_data and "command_prefix" in guild_config_data:
        prefix_to_use = guild_config_data["command_prefix"]

    return commands.when_mentioned_or(prefix_to_use)(bot_instance, message)


# --- KHỞI TẠO BOT ---
intents = discord.Intents.default()
intents.message_content = True # Đọc msg (game, prefix cmd)
intents.reactions = True # Thêm/xóa reaction
intents.guilds = True # on_guild_join, guild info

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None) # Tắt help cmd mặc định

# Tài nguyên chia sẻ
bot.db_pool = None # DB pool
bot.http_session = None # HTTP session
bot.active_games = {} # {channel_id: game_state}
bot.wiktionary_cache = {} # Cache Wiktionary
bot.local_dictionary = set() # Từ điển local

# --- TẢI TỪ ĐIỂN LOCAL ---
async def load_local_dictionary(bot_instance: commands.Bot, file_path="tudien.txt"):
    script_dir = os.path.dirname(__file__) # Thư mục hiện tại
    absolute_file_path = os.path.join(script_dir, file_path) # Đường dẫn tuyệt đối

    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f: # Đọc file UTF-8
            for line in f:
                word = line.strip().lower() # Chuẩn hóa
                if word: # Ko thêm dòng rỗng
                    bot_instance.local_dictionary.add(word)
        print(f"Đã tải {len(bot_instance.local_dictionary)} từ vào từ điển local từ '{file_path}'.")
    except FileNotFoundError:
        print(f"LỖI: File từ điển '{absolute_file_path}' ko tìm thấy. Sẽ dùng Wiktionary.")
    except Exception as e:
        print(f"Lỗi tải từ điển local: {e}")
        traceback.print_exc()

# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đang kết nối và khởi tạo...')

    # Init DB Pool
    if not bot.db_pool:
        bot.db_pool = await database.init_db(
            bot_cfg.DATABASE_URL,
            bot_cfg.DEFAULT_COMMAND_PREFIX,
            bot_cfg.DEFAULT_TIMEOUT_SECONDS,
            bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT
        )
    if not bot.db_pool: # Lỗi DB nghiêm trọng
        print("LỖI NGHIÊM TRỌNG: Bot không thể khởi động do lỗi DB.")
        await bot.close()
        return

    # Init HTTP Session
    if not bot.http_session or bot.http_session.closed:
        bot.http_session = aiohttp.ClientSession()

    # Tải từ điển local
    await load_local_dictionary(bot)

    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đã kết nối Discord và sẵn sàng!')
    if bot.application_id:
        print(f"Application ID (Client ID): {bot.application_id}")
    else:
        print("Cảnh báo: Ko tìm thấy Application ID.")

    print(f"DB Pool: {'Hoạt động' if bot.db_pool else 'Ko hoạt động'}")

    # Tải Cogs KHI db_pool và http_session SẴN SÀNG
    if bot.db_pool:
        cog_extensions = [
            'Noitu.cogs.general_cog',
            'Noitu.cogs.game_cog',
            'Noitu.cogs.admin_cog'
        ]
        for extension in cog_extensions:
            try:
                await bot.load_extension(extension)
                print(f"Đã tải cog: {extension}")
            except Exception as e:
                print(f"Lỗi tải cog {extension}: {e}")
                traceback.print_exc()

        # Đồng bộ slash commands
        try:
            synced_commands = await bot.tree.sync()
            print(f"Đã đồng bộ {len(synced_commands)} slash commands.")
        except Exception as e:
            print(f"Lỗi đồng bộ slash commands: {e}")
            traceback.print_exc()
    else:
        print("Cogs và slash commands chưa được xử lý do lỗi DB.")

    print(f"Prefix động theo server (mặc định: {bot_cfg.DEFAULT_COMMAND_PREFIX}).")
    print(f"Hướng dẫn: <prefix>help hoặc /help.")


# --- MAIN FUNCTION ---
async def main():
    # Check env vars
    if not bot_cfg.BOT_TOKEN:
        print("LỖI NGHIÊM TRỌNG: BOT_TOKEN thiếu.")
        return
    if not bot_cfg.DATABASE_URL:
        print("LỖI NGHIÊM TRỌNG: DATABASE_URL thiếu.")
        return

    try:
        async with bot:
            await bot.start(bot_cfg.BOT_TOKEN)
    except discord.errors.LoginFailure: # Sai token
        print("LỖI NGHIÊM TRỌNG: Token bot không hợp lệ.")
    except Exception as e: # Lỗi khác
        print(f"LỖI ko xđ khi chạy bot: {e}")
        traceback.print_exc()
    finally:
        # Dọn dẹp
        if bot.http_session and not bot.http_session.closed:
            await bot.http_session.close()
            print("HTTP session đã đóng.")
        if bot.db_pool:
            await bot.db_pool.close()
            print("DB pool đã đóng.")
        print(f"Wiktionary cache: {len(bot.wiktionary_cache)} mục.")
        print(f"Từ điển local: {len(bot.local_dictionary)} từ.") # Log thêm
        print("Bot đã tắt.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt: # Ctrl+C
        print("Bot đang tắt do KeyboardInterrupt...")