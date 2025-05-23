# Noitu/noitu.py (Main Bot File)

import discord
from discord.ext import commands
import asyncio
import aiohttp
import traceback

# Import các module cục bộ
from . import config as bot_cfg 
from . import database

# --- LẤY PREFIX ĐỘNG ---
async def get_prefix(bot_instance: commands.Bot, message: discord.Message):
    if not message.guild: # Tin nhắn DM -> dùng prefix mặc định
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)
    
    # Nếu DB chưa sẵn sàng (trong quá trình khởi động sớm) -> fallback
    if not bot_instance.db_pool: 
        # print("Cảnh báo: db_pool chưa sẵn sàng cho get_prefix, dùng prefix mặc định.")
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)

    # Lấy config của guild từ DB
    guild_config_data = await database.get_guild_config(bot_instance.db_pool, message.guild.id)
    
    prefix_to_use = bot_cfg.DEFAULT_COMMAND_PREFIX # Fallback nếu ko có config
    if guild_config_data and "command_prefix" in guild_config_data:
        prefix_to_use = guild_config_data["command_prefix"]
        
    return commands.when_mentioned_or(prefix_to_use)(bot_instance, message)


# --- KHỞI TẠO BOT ---
intents = discord.Intents.default()
intents.message_content = True # Cần để đọc nội dung tin nhắn (cho game, lệnh prefix)
intents.reactions = True # Cần để thêm/xóa reaction
intents.guilds = True # Cần cho on_guild_join và thông tin guild

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None) # Tắt help command mặc định

# Gắn các tài nguyên chia sẻ vào bot instance
bot.db_pool = None # Pool kết nối CSDL
bot.http_session = None # Session HTTP cho API
bot.active_games = {} # Dict lưu trạng thái các game đang chạy {channel_id: game_state}
bot.wiktionary_cache = {} # Cache cho các từ đã tra trên Wiktionary


# --- EVENTS ---
@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đang kết nối và khởi tạo...')

    # Khởi tạo Database Pool (nếu chưa có)
    if not bot.db_pool:
        bot.db_pool = await database.init_db(
            bot_cfg.DATABASE_URL,
            bot_cfg.DEFAULT_COMMAND_PREFIX,
            bot_cfg.DEFAULT_TIMEOUT_SECONDS,
            bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT
        )
    if not bot.db_pool: # Lỗi nghiêm trọng nếu ko có DB
        print("LỖI NGHIÊM TRỌNG: Bot không thể khởi động do lỗi kết nối/khởi tạo Database.")
        await bot.close() 
        return

    # Khởi tạo HTTP Session (nếu chưa có hoặc đã đóng)
    if not bot.http_session or bot.http_session.closed:
        bot.http_session = aiohttp.ClientSession()

    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đã kết nối Discord và sẵn sàng!')
    if bot.application_id:
        # bot_cfg.APPLICATION_ID = bot.application_id # Lưu lại nếu cần, config.py có thể là const
        print(f"Application ID (Client ID): {bot.application_id}")
    else:
        print("Cảnh báo: Không tìm thấy Application ID trên bot instance lúc on_ready.")

    print(f"Trạng thái Database Pool: {'Hoạt động' if bot.db_pool else 'Không hoạt động'}")

    # Tải các Cogs SAU KHI db_pool và http_session sẵn sàng
    # Điều này đảm bảo cogs có thể truy cập self.bot.db_pool, self.bot.http_session trong __init__
    if bot.db_pool: 
        cog_extensions = [
            'Noitu.cogs.general_cog', # Đường dẫn đúng đến các file cog
            'Noitu.cogs.game_cog',
            'Noitu.cogs.admin_cog'
        ]
        for extension in cog_extensions:
            try:
                await bot.load_extension(extension)
                print(f"Đã tải cog: {extension}")
            except Exception as e:
                print(f"Lỗi khi tải cog {extension}: {e}")
                traceback.print_exc()
        
        # Đồng bộ hóa slash commands (sau khi cogs đã load)
        try:
            synced_commands = await bot.tree.sync()
            print(f"Đã đồng bộ {len(synced_commands)} slash commands toàn cục.")
        except Exception as e:
            print(f"Lỗi khi đồng bộ hóa slash commands: {e}")
            traceback.print_exc()
    else: # Không có DB thì ko nên load cog/sync cmd
        print("Cogs chưa được tải và slash commands chưa đồng bộ do Database pool không hoạt động.")

    print(f"Bot sử dụng prefix lệnh động theo từng server (mặc định: {bot_cfg.DEFAULT_COMMAND_PREFIX}).")
    print(f"Để xem hướng dẫn, người dùng có thể gõ: <prefix>help hoặc /help trong server.")


# --- MAIN FUNCTION ---
async def main():
    # Kiểm tra các biến môi trường thiết yếu
    if not bot_cfg.BOT_TOKEN:
        print("LỖI NGHIÊM TRỌNG: BOT_TOKEN không được tìm thấy trong config.")
        return
    if not bot_cfg.DATABASE_URL: 
        print("LỖI NGHIÊM TRỌNG: DATABASE_URL không được tìm thấy trong config.")
        return

    # db_pool, http_session, và cogs được xử lý trong on_ready

    try:
        # async with bot đảm bảo bot.start và bot.close được gọi đúng cách
        async with bot: 
            await bot.start(bot_cfg.BOT_TOKEN)
    except discord.errors.LoginFailure: # Sai token
        print("LỖI NGHIÊM TRỌNG: Token bot không hợp lệ.")
    except Exception as e: # Các lỗi khác khi chạy bot
        print(f"LỖI không xác định khi chạy bot: {e}")
        traceback.print_exc()
    finally:
        # Dọn dẹp tài nguyên khi bot tắt
        if bot.http_session and not bot.http_session.closed:
            await bot.http_session.close()
            print("HTTP session đã đóng.")
        if bot.db_pool:
            await bot.db_pool.close()
            print("Kết nối Database (pool) đã đóng.")
        print(f"Số mục trong Wiktionary cache: {len(bot.wiktionary_cache)}")
        print("Bot đã tắt.")


if __name__ == "__main__":
    # discord.utils.setup_logging() # Bật logging của discord.py nếu cần chi tiết hơn
    try:
        asyncio.run(main())
    except KeyboardInterrupt: # Ctrl+C
        print("Bot đang tắt do KeyboardInterrupt...")
    # `finally` trong `main` sẽ xử lý việc đóng các kết nối