# Noitu/utils.py
import discord
from discord.ext import commands
from discord.ui import View 
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

    embed_title = f"📜 Luật chơi Nối Từ ({'Tiếng Việt' if game_lang == 'VN' else 'Tiếng Nhật - しりとり'})"
    embed = discord.Embed(title=embed_title, color=discord.Color.teal())
    
    common_rules = (
        f"Sử dụng lệnh slash (gõ `/` để xem) hoặc lệnh prefix (hiện tại là `{current_prefix}`).\n"
        f"Sau khi có ít nhất **{min_p}** người chơi khác nhau tham gia, nếu sau **{timeout_s} giây** không ai nối được từ của bạn, bạn **thắng**!"
    )

    if game_lang == "VN":
        embed.description = (
            f"{common_rules}\n"
            f"**Luật chơi (Tiếng Việt):** Đưa ra cụm từ **đúng 2 chữ** tiếng Việt, có nghĩa và được Wiktionary công nhận. "
            f"Chữ đầu của cụm mới phải là chữ thứ hai của cụm trước."
        )
        start_game_help = f"`/start [chữ1 chữ2]` hoặc `{current_prefix}start [chữ1 chữ2]`.\nNếu không nhập từ, bot tự chọn."
    else: # JP
        embed.description = (
            f"{common_rules}\n"
            f"**Luật chơi (Tiếng Nhật - Shiritori):** Đưa ra một từ tiếng Nhật (Kanji, Hiragana, Katakana, Romaji). "
            f"Từ phải có nghĩa và được từ điển/Wiktionary công nhận.\n"
            f"Âm tiết (Hiragana) cuối của từ trước phải là âm tiết đầu của từ sau.\n"
            f"**QUAN TRỌNG:** Từ kết thúc bằng âm 'ん' (n) sẽ khiến người chơi đó **THUA CUỘC** ngay lập tức!"
        )
        start_game_help = f"`/start [từ tiếng Nhật]` hoặc `{current_prefix}start [từ tiếng Nhật]`.\nNếu không nhập từ, bot tự chọn."

    embed.add_field(name="🎮 Bắt đầu game", value=f"{start_game_help}\nNút 'Bắt Đầu Nhanh' (bot chọn từ).", inline=False)
    embed.add_field(name="🛑 Dừng game", value=f"`/stop` hoặc `{current_prefix}stop`.", inline=False)
    embed.add_field(name="🏆 Bảng xếp hạng", value=f"`/bxh` hoặc `{current_prefix}bxh` (hiển thị BXH cho ngôn ngữ của kênh này).", inline=False)
    embed.add_field(name="⚙️ Cấu hình (Admin)",
                    value=(f"`/config view` - Xem cấu hình kênh.\n"
                           f"`/config set_prefix <kí_tự>`\n"
                           f"`/config set_timeout <giây>`\n"
                           f"`/config set_minplayers <số>`\n"
                           f"`/config set_vn_channel <#kênh>` - Đặt kênh chơi Tiếng Việt.\n"
                           f"`/config set_jp_channel <#kênh>` - Đặt kênh chơi Tiếng Nhật.\n"
                           f"Hoặc `{current_prefix}config ...` (lệnh prefix có thể không hỗ trợ hết các cấu hình kênh)."),
                    inline=False)
    embed.set_footer(text=f"Bot thả reaction: ✅ đúng, ❌ sai từ/đã dùng, ⚠️ sai lượt, {bot_cfg.SHIRITORI_LOSS_REACTION} thua (luật 'ん').")
    return embed, None


async def generate_leaderboard_embed(bot: commands.Bot, guild: discord.Guild, game_language: str):
    """Tạo embed bảng xếp hạng. Trả về (embed, error_message_str)."""
    if not bot.db_pool:
        return None, "Lỗi: DB chưa sẵn sàng."
    if not guild:
        return None, "Lỗi: Không thể xác định server."
    if game_language not in ["VN", "JP"]:
        return None, "Lỗi: Ngôn ngữ không hợp lệ cho bảng xếp hạng."

    game_lang_name = "Tiếng Việt" if game_language == "VN" else "Tiếng Nhật (しりとり)"
    async with bot.db_pool.acquire() as conn:
        # Thêm cột lost_by_n_ending vào SELECT nếu cần hiển thị
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

    embed = discord.Embed(title=f"🏆 BXH Nối Từ ({game_lang_name}) - {guild_name_escaped} 🏆", color=discord.Color.gold())
    desc = ""
    emojis = ["🥇", "🥈", "🥉"] 
    for i, s_dict in enumerate(rows):
        s = dict(s_dict) 
        rank_display = emojis[i] if i < len(emojis) else f"**{i+1}.**"
        streak_info = f" (Hiện tại: {s['current_win_streak']})" if s['current_win_streak'] > 0 else ""
        
        total_errors = s.get("wrong_word_link",0) + s.get("invalid_wiktionary",0) + s.get("used_word_error",0)
        if game_language == "JP":
            total_errors += s.get("lost_by_n_ending", 0)
        
        player_name = s['name']
        if len(player_name) > 25: player_name = player_name[:22] + "..." 

        desc += (f"{rank_display} **{discord.utils.escape_markdown(player_name)}**\n"
                 f"   🏅 Thắng: `{s['wins']}` | ✅ Lượt đúng: `{s['correct_moves']}`\n"
                 f"   🔥 Chuỗi max: `{s['max_win_streak']}`{streak_info}\n"
                 f"   ⚠️ Lỗi (gộp): `{total_errors}` | ⏰ Sai lượt: `{s['wrong_turn']}`\n\n") # 'Lỗi (gộp)'

    embed.description = desc.strip()
    embed.set_footer(text=f"BXH ({game_lang_name}): Thắng > Lượt đúng > Chuỗi max > Chuỗi hiện tại > Ít lỗi > Tên.")
    return embed, None