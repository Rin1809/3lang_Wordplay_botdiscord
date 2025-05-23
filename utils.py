# Noitu/utils.py
import discord
from discord.ext import commands
from discord.ui import View 
import random

from . import database
from . import config as bot_cfg 
from . import wiktionary_api 

def get_words_from_input(phrase_input: str) -> list[str]: # Dùng cho VN
    return [word.strip().lower() for word in phrase_input.strip().split() if word.strip()]

def get_last_hiragana_char(hira_string: str) -> str | None:
    if not hira_string:
        return None
    return hira_string[-1]

def get_first_hiragana_char(hira_string: str) -> str | None:
    if not hira_string:
        return None
    return hira_string[0]

async def get_channel_game_settings(bot: commands.Bot, guild_id: int, channel_id: int): # Nhận bot instance và channel_id
    """Lấy cài đặt game của guild và xác định ngôn ngữ cho kênh cụ thể."""
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

    return timeout, min_players, game_lang_for_channel # Trả về game_lang_for_channel (có thể là None)


async def _send_message_smart(target: discord.Interaction | commands.Context, content=None, embed=None, view=None, ephemeral=False, delete_after=None):
    """Gửi tin nhắn thông minh dựa trên context hoặc interaction."""
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
        if not isinstance(target, discord.Interaction): 
            print(f"Lỗi _send_message_smart: target tưởng là interaction nhưng ko. Type: {type(target)}")
            if hasattr(target, 'channel') and isinstance(target.channel, discord.TextChannel):
                fallback_kwargs = send_kwargs.copy()
                if delete_after is not None and not ephemeral: 
                    fallback_kwargs['delete_after'] = delete_after
                try:
                    return await target.channel.send(**fallback_kwargs)
                except Exception as e_send:
                    print(f"Lỗi fallback send trong _send_message_smart: {e_send}")
            return None # Quan trọng: trả về None nếu có lỗi

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
            print(f"Lỗi HTTP khi gửi/followup tin nhắn interaction: {e}")
            # Fallback to channel send if possible and not ephemeral
            if hasattr(target, 'channel') and isinstance(target.channel, discord.TextChannel) and not ephemeral:
                try:
                    print("Thực hiện fallback send to channel.")
                    fallback_kwargs = send_kwargs.copy()
                    if delete_after is not None: fallback_kwargs['delete_after'] = delete_after
                    return await target.channel.send(**fallback_kwargs)
                except Exception as e_fallback:
                    print(f"Lỗi fallback send to channel: {e_fallback}")
            return None


    elif isinstance(target, commands.Context): 
        context_send_kwargs = send_kwargs.copy()
        if delete_after is not None: context_send_kwargs['delete_after'] = delete_after
        try:
            original_message_response = await target.send(**context_send_kwargs)
        except discord.HTTPException as e:
            print(f"Lỗi HTTP khi gửi tin nhắn context: {e}")
            return None
    else:
        print(f"Lỗi _send_message_smart: Loại target ko xđ: {type(target)}")
        return None

    return original_message_response 


async def generate_help_embed(bot: commands.Bot, guild: discord.Guild, current_prefix: str, channel_id: int):
    """Tạo embed hướng dẫn, nhận channel_id để xác định ngôn ngữ."""
    if not guild: return None, "Lỗi: Không thể xác định server."

    timeout_s, min_p, game_lang = await get_channel_game_settings(bot, guild.id, channel_id)

    if game_lang is None:
        return None, (
            f"Kênh này chưa được cấu hình để chơi Nối Từ. "
            f"Admin có thể dùng lệnh `/config set_vn_channel` hoặc `/config set_jp_channel`."
        )

    embed_title = f"{bot_cfg.HELP_ICON} Hướng dẫn chơi Nối Từ ({bot_cfg.GAME_VN_ICON} Tiếng Việt / {bot_cfg.GAME_JP_ICON} Tiếng Nhật)"
    embed_color = bot_cfg.EMBED_COLOR_HELP
    
    embed = discord.Embed(title=embed_title, color=embed_color)
    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    common_rules_intro = (
        f"Chào mừng bạn đến với Nối Từ! Dưới đây là các lệnh và luật chơi cơ bản.\n"
        f"Sử dụng lệnh slash (gõ `/` để xem) hoặc lệnh prefix (hiện tại của server này là `{current_prefix}`).\n"
    )
    embed.description = common_rules_intro

    game_rules_title = f"{bot_cfg.RULES_ICON} Luật chơi cho kênh này: "
    if game_lang == "VN":
        game_rules_title += f"{bot_cfg.GAME_VN_ICON} **Tiếng Việt**"
        game_rules_details = (
            f"• Đưa ra cụm từ có **đúng 2 chữ** tiếng Việt, có nghĩa và được từ điển/Wiktionary công nhận.\n"
            f"• Chữ đầu của cụm mới phải là chữ thứ hai của cụm trước (ví dụ: *học **sinh*** → ***sinh** viên*).\n"
            f"• Sau khi có ít nhất **{min_p}** người chơi khác nhau tham gia, nếu sau **{timeout_s} giây** không ai nối được từ của bạn, bạn **thắng**!"
        )
        start_game_help_specific = f"`/start [chữ1 chữ2]` hoặc `{current_prefix}start [chữ1 chữ2]`."
    else: # JP
        game_rules_title += f"{bot_cfg.GAME_JP_ICON} **Tiếng Nhật (Shiritori - しりとり)**"
        game_rules_details = (
            f"• Đưa ra một từ tiếng Nhật (Kanji, Hiragana, Katakana, Romaji).\n"
            f"• Từ phải có nghĩa và được từ điển/Wiktionary công nhận.\n"
            f"• Âm tiết (Hiragana) cuối của từ trước phải là âm tiết đầu của từ sau (ví dụ: *さく**ら*** → ***ら**いおん*).\n"
            f"• **QUAN TRỌNG:** Từ kết thúc bằng âm 'ん' (n) sẽ khiến người chơi đó **THUA CUỘC** ngay lập tức!\n"
            f"• Sau khi có ít nhất **{min_p}** người chơi khác nhau tham gia, nếu sau **{timeout_s} giây** không ai nối được từ của bạn, bạn **thắng**!"
        )
        start_game_help_specific = f"`/start [từ tiếng Nhật]` hoặc `{current_prefix}start [từ tiếng Nhật]`."
    
    embed.add_field(name=game_rules_title, value=game_rules_details, inline=False)

    embed.add_field(name=f"{bot_cfg.GAME_START_ICON} Bắt đầu game", 
                    value=f"{start_game_help_specific}\nNếu không nhập từ, bot sẽ tự chọn từ ngẫu nhiên.\nNút 'Bắt Đầu Nhanh' bên dưới cũng sẽ để bot chọn từ.", 
                    inline=False)
    embed.add_field(name=f"{bot_cfg.STOP_ICON} Dừng game", value=f"`/stop` hoặc `{current_prefix}stop`.", inline=False)
    embed.add_field(name=f"{bot_cfg.LEADERBOARD_ICON} Bảng xếp hạng", value=f"`/bxh` hoặc `{current_prefix}bxh` (hiển thị BXH cho ngôn ngữ của kênh này).", inline=False)
    
    admin_cmds_value = (
        f"`/config view` - Xem cấu hình kênh.\n"
        f"`/config set_prefix <kí_tự>`\n"
        f"`/config set_timeout <giây>`\n"
        f"`/config set_minplayers <số>`\n"
        f"`/config set_vn_channel <#kênh>`\n"
        f"`/config set_jp_channel <#kênh>`\n"
        f"(Hoặc dùng `{current_prefix}config ...` cho một số cài đặt cơ bản)"
    )
    embed.add_field(name=f"{bot_cfg.CONFIG_ICON} Cấu hình (Admin)", value=admin_cmds_value, inline=False)
    
    reactions_guide = (
        f"{bot_cfg.CORRECT_REACTION} Từ hợp lệ | "
        f"{bot_cfg.ERROR_REACTION} Từ không hợp lệ / đã dùng | "
        f"{bot_cfg.WRONG_TURN_REACTION} Sai lượt chơi\n"
        f"{bot_cfg.SHIRITORI_LOSS_REACTION} Thua do luật 'ん' (Tiếng Nhật)"
    )
    embed.add_field(name="💡 Reactions của Bot", value=reactions_guide, inline=False)
    embed.set_footer(text=f"Bot Nối Từ | {guild.name}")
    return embed, None


async def generate_leaderboard_embed(bot: commands.Bot, guild: discord.Guild, game_language: str):
    """Tạo embed bảng xếp hạng. Trả về (embed, error_message_str)."""
    if not bot.db_pool:
        return None, "Lỗi: DB chưa sẵn sàng."
    if not guild:
        return None, "Lỗi: Không thể xác định server."
    if game_language not in ["VN", "JP"]:
        return None, "Lỗi: Ngôn ngữ không hợp lệ cho bảng xếp hạng."

    game_lang_name = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if game_language == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật (しりとり)"
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
        return None, f"Chưa có ai trên BXH Nối Từ ({game_lang_name}) của server **{guild_name_escaped}**!"

    embed = discord.Embed(title=f"{bot_cfg.LEADERBOARD_ICON} BXH Nối Từ ({game_lang_name})", color=bot_cfg.EMBED_COLOR_LEADERBOARD)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    
    desc_parts = []
    emojis = ["🥇", "🥈", "🥉"] 
    for i, s_dict in enumerate(rows):
        s = dict(s_dict) 
        rank_display = emojis[i] if i < len(emojis) else f"**{i+1}.**"
        
        player_name_escaped = discord.utils.escape_markdown(s['name'])
        if len(player_name_escaped) > 25: player_name_escaped = player_name_escaped[:22] + "..." 

        streak_info = f" (Hiện tại: **{s['current_win_streak']}** 🔥)" if s['current_win_streak'] > 0 else ""
        
        total_errors = s.get("wrong_word_link",0) + s.get("invalid_wiktionary",0) + s.get("used_word_error",0)
        if game_language == "JP":
            total_errors += s.get("lost_by_n_ending", 0)
        
        player_entry = (
            f"{rank_display} **{player_name_escaped}**\n"
            f"   🏅 Thắng: `{s['wins']}` | ✅ Lượt đúng: `{s['correct_moves']}`\n"
            f"   🏆 Chuỗi thắng max: `{s['max_win_streak']}`{streak_info}\n"
            f"   ⚠️ Lỗi (tổng): `{total_errors}` | ⏰ Sai lượt: `{s['wrong_turn']}`"
        )
        desc_parts.append(player_entry)

    embed.description = "\n\n".join(desc_parts) # Thêm khoảng cách giữa các entry
    embed.set_footer(text=f"Server: {guild.name} | Sắp xếp: Thắng > Lượt đúng > Chuỗi max > ...")
    return embed, None

async def send_random_guild_emoji_if_any(channel: discord.TextChannel, guild: discord.Guild):
    """Gửi một emoji ngẫu nhiên từ server vào kênh (nếu có)."""
    if guild and guild.emojis:
        available_emojis = list(guild.emojis) # Lấy tất cả emojis
        if available_emojis:
            try:
                random_emoji = random.choice(available_emojis)
                await channel.send(str(random_emoji))
            except discord.HTTPException as e:
                print(f"Lỗi gửi random emoji vào kênh {channel.id} của guild {guild.id}: {e}")
            except Exception as e_rand:
                print(f"Lỗi không xác định khi chọn/gửi random emoji: {e_rand}")