# Noitu/noitu.py (Main Bot File)

import discord
from discord.ext import commands
import asyncio
import aiohttp
import traceback
import os 
import csv 

from . import config as bot_cfg
from . import database
from . import utils 

try:
    from pykakasi import kakasi
    kks_instance = kakasi() # Renamed for clarity
    kakasi_converter = kks_instance 
    try:
        test_conversion = kakasi_converter.convert("テスト")
        if not test_conversion or not isinstance(test_conversion, list) or not ('hira' in test_conversion[0]):
            raise ValueError("Kết quả convert() không như mong đợi.")
        print(f"PyKakasi initialized and conversion test successful. Example: {test_conversion}")
    except Exception as e_test:
        print(f"PyKakasi initialized, but conversion test failed: {e_test}")
        print("Chức năng tiếng Nhật có thể bị ảnh hưởng.")
except ImportError:
    kakasi_converter = None
    print("LỖI: Thư viện PyKakasi chưa được cài đặt. Chức năng tiếng Nhật sẽ bị hạn chế.")
    print("Vui lòng chạy: pip install pykakasi")
except Exception as e: 
    kakasi_converter = None
    print(f"LỖI: Không thể khởi tạo PyKakasi: {e}")
    traceback.print_exc()

async def get_prefix(bot_instance: commands.Bot, message: discord.Message):
    if not message.guild: 
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)
    if not bot_instance.db_pool:
        return commands.when_mentioned_or(bot_cfg.DEFAULT_COMMAND_PREFIX)(bot_instance, message)
    guild_config_data = await database.get_guild_config(bot_instance.db_pool, message.guild.id)
    prefix_to_use = bot_cfg.DEFAULT_COMMAND_PREFIX 
    if guild_config_data and "command_prefix" in guild_config_data:
        prefix_to_use = guild_config_data["command_prefix"]
    return commands.when_mentioned_or(prefix_to_use)(bot_instance, message)

intents = discord.Intents.default()
intents.message_content = True 
intents.reactions = True 
intents.guilds = True 

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None) 

bot.db_pool = None 
bot.http_session = None 
bot.active_games = {} 
bot.wiktionary_cache_vn = {} 
bot.wiktionary_cache_jp = {} 
bot.local_dictionary_vn = set() 
bot.local_dictionary_jp = [] 
bot.kakasi = kakasi_converter 

async def load_vietnamese_dictionary(bot_instance: commands.Bot, file_path="tudien-vn.txt"): # Corrected file name
    script_dir = os.path.dirname(__file__)
    absolute_file_path = os.path.join(script_dir, file_path)
    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip().lower()
                if word:
                    bot_instance.local_dictionary_vn.add(word)
        print(f"Đã tải {len(bot_instance.local_dictionary_vn)} từ vào từ điển Tiếng Việt từ '{file_path}'.")
    except FileNotFoundError:
        print(f"LỖI: File từ điển Tiếng Việt '{absolute_file_path}' ko tìm thấy.")
    except Exception as e:
        print(f"Lỗi tải từ điển Tiếng Việt: {e}")
        traceback.print_exc()

async def load_japanese_dictionary(bot_instance: commands.Bot, file_path="tudien-jp.txt"): # Corrected file name
    script_dir = os.path.dirname(__file__)
    absolute_file_path = os.path.join(script_dir, file_path)
    loaded_count = 0
    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            # Assuming CSV format: kanji,hira,roma
            reader = csv.reader(f) 
            for row in reader:
                if len(row) >= 2: # Need at least kanji/hira and hira
                    kanji_or_kana = row[0].strip()
                    hira = row[1].strip()
                    roma = row[2].strip() if len(row) >= 3 else ""
                    
                    if hira: # Hiragana is essential
                        entry = {'kanji': kanji_or_kana if kanji_or_kana else hira, 'hira': hira, 'roma': roma}
                        bot_instance.local_dictionary_jp.append(entry)
                        loaded_count += 1
        print(f"Đã tải {loaded_count} từ vào từ điển Tiếng Nhật từ '{file_path}'.")
    except FileNotFoundError:
        print(f"LỖI: File từ điển Tiếng Nhật '{absolute_file_path}' ko tìm thấy.")
    except Exception as e:
        print(f"Lỗi tải từ điển Tiếng Nhật: {e}")
        traceback.print_exc()

@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đang kết nối và khởi tạo...')

    if not bot.db_pool:
        bot.db_pool = await database.init_db( # Removed default_language parameter
            bot_cfg.DATABASE_URL,
            bot_cfg.DEFAULT_COMMAND_PREFIX,
            bot_cfg.DEFAULT_TIMEOUT_SECONDS,
            bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT
        )
    if not bot.db_pool: 
        print("LỖI NGHIÊM TRỌNG: Bot không thể khởi động do lỗi DB.")
        await bot.close()
        return

    if not bot.http_session or bot.http_session.closed:
        bot.http_session = aiohttp.ClientSession()

    await load_vietnamese_dictionary(bot)
    await load_japanese_dictionary(bot) # Ensure this uses CSV reader

    print(f'Bot {bot.user.name} (ID: {bot.user.id}) đã kết nối Discord và sẵn sàng!')
    if not bot.application_id and not bot_cfg.APPLICATION_ID:
        try:
            app_info = await bot.application_info()
            bot_cfg.APPLICATION_ID = app_info.id 
            bot.application_id = app_info.id 
        except Exception as e:
            print(f"Không thể tự động lấy Application ID: {e}")

    if bot.application_id:
        print(f"Application ID (Client ID): {bot.application_id}")
    else:
        print("Cảnh báo: Ko tìm thấy Application ID.")

    print(f"DB Pool: {'Hoạt động' if bot.db_pool else 'Ko hoạt động'}")
    print(f"Kakasi (JP): {'Sẵn sàng' if bot.kakasi else 'Không khả dụng'}")

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
        try:
            if bot.application_id:
                synced_commands = await bot.tree.sync()
                print(f"Đã đồng bộ {len(synced_commands)} slash commands.")
            else:
                print("Bỏ qua đồng bộ slash commands vì không có Application ID.")
        except Exception as e:
            print(f"Lỗi đồng bộ slash commands: {e}")
            traceback.print_exc()
    else:
        print("Cogs và slash commands chưa được xử lý do lỗi DB.")

    print(f"Prefix động theo server (mặc định: {bot_cfg.DEFAULT_COMMAND_PREFIX}).")
    # print(f"Ngôn ngữ game mặc định: {bot_cfg.DEFAULT_GAME_LANGUAGE}.") # Removed
    print(f"Ngôn ngữ game được xác định theo từng kênh (cấu hình qua /config).")
    print(f"Hướng dẫn: <prefix>help hoặc /help.")

async def main():
    if not bot_cfg.BOT_TOKEN:
        print("LỖI NGHIÊM TRỌNG: BOT_TOKEN thiếu.")
        return
    if not bot_cfg.DATABASE_URL:
        print("LỖI NGHIÊM TRỌNG: DATABASE_URL thiếu.")
        return
    
    if not bot.kakasi: 
        print("CẢNH BÁO: PyKakasi không được khởi tạo. Chức năng tiếng Nhật có thể không hoạt động đúng.")

    try:
        async with bot:
            await bot.start(bot_cfg.BOT_TOKEN)
    except discord.errors.LoginFailure: 
        print("LỖI NGHIÊM TRỌNG: Token bot không hợp lệ.")
    except Exception as e: 
        print(f"LỖI ko xđ khi chạy bot: {e}")
        traceback.print_exc()
    finally:
        if bot.http_session and not bot.http_session.closed:
            await bot.http_session.close()
            print("HTTP session đã đóng.")
        if bot.db_pool:
            await bot.db_pool.close()
            print("DB pool đã đóng.")
        print(f"Wiktionary VN cache: {len(bot.wiktionary_cache_vn)} mục.")
        print(f"Wiktionary JP cache: {len(bot.wiktionary_cache_jp)} mục.")
        print(f"Từ điển local VN: {len(bot.local_dictionary_vn)} từ.")
        print(f"Từ điển local JP: {len(bot.local_dictionary_jp)} từ.")
        print("Bot đã tắt.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt: 
        print("Bot đang tắt do KeyboardInterrupt...")