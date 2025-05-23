# Noitu/utils.py
import discord
from discord.ext import commands
from discord.ui import View 
from . import database
from . import config as bot_cfg 
from . import wiktionary_api 

def get_words_from_input(phrase_input: str) -> list[str]: # Dùng cho VN
    return [word.strip().lower() for word in phrase_input.strip().split() if word.strip()]

# Hàm này có thể hữu ích cho việc lấy ký tự cuối/đầu của Hiragana
def get_last_hiragana_char(hira_string: str) -> str | None:
    if not hira_string:
        return None
    # Xử lý trường hợp ký tự kéo dài âm (ー) hoặc dấu lặp lại (ゝゞ々)
    # Với Shiritori cơ bản, ta có thể lấy ký tự cuối cùng trực tiếp.
    # Một số luật Shiritori phức tạp hơn có thể bỏ qua ký tự kéo dài.
    # Ví dụ: コンピューター (konpyuutaa) -> kết thúc bằng 'ta', không phải 'a' sau khi bỏ 'ー'.
    # Kakasi thường trả về Hiragana không có 'ー' cho Romaji (computer -> こんぴゅーた)
    # Nếu từ kết thúc bằng ー, ký tự trước nó sẽ được dùng.
    # Ví dụ: サーバー -> さーばー. Kakasi: さあばあ. Lấy 'あ'.
    # Tuy nhiên, để đơn giản, lấy ký tự cuối.
    
    # Xử lý trường hợp kết thúc bằng ん (n) - không cần xử lý đặc biệt ở đây,
    # logic game sẽ quyết định.
    
    # Xử lý các ký tự nhỏ (ゃ, ゅ, ょ, っ) - chúng là một phần của âm tiết trước đó.
    # Ví dụ: きっぷ (kippu) -> ぷ. しゅっちょう (shucchou) -> う.
    # Việc lấy ký tự cuối của chuỗi Hiragana thường là đủ.
    return hira_string[-1]

def get_first_hiragana_char(hira_string: str) -> str | None:
    if not hira_string:
        return None
    return hira_string[0]


async def get_guild_game_settings(bot: commands.Bot, guild_id: int): # Nhận bot instance
    """Lấy cài đặt game của guild, fallback về mặc định."""
    if not bot.db_pool: # Nếu CSDL ko sẵn sàng
        return bot_cfg.DEFAULT_TIMEOUT_SECONDS, bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT, bot_cfg.DEFAULT_GAME_LANGUAGE

    guild_cfg_data = await database.get_guild_config(bot.db_pool, guild_id)
    if not guild_cfg_data: 
        return bot_cfg.DEFAULT_TIMEOUT_SECONDS, bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT, bot_cfg.DEFAULT_GAME_LANGUAGE

    return (
        guild_cfg_data.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS),
        guild_cfg_data.get("min_players_for_timeout", bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT),
        guild_cfg_data.get("game_language", bot_cfg.DEFAULT_GAME_LANGUAGE).upper() # Đảm bảo là chữ hoa
    )


async def _send_message_smart(target: discord.Interaction | commands.Context, content=None, embed=None, view=None, ephemeral=False, delete_after=None):
    """Gửi tin nhắn thông minh dựa trên context hoặc interaction."""
    original_message_response = None
    is_interaction_source = False

    # Xác định nguồn là interaction hay context
    if isinstance(target, discord.Interaction):
        is_interaction_source = True
    elif isinstance(target, commands.Context) and hasattr(target, 'interaction') and target.interaction:
        target = target.interaction # Ưu tiên interaction nếu có trong context
        is_interaction_source = True

    send_kwargs = {} # Các tham số để gửi
    if content is not None: send_kwargs['content'] = content
    if embed is not None: send_kwargs['embed'] = embed
    if view is not None and isinstance(view, View): send_kwargs['view'] = view


    if is_interaction_source:
        if not isinstance(target, discord.Interaction): # Kiểm tra lại type
            print(f"Lỗi _send_message_smart: target tưởng là interaction nhưng ko. Type: {type(target)}")
            if hasattr(target, 'channel') and isinstance(target.channel, discord.TextChannel):
                fallback_kwargs = send_kwargs.copy()
                if delete_after is not None and not ephemeral: 
                    fallback_kwargs['delete_after'] = delete_after
                # await target.channel.send(**fallback_kwargs) # Bỏ await vì có thể gây lỗi unawaited coroutine
                # Nên:
                try:
                    await target.channel.send(**fallback_kwargs)
                except Exception as e_send:
                    print(f"Lỗi fallback send trong _send_message_smart: {e_send}")

            return

        interaction_send_kwargs = send_kwargs.copy()
        interaction_send_kwargs['ephemeral'] = ephemeral 

        if target.response.is_done(): 
            interaction_send_kwargs['wait'] = True 
            original_message_response = await target.followup.send(**interaction_send_kwargs)
        else: 
            await target.response.send_message(**interaction_send_kwargs)
            original_message_response = await target.original_response() 

    elif isinstance(target, commands.Context): 
        context_send_kwargs = send_kwargs.copy()
        if delete_after is not None: context_send_kwargs['delete_after'] = delete_after
        original_message_response = await target.send(**context_send_kwargs)
    else:
        print(f"Lỗi _send_message_smart: Loại target ko xđ: {type(target)}")

    return original_message_response 


async def generate_help_embed(bot: commands.Bot, guild: discord.Guild, current_prefix: str): # Nhận bot instance
    """Tạo embed hướng dẫn."""
    if not guild: return None, "Lỗi: Không thể xác định server."

    timeout_s, min_p, game_lang = await get_guild_game_settings(bot, guild.id) # Dùng bot instance

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
            f"Từ kết thúc bằng 'ん' (n) thường là thua cuộc, nhưng ở đây bot sẽ cho phép và yêu cầu từ tiếp theo bắt đầu bằng 'ん' (nếu có)." # Điều chỉnh luật này nếu muốn
        )
        start_game_help = f"`/start [từ tiếng Nhật]` hoặc `{current_prefix}start [từ tiếng Nhật]`.\nNếu không nhập từ, bot tự chọn."

    embed.add_field(name="🎮 Bắt đầu game", value=f"{start_game_help}\nNút 'Bắt Đầu Nhanh' (bot chọn từ).", inline=False)
    embed.add_field(name="🛑 Dừng game", value=f"`/stop` hoặc `{current_prefix}stop`.", inline=False)
    embed.add_field(name="🏆 Bảng xếp hạng", value=f"`/bxh` hoặc `{current_prefix}bxh`.", inline=False)
    embed.add_field(name="⚙️ Cấu hình (Admin)",
                    value=(f"`/config set_prefix <kí_tự>`\n"
                           f"`/config set_timeout <giây>`\n"
                           f"`/config set_minplayers <số>`\n"
                           f"`/config set_language <vn|jp>`\n" # Thêm set_language
                           f"Hoặc `{current_prefix}config ...`."),
                    inline=False)
    embed.set_footer(text=f"Bot thả reaction: ✅ đúng, ❌ sai từ/đã dùng, ⚠️ sai lượt.")
    return embed, None


async def generate_leaderboard_embed(bot: commands.Bot, guild: discord.Guild): # Nhận bot instance
    """Tạo embed bảng xếp hạng. Trả về (embed, error_message_str)."""
    if not bot.db_pool:
        return None, "Lỗi: DB chưa sẵn sàng."
    if not guild:
        return None, "Lỗi: Không thể xác định server."

    async with bot.db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT name, wins, correct_moves, wrong_word_link, invalid_wiktionary, used_word_error, wrong_turn, current_win_streak, max_win_streak
            FROM leaderboard_stats WHERE guild_id = $1
            ORDER BY wins DESC, correct_moves DESC, max_win_streak DESC, current_win_streak DESC,
                     (wrong_word_link + invalid_wiktionary + used_word_error + wrong_turn) ASC, name ASC
            LIMIT 10;
            """, guild.id
        )

    guild_name = discord.utils.escape_markdown(guild.name)
    if not rows:
        return None, f"Chưa có ai trên BXH Nối Từ của server **{guild_name}**!"

    embed = discord.Embed(title=f"🏆 Bảng Xếp Hạng Nối Từ - {guild_name} 🏆", color=discord.Color.gold())
    desc = ""
    emojis = ["🥇", "🥈", "🥉"] # Icon rank
    for i, s_dict in enumerate(rows):
        s = dict(s_dict) 
        rank_display = emojis[i] if i < len(emojis) else f"**{i+1}.**"
        streak_info = f" (Hiện tại: {s['current_win_streak']})" if s['current_win_streak'] > 0 else ""
        total_errors = s.get("wrong_word_link",0) + s.get("invalid_wiktionary",0) + s.get("used_word_error",0)
        player_name = s['name']
        if len(player_name) > 25: player_name = player_name[:22] + "..." # Rút gọn tên dài

        desc += (f"{rank_display} **{discord.utils.escape_markdown(player_name)}**\n"
                 f"   🏅 Thắng: `{s['wins']}` | ✅ Lượt đúng: `{s['correct_moves']}`\n"
                 f"   🔥 Chuỗi max: `{s['max_win_streak']}`{streak_info}\n"
                 f"   ⚠️ Lỗi từ: `{total_errors}` | ⏰ Sai lượt: `{s['wrong_turn']}`\n\n")

    embed.description = desc.strip()
    embed.set_footer(text="BXH: Thắng > Lượt đúng > Chuỗi max > Chuỗi hiện tại > Ít lỗi > Tên.")
    return embed, None