# Noitu/noitu.py

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

kakasi_converter = None # Khởi tạo là None
pykakasi_load_error_message = "" # Lưu trữ thông báo lỗi nếu có

try:
    from pykakasi import kakasi # type: ignore
    kks_instance = kakasi()
    try:
        # Test với một từ Katakana và một từ có Kanji/Hiragana
        test_conversion_kata = kks_instance.convert("テスト") # Test
        test_conversion_kanji = kks_instance.convert("言葉") # Kotoba
        if not test_conversion_kata or not isinstance(test_conversion_kata, list) or not ('hira' in test_conversion_kata[0]):
            raise ValueError("Kq cv Katakana k như mong đợi.")
        if not test_conversion_kanji or not isinstance(test_conversion_kanji, list) or not ('hira' in test_conversion_kanji[0]):
            raise ValueError("Kq cv Kanji k như mong đợi.")
        kakasi_converter = kks_instance # Chỉ gán nếu test thành công
        print(f"PyKakasi initialized successfully. Katakana test: {test_conversion_kata}, Kanji test: {test_conversion_kanji}")
    except Exception as e_test:
        pykakasi_load_error_message = f"PyKakasi initialized, but conversion test FAILED: {e_test}. Japanese features might be impaired."
        print(pykakasi_load_error_message)
        # kakasi_converter vẫn là None
except ImportError:
    pykakasi_load_error_message = "CRITICAL ERROR: PyKakasi library not installed. Japanese features will be SEVERELY limited or non-functional. Please run: pip install pykakasi"
    print(pykakasi_load_error_message)
    # kakasi_converter vẫn là None
except Exception as e_init:
    pykakasi_load_error_message = f"CRITICAL ERROR: Could not initialize PyKakasi: {e_init}. Japanese features will be SEVERELY limited or non-functional."
    print(pykakasi_load_error_message)
    traceback.print_exc()
    # kakasi_converter vẫn là None


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
bot.kakasi = kakasi_converter # Gán instance đã được test (hoặc None)
bot.pykakasi_load_error = pykakasi_load_error_message # Lưu lỗi để cog có thể truy cập

async def load_vietnamese_dictionary(bot_instance: commands.Bot, file_path="tudien-vn.txt"):
    script_dir = os.path.dirname(__file__)
    absolute_file_path = os.path.join(script_dir, file_path)
    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                word = line.strip().lower()
                if word:
                    bot_instance.local_dictionary_vn.add(word)
        print(f"Loaded {len(bot_instance.local_dictionary_vn)} words into Vietnamese dictionary from '{file_path}'.")
    except FileNotFoundError:
        print(f"ERROR: Vietnamese dictionary file '{absolute_file_path}' not found.")
    except Exception as e:
        print(f"Error loading Vietnamese dictionary: {e}")
        traceback.print_exc()

async def load_japanese_dictionary(bot_instance: commands.Bot, file_path="tudien-jp.txt"):
    script_dir = os.path.dirname(__file__)
    absolute_file_path = os.path.join(script_dir, file_path)
    loaded_count = 0
    try:
        with open(absolute_file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    kanji_or_kana = row[0].strip()
                    hira = row[1].strip()
                    roma = row[2].strip() if len(row) >= 3 else ""

                    if hira:
                        entry = {'kanji': kanji_or_kana if kanji_or_kana else hira, 'hira': hira, 'roma': roma}
                        bot_instance.local_dictionary_jp.append(entry)
                        loaded_count += 1
        print(f"Loaded {loaded_count} words into Japanese dictionary from '{file_path}'.")
    except FileNotFoundError:
        print(f"ERROR: Japanese dictionary file '{absolute_file_path}' not found.")
    except Exception as e:
        print(f"Error loading Japanese dictionary: {e}")
        traceback.print_exc()

@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} (ID: {bot.user.id}) connecting and initializing...')

    if not bot.db_pool:
        bot.db_pool = await database.init_db(
            bot_cfg.DATABASE_URL,
            bot_cfg.DEFAULT_COMMAND_PREFIX,
            bot_cfg.DEFAULT_TIMEOUT_SECONDS,
            bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT
        )
    if not bot.db_pool:
        print("CRITICAL ERROR: Bot cannot start due to DB error.")
        await bot.close()
        return

    if not bot.http_session or bot.http_session.closed:
        bot.http_session = aiohttp.ClientSession()

    await load_vietnamese_dictionary(bot)
    await load_japanese_dictionary(bot)

    print(f'Bot {bot.user.name} (ID: {bot.user.id}) connected to Discord and ready!')
    if not hasattr(bot, 'application_id') or not bot.application_id: # Check if attr exists before use
      if not bot_cfg.APPLICATION_ID:
          try:
              app_info = await bot.application_info()
              bot_cfg.APPLICATION_ID = app_info.id
              bot.application_id = app_info.id # type: ignore
          except Exception as e:
              print(f"Could not automatically fetch Application ID: {e}")
      else: # Use from bot_cfg if available
          bot.application_id = bot_cfg.APPLICATION_ID # type: ignore


    if hasattr(bot, 'application_id') and bot.application_id:
        print(f"Application ID (Client ID): {bot.application_id}")
    else:
        print("Warning: Application ID not found.")

    print(f"DB Pool: {'Active' if bot.db_pool else 'Inactive'}")
    if bot.kakasi:
        print("PyKakasi (JP): Ready and Tested.")
    else:
        print(f"PyKakasi (JP): NOT AVAILABLE or FAILED. Reason: {bot.pykakasi_load_error if bot.pykakasi_load_error else 'Unknown initialization error.'}")


    if bot.db_pool:
        cog_extensions = [
            'Noitu.cogs.general_cog',
            'Noitu.cogs.game_cog',
            'Noitu.cogs.admin_cog'
        ]
        for extension in cog_extensions:
            try:
                await bot.load_extension(extension)
                print(f"Loaded cog: {extension}")
            except Exception as e:
                print(f"Failed to load cog {extension}: {e}")
                traceback.print_exc()
        try:
            if hasattr(bot, 'application_id') and bot.application_id:
                synced_commands = await bot.tree.sync()
                print(f"Synced {len(synced_commands)} slash commands.")
            else:
                print("Skipping slash command sync due to missing Application ID.")
        except Exception as e:
            print(f"Error syncing slash commands: {e}")
            traceback.print_exc()
    else:
        print("Cogs and slash commands not processed due to DB error.")

    print(f"Dynamic server prefix (default: {bot_cfg.DEFAULT_COMMAND_PREFIX}).")
    print(f"Game language is determined per-channel (configured via /config).")
    print(f"Guide: <prefix>help or /help.")

async def main():
    if not bot_cfg.BOT_TOKEN:
        print("CRITICAL ERROR: BOT_TOKEN missing.")
        return
    if not bot_cfg.DATABASE_URL:
        print("CRITICAL ERROR: DATABASE_URL missing.")
        return

    if not bot.kakasi: # Re-check here, mainly for the log message before start
        print(f"WARNING: PyKakasi is not properly initialized. Japanese features will be affected. Details: {bot.pykakasi_load_error}")

    try:
        async with bot:
            await bot.start(bot_cfg.BOT_TOKEN)
    except discord.errors.LoginFailure:
        print("CRITICAL ERROR: Invalid Bot Token.")
    except Exception as e:
        print(f"Undefined error running bot: {e}")
        traceback.print_exc()
    finally:
        if bot.http_session and not bot.http_session.closed:
            await bot.http_session.close()
            print("HTTP session closed.")
        if bot.db_pool:
            await bot.db_pool.close()
            print("DB pool closed.")
        print(f"Wiktionary VN cache: {len(bot.wiktionary_cache_vn)} items.")
        print(f"Wiktionary JP cache: {len(bot.wiktionary_cache_jp)} items.")
        print(f"Local VN dictionary: {len(bot.local_dictionary_vn)} words.")
        print(f"Local JP dictionary: {len(bot.local_dictionary_jp)} words.")
        print("Bot shutdown.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot shutting down due to KeyboardInterrupt...")