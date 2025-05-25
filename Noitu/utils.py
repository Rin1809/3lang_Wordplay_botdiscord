# Noitu/utils.py
import discord
from discord.ext import commands
from discord.ui import View
import random

from . import database
from . import config as bot_cfg
from . import wiktionary_api # Giữ nếu wiktionary_api cần utils

# --- START: Romaji to Hiragana Conversion Logic ---
ROMAJI_TO_HIRAGANA_MAP = {
    'kya': 'きゃ', 'kyu': 'きゅ', 'kyo': 'きょ',
    'sha': 'しゃ', 'shu': 'しゅ', 'sho': 'しょ',
    'cha': 'ちゃ', 'chu': 'ちゅ', 'cho': 'ちょ',
    'nya': 'にゃ', 'nyu': 'にゅ', 'nyo': 'にょ',
    'hya': 'ひゃ', 'hyu': 'ひゅ', 'hyo': 'ひょ',
    'mya': 'みゃ', 'myu': 'みゅ', 'myo': 'みょ',
    'rya': 'りゃ', 'ryu': 'りゅ', 'ryo': 'りょ',
    'gya': 'ぎゃ', 'gyu': 'ぎゅ', 'gyo': 'ぎょ',
    'ja': 'じゃ', 'ju': 'じゅ', 'jo': 'じょ',
    'dha': 'ぢゃ', 'dhu': 'ぢゅ', 'dho': 'ぢょ',
    'bya': 'びゃ', 'byu': 'びゅ', 'byo': 'びょ',
    'pya': 'ぴゃ', 'pyu': 'ぴゅ', 'pyo': 'ぴょ',

    'tsu': 'つ', 'chi': 'ち', 'shi': 'し',
    'ka': 'か', 'ki': 'き', 'ku': 'く', 'ke': 'け', 'ko': 'こ',
    'sa': 'さ', 'su': 'す', 'se': 'せ', 'so': 'そ',
    'ta': 'た', 'te': 'て', 'to': 'と',
    'na': 'な', 'ni': 'に', 'nu': 'ぬ', 'ne': 'ね', 'no': 'の',
    'ha': 'は', 'hi': 'ひ', 'fu': 'ふ', 'he': 'へ', 'ho': 'ほ',
    'ma': 'ま', 'mi': 'み', 'mu': 'む', 'me': 'め', 'mo': 'も',
    'ya': 'や', 'yu': 'ゆ', 'yo': 'よ',
    'ra': 'ら', 'ri': 'り', 'ru': 'る', 're': 'れ', 'ro': 'ろ',
    'wa': 'わ', 'wi': 'ゐ', 'we': 'ゑ', 'wo': 'を',
    'ga': 'が', 'gi': 'ぎ', 'gu': 'ぐ', 'ge': 'げ', 'go': 'ご',
    'za': 'ざ', 'ji': 'じ', 'zu': 'ず', 'ze': 'ぜ', 'zo': 'ぞ',
    'da': 'だ', 'di': 'ぢ', 'du': 'づ', 'de': 'で', 'do': 'ど',
    'ba': 'ば', 'bi': 'び', 'bu': 'ぶ', 'be': 'べ', 'bo': 'ぼ',
    'pa': 'ぱ', 'pi': 'ぴ', 'pu': 'ぷ', 'pe': 'ぺ', 'po': 'ぽ',
    'a': 'あ', 'i': 'い', 'u': 'う', 'e': 'え', 'o': 'お',
    'vu': 'ゔ',
}

ROMAJI_KEYS_SORTED_FOR_CONVERSION = sorted(ROMAJI_TO_HIRAGANA_MAP.keys(), key=len, reverse=True)

def convert_romaji_to_hiragana_custom(romaji_text: str) -> str:
    """Cv Romaji -> Hiragana. Xử lý 'n' & sokuon."""
    if not romaji_text: return ""
    
    romaji_text = romaji_text.lower()
    hiragana_text = ""
    i = 0
    n_len = len(romaji_text)

    while i < n_len:
        # Sokuon (っ) - doubled consonants (ko 'n')
        if i + 1 < n_len and \
           romaji_text[i] == romaji_text[i+1] and \
           romaji_text[i] not in "aiueon'm" and \
           romaji_text[i:i+2] not in ROMAJI_TO_HIRAGANA_MAP:
            hiragana_text += "っ"
            i += 1 
            continue

        # 'n' (ん)
        if romaji_text[i] == 'n':
            if (i + 1 == n_len or \
                (romaji_text[i+1].isalpha() and \
                 romaji_text[i+1] not in "aiueoyāīūēō")):
                is_ny_combo = False
                if i + 2 < n_len:
                    if romaji_text[i:i+3] in ROMAJI_TO_HIRAGANA_MAP: #nya, nyu, nyo
                        is_ny_combo = True
                if not is_ny_combo:
                    hiragana_text += "ん"
                    i += 1
                    continue

        # Trường âm (vd: ou -> おう)
        if i + 1 < n_len:
            if romaji_text[i] == 'o' and romaji_text[i+1] == 'u':
                found_longer = False
                for key_len_check in range(3, 1, -1):
                    if i + key_len_check <= n_len:
                        segment_check = romaji_text[i : i + key_len_check]
                        if segment_check in ROMAJI_TO_HIRAGANA_MAP:
                            found_longer = True
                            break
                if not found_longer:
                    hiragana_text += ROMAJI_TO_HIRAGANA_MAP['o'] + ROMAJI_TO_HIRAGANA_MAP['u']
                    i += 2
                    continue
        
        # Khớp dài nhất
        matched_key = None
        for key in ROMAJI_KEYS_SORTED_FOR_CONVERSION:
            if romaji_text.startswith(key, i):
                matched_key = key
                break
        
        if matched_key:
            hiragana_text += ROMAJI_TO_HIRAGANA_MAP[matched_key]
            i += len(matched_key)
        else:
            # 'm' trc b/p/m -> 'ん'
            if romaji_text[i] == 'm' and i + 1 < n_len and romaji_text[i+1] in "bpm":
                hiragana_text += "ん"
                i += 1
            else:
                hiragana_text += romaji_text[i]
                i += 1
                
    return hiragana_text

def is_pure_katakana(text: str) -> bool:
    """Ktra str có thuần Katakana (và Chōonpu)."""
    if not text: return False
    for char_code in map(ord, text):
        # Katakana Unicode: 0x30A0-0x30FF, Katakana Phonetic Ext: 0x31F0-0x31FF, Chōonpu (ー): 0x30FC
        if not ((0x30A0 <= char_code <= 0x30FF) or \
                (0x31F0 <= char_code <= 0x31FF) or \
                char_code == 0x30FC):
            return False
    return True

def convert_katakana_to_hiragana_custom(katakana_text: str) -> str:
    """Cv Katakana -> Hiragana bằng mã offset."""
    if not katakana_text: return ""
    hiragana_text = ""
    for char_k in katakana_text:
        code_k = ord(char_k)
        # Khoảng Katakana thông dụng (ァ-ヺ, 0x30A1-0x30FA)
        if (0x30A1 <= code_k <= 0x30FA):
            hiragana_text += chr(code_k - 0x0060) # Offset sang Hiragana
        elif code_k == 0x30FD or code_k == 0x30FE: # Dấu lặp Katakana ヽ, ヾ
             hiragana_text += chr(code_k - 0x0060)
        elif char_k == 'ー': # Chōonpu (ー), giữ nguyên
            hiragana_text += 'ー'
        # Các ký tự đặc thù khác nếu cần
        elif code_k == 0x30F4: # ヴ (VU) -> ゔ (vu)
            hiragana_text += chr(code_k - 0x0060)
        elif code_k == 0x30F5: # ヵ (KA nhỏ) -> ゕ (ka nhỏ)
            hiragana_text += chr(code_k - 0x0060)
        elif code_k == 0x30F6: # ヶ (KE nhỏ) -> ゖ (ke nhỏ)
            hiragana_text += chr(code_k - 0x0060)
        else:
            hiragana_text += char_k # Giữ ký tự khác (punctuation, Kanji)
    return hiragana_text

def is_pure_hiragana(text: str) -> bool:
    """Ktra str có thuần Hiragana (và Chōonpu)."""
    if not text: return False
    for char_code in map(ord, text):
        # Hiragana Unicode 0x3040-0x309F, Chōonpu (ー, 0x30FC)
        if not ((0x3040 <= char_code <= 0x309F) or char_code == 0x30FC):
            return False
    return True
# --- END: Romaji to Hiragana Conversion Logic ---

# Hira nhỏ -> hira đủ (khi cuối ko phải Yōon)
HIRAGANA_SMALL_TO_FULL_MAP = {
    'ぁ': 'あ', 'ぃ': 'い', 'ぅ': 'う', 'ぇ': 'え', 'ぉ': 'お',
    'ゃ': 'や', 'ゅ': 'ゆ', 'ょ': 'よ', 'ゎ': 'わ',
    'っ': 'つ', 
}

YŌON_BASES = "きしちにひみりぎじぢびぴ"
YŌON_SMALLS = "ゃゅょ"

def get_words_from_input(phrase_input: str) -> list[str]: # Cho VN
    return [word.strip().lower() for word in phrase_input.strip().split() if word.strip()]

def get_shiritori_linking_mora_from_previous_word(hira_string: str) -> str | None: # Âm tiết nối
    if not hira_string: return None

    # Xử lý chōonpu (ー) cuối
    if hira_string.endswith('ー'):
        if len(hira_string) == 1: return None # 'ー' đơn lẻ
        part_before_choon = hira_string[:-1]
        if not part_before_choon: return None
        
        # Yōon cuối của phần trc 'ー'
        if len(part_before_choon) >= 2:
            second_last_char_of_part = part_before_choon[-2]
            last_char_of_part = part_before_choon[-1]
            if last_char_of_part in YŌON_SMALLS and second_last_char_of_part in YŌON_BASES:
                return second_last_char_of_part + last_char_of_part 
        
        # Ko Yōon, lấy ký tự cuối của phần trc 'ー'
        last_char_final_of_part = part_before_choon[-1]
        return HIRAGANA_SMALL_TO_FULL_MAP.get(last_char_final_of_part, last_char_final_of_part)

    # Logic gốc cho từ ko kết thúc bằng 'ー'
    if len(hira_string) >= 2:
        second_last_char = hira_string[-2]
        last_char = hira_string[-1]
        if last_char in YŌON_SMALLS and second_last_char in YŌON_BASES:
            return second_last_char + last_char # Vd: "しゃ" từ "いしゃ"
    
    last_char_final = hira_string[-1]
    return HIRAGANA_SMALL_TO_FULL_MAP.get(last_char_final, last_char_final)

def get_first_mora_of_current_word(hira_string: str) -> str | None: # Âm tiết đầu
    if not hira_string: return None

    if len(hira_string) >= 2:
        first_char = hira_string[0]
        second_char = hira_string[1]
        if second_char in YŌON_SMALLS and first_char in YŌON_BASES:
            return first_char + second_char # Vd: "しゃ" từ "しゃかい"
            
    return hira_string[0]


async def get_channel_game_settings(bot: commands.Bot, guild_id: int, channel_id: int):
    game_lang_for_channel = None
    guild_cfg_data = None

    if bot.db_pool:
        guild_cfg_data = await database.get_guild_config(bot.db_pool, guild_id)
        if guild_cfg_data:
            if guild_cfg_data.get("jp_channel_id") == channel_id:
                game_lang_for_channel = "JP"
            elif guild_cfg_data.get("vn_channel_id") == channel_id:
                game_lang_for_channel = "VN"

    timeout = bot_cfg.DEFAULT_TIMEOUT_SECONDS
    min_players = bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT

    if guild_cfg_data:
        timeout = guild_cfg_data.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS)
        min_players = guild_cfg_data.get("min_players_for_timeout", bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT)

    return timeout, min_players, game_lang_for_channel

async def _send_message_smart(target: discord.Interaction | commands.Context, content=None, embed=None, view=None, ephemeral=False, delete_after=None):
    original_message_response = None
    is_interaction_source = False

    if isinstance(target, discord.Interaction):
        is_interaction_source = True
    elif isinstance(target, commands.Context) and hasattr(target, 'interaction') and target.interaction:
        target = target.interaction
        is_interaction_source = True

    send_kwargs = {}
    if content is not None: send_kwargs['content'] = content
    if embed is not None: send_kwargs['embed'] = embed
    if view is not None and isinstance(view, View): send_kwargs['view'] = view

    if is_interaction_source:
        if not isinstance(target, discord.Interaction): # Lỗi type
            print(f"ERR _send_smart: target ko phải inter. Type: {type(target)}")
            if hasattr(target, 'channel') and isinstance(target.channel, discord.TextChannel):
                fallback_kwargs = send_kwargs.copy()
                if delete_after is not None and not ephemeral:
                    fallback_kwargs['delete_after'] = delete_after
                try: return await target.channel.send(**fallback_kwargs)
                except Exception as e_send: print(f"ERR fallback send: {e_send}")
            return None

        interaction_send_kwargs = send_kwargs.copy()
        interaction_send_kwargs['ephemeral'] = ephemeral

        try:
            if target.response.is_done():
                interaction_send_kwargs['wait'] = True
                original_message_response = await target.followup.send(**interaction_send_kwargs)
            else:
                await target.response.send_message(**interaction_send_kwargs)
                original_message_response = await target.original_response()
        except discord.HTTPException as e:
            print(f"ERR HTTP inter send/followup: {e}")
            if hasattr(target, 'channel') and isinstance(target.channel, discord.TextChannel) and not ephemeral:
                try:
                    print("Fallback send to channel.")
                    fallback_kwargs = send_kwargs.copy()
                    if delete_after is not None: fallback_kwargs['delete_after'] = delete_after
                    return await target.channel.send(**fallback_kwargs)
                except Exception as e_fallback: print(f"ERR fallback send channel: {e_fallback}")
            return None

    elif isinstance(target, commands.Context):
        context_send_kwargs = send_kwargs.copy()
        if delete_after is not None: context_send_kwargs['delete_after'] = delete_after
        try: original_message_response = await target.send(**context_send_kwargs)
        except discord.HTTPException as e:
            print(f"ERR HTTP ctx send: {e}")
            return None
    else:
        print(f"ERR _send_smart: target type ko xđ: {type(target)}")
        return None

    return original_message_response


async def generate_help_embed(bot: commands.Bot, guild: discord.Guild, current_prefix: str, channel_id: int):
    if not guild: return None, "Lỗi: Ko xđ server."

    timeout_s, min_p, game_lang = await get_channel_game_settings(bot, guild.id, channel_id)

    if game_lang is None:
        return None, (
            f"Kênh này chưa config Nối Từ. "
            f"Admin dùng `/config set_vn_channel` or `/config set_jp_channel`."
        )

    embed_title = f"{bot_cfg.HELP_ICON} HD chơi Nối Từ ({bot_cfg.GAME_VN_ICON} VN / {bot_cfg.GAME_JP_ICON} JP)"
    embed_color = bot_cfg.EMBED_COLOR_HELP
    embed = discord.Embed(title=embed_title, color=embed_color)
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    common_rules_intro = (
        f"Chào mừng! Đây là lệnh & luật chơi.\n"
        f"Dùng lệnh slash (gõ `/`) hoặc prefix (hiện tại: `{current_prefix}`).\n"
    )
    embed.description = common_rules_intro
    game_rules_title = f"{bot_cfg.RULES_ICON} Luật chơi kênh này: "

    if game_lang == "VN":
        game_rules_title += f"{bot_cfg.GAME_VN_ICON} **Tiếng Việt**"
        game_rules_details = (
            f"• Cụm từ **2 chữ** TV, có nghĩa, được từ điển/Wiktionary nhận.\n"
            f"• Chữ đầu cụm mới = chữ hai cụm trc (vd: *học **sinh*** → ***sinh** viên*).\n"
            f"• Sau khi có >= **{min_p}** người chơi, nếu sau **{timeout_s}s** ko ai nối, bạn **thắng**!"
        )
        start_game_help_specific = f"`/start [chữ1 chữ2]` or `{current_prefix}start [chữ1 chữ2]`."
    else: # JP
        game_rules_title += f"{bot_cfg.GAME_JP_ICON} **Tiếng Nhật (Shiritori - しりとり)**"
        game_rules_details = (
            f"• Từ TN (Kanji, Hira, Kata, Roma). Bot cố cv Roma -> Hira.\n"
            f"• Từ có nghĩa, được từ điển/Wiktionary nhận.\n"
            f"• Âm cuối từ trc = âm đầu từ sau (theo Hira).\n"
            f"  - Vd: *さく**ら*** (sakura) → ***ら**いおん* (raion).\n"
            f"  - Âm ghép (Yōon) *い**しゃ*** (isha) → tiếp theo bắt đầu **しゃ** (sha), vd: ***しゃ**かい* (shakai).\n"
            f"  - Từ cuối bằng trường âm (ー), vd *ラーメン* (rāmen) → nối bằng âm trc dấu (メ, me). Vd: ラーメン → めがみ (megami).\n"
            f"• **LƯU Ý:** Từ cuối bằng 'ん' (n) (dạng Hira) → người đó **THUA**!\n"
            f"• Sau khi có >= **{min_p}** người chơi, nếu sau **{timeout_s}s** ko ai nối, bạn **thắng**!"
        )
        start_game_help_specific = f"`/start [từ TN]` or `{current_prefix}start [từ TN]`."

    embed.add_field(name=game_rules_title, value=game_rules_details, inline=False)
    embed.add_field(name=f"{bot_cfg.GAME_START_ICON} Bắt đầu game",
                    value=f"{start_game_help_specific}\nBỏ trống từ -> bot chọn.\nNút 'Bắt Đầu Nhanh' -> bot chọn.",
                    inline=False)
    embed.add_field(name=f"{bot_cfg.STOP_ICON} Dừng game", value=f"`/stop` or `{current_prefix}stop`.", inline=False)
    embed.add_field(name=f"{bot_cfg.LEADERBOARD_ICON} BXH", value=f"`/bxh` or `{current_prefix}bxh` (BXH cho ngôn ngữ kênh này).", inline=False)

    admin_cmds_value = (
        f"`/config view`\n"
        f"`/config set_prefix <kí_tự>`\n"
        f"`/config set_timeout <giây>`\n"
        f"`/config set_minplayers <số>`\n"
        f"`/config set_vn_channel <#kênh>`\n"
        f"`/config set_jp_channel <#kênh>`\n"
        f"(Hoặc `{current_prefix}config ...` cho vài cài đặt)"
    )
    embed.add_field(name=f"{bot_cfg.CONFIG_ICON} Cấu hình (Admin)", value=admin_cmds_value, inline=False)
    reactions_guide = (
        f"{bot_cfg.CORRECT_REACTION} Hợp lệ | "
        f"{bot_cfg.ERROR_REACTION} Ko hợp lệ/đã dùng | "
        f"{bot_cfg.WRONG_TURN_REACTION} Sai lượt\n"
        f"{bot_cfg.SHIRITORI_LOSS_REACTION} Thua 'ん' (JP)"
    )
    embed.add_field(name="💡 Reactions Bot", value=reactions_guide, inline=False)
    embed.set_footer(text=f"Bot Nối Từ | {guild.name}")
    return embed, None


async def generate_leaderboard_embed(bot: commands.Bot, guild: discord.Guild, game_language: str):
    if not bot.db_pool: return None, "Lỗi: DB chưa sẵn sàng."
    if not guild: return None, "Lỗi: Ko xđ server."
    if game_language not in ["VN", "JP"]: return None, "Lỗi: Ngôn ngữ BXH ko hợp lệ."

    game_lang_name = f"{bot_cfg.GAME_VN_ICON} TV" if game_language == "VN" else f"{bot_cfg.GAME_JP_ICON} TN (しりとり)"
    async with bot.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT name, wins, correct_moves, wrong_word_link, invalid_wiktionary, used_word_error, wrong_turn,
                   lost_by_n_ending, current_win_streak, max_win_streak
            FROM leaderboard_stats
            WHERE guild_id = $1 AND game_language = $2
            ORDER BY wins DESC, correct_moves DESC, max_win_streak DESC, current_win_streak DESC,
                     (wrong_word_link + invalid_wiktionary + used_word_error + wrong_turn + lost_by_n_ending) ASC,
                     name ASC
            LIMIT 10;
            """, guild.id, game_language
        )

    guild_name_escaped = discord.utils.escape_markdown(guild.name)
    if not rows:
        return None, f"Chưa có ai trên BXH Nối Từ ({game_lang_name}) của **{guild_name_escaped}**!"

    embed = discord.Embed(title=f"{bot_cfg.LEADERBOARD_ICON} BXH Nối Từ ({game_lang_name})", color=bot_cfg.EMBED_COLOR_LEADERBOARD)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    desc_parts = []
    emojis = ["🥇", "🥈", "🥉"]
    for i, s_dict in enumerate(rows):
        s = dict(s_dict) # s là 1 record
        rank_display = emojis[i] if i < len(emojis) else f"**{i+1}.**"
        player_name_escaped = discord.utils.escape_markdown(s['name'])
        if len(player_name_escaped) > 25: player_name_escaped = player_name_escaped[:22] + "..."
        streak_info = f" (Hiện tại: **{s['current_win_streak']}** 🔥)" if s['current_win_streak'] > 0 else ""
        total_errors = s.get("wrong_word_link",0) + s.get("invalid_wiktionary",0) + s.get("used_word_error",0)
        if game_language == "JP": total_errors += s.get("lost_by_n_ending", 0)

        player_entry = (
            f"{rank_display} **{player_name_escaped}**\n"
            f"   🏅 Thắng: `{s['wins']}` | ✅ Lượt đúng: `{s['correct_moves']}`\n"
            f"   🏆 Chuỗi max: `{s['max_win_streak']}`{streak_info}\n"
            f"   ⚠️ Lỗi: `{total_errors}` | ⏰ Sai lượt: `{s['wrong_turn']}`"
        )
        desc_parts.append(player_entry)

    embed.description = "\n\n".join(desc_parts)
    embed.set_footer(text=f"Server: {guild.name} | Sắp xếp: Thắng > Lượt > Chuỗi max > ...")
    return embed, None

async def send_random_guild_emoji_if_any(channel: discord.TextChannel, guild: discord.Guild):
    if guild and guild.emojis:
        available_emojis = list(guild.emojis)
        if available_emojis:
            try:
                random_emoji = random.choice(available_emojis)
                await channel.send(str(random_emoji))
            except discord.HTTPException as e: print(f"ERR gửi rand emoji {channel.id} guild {guild.id}: {e}")
            except Exception as e_rand: print(f"ERR rand emoji ko xđ: {e_rand}")

def is_romaji(text: str) -> bool:
    """Ktra str có chủ yếu là ASCII letters (gợi ý Romaji)."""
    if not text: return False
    alpha_count = 0
    for char in text:
        if 'a' <= char.lower() <= 'z':
            alpha_count += 1
        elif char in "'-": # Phổ biến trong Romaji
            alpha_count += 0.5 # Tính 1 phần
    return alpha_count / len(text) > 0.7 # Hơn 70% là ký tự alphabet/liên quan romaji