# Noitu/game/logic.py
import discord
from discord.ext import commands
import random
import asyncio
import traceback

from .. import database
from .. import wiktionary_api
from .. import utils
from .. import config as bot_cfg 
from .views import PostGameView # Import PostGameView để dùng ở cuối game


async def check_game_timeout(bot: commands.Bot, channel_id: int, guild_id: int, expected_last_player_id: int, expected_phrase_normalized: str):
    if not bot.db_pool: return # DB phải sẵn sàng

    guild_cfg = await database.get_guild_config(bot.db_pool, guild_id) # Lấy config guild
    timeout_seconds_for_guild = guild_cfg.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS)
    command_prefix_for_guild = guild_cfg.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX)

    countdown_message: discord.Message = None
    message_channel = bot.get_channel(channel_id)
    if not message_channel or not isinstance(message_channel, discord.TextChannel):
        if channel_id in bot.active_games: del bot.active_games[channel_id] # Dọn dẹp nếu kênh ko hợp lệ
        return

    initial_countdown_text_base = "" # Text cố định của msg đếm ngược
    if expected_last_player_id == bot.user.id:
        initial_countdown_text_base = f"⏳ Bot đã ra từ \"**{expected_phrase_normalized.title()}**\". "
    else:
        try:
            winner_user_to_be = await bot.fetch_user(expected_last_player_id)
            initial_countdown_text_base = f"⏳ {winner_user_to_be.mention} đã ra từ \"**{expected_phrase_normalized.title()}**\". "
        except discord.NotFound:
            initial_countdown_text_base = f"⏳ Người chơi ID {expected_last_player_id} đã ra từ \"**{expected_phrase_normalized.title()}**\". "
        except discord.HTTPException: # Lỗi API Discord
            initial_countdown_text_base = f"⏳ Một người chơi đã ra từ \"**{expected_phrase_normalized.title()}**\". "
    
    try:
        countdown_message = await message_channel.send(f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {timeout_seconds_for_guild} giây.")
    except discord.HTTPException as e:
        print(f"Lỗi gửi msg đếm ngược: {e}")
        countdown_message = None

    time_slept = 0 # Tổng thời gian đã ngủ
    edit_interval = 1 # Edit msg mỗi 1s

    try:
        while time_slept < timeout_seconds_for_guild:
            await asyncio.sleep(min(edit_interval, timeout_seconds_for_guild - time_slept))
            time_slept += edit_interval

            # Kiểm tra game có còn hoạt động và đúng trạng thái ko
            if channel_id not in bot.active_games or not bot.active_games[channel_id]["active"]:
                if countdown_message: # Dọn msg nếu game dừng sớm
                    try: await countdown_message.delete()
                    except (discord.NotFound, discord.HTTPException): pass
                return

            game = bot.active_games[channel_id]
            if not (game.get("last_player_id") == expected_last_player_id and \
                    game.get("current_phrase_str") == expected_phrase_normalized):
                if countdown_message: # Dọn msg nếu có người chơi mới
                    try: await countdown_message.delete()
                    except (discord.NotFound, discord.HTTPException): pass
                return
            
            if countdown_message: # Cập nhật msg đếm ngược
                remaining_time = max(0, timeout_seconds_for_guild - time_slept)
                new_text = f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {remaining_time} giây."
                if remaining_time > 0 :
                    try: await countdown_message.edit(content=new_text)
                    except (discord.NotFound, discord.HTTPException): countdown_message = None 

            if time_slept >= timeout_seconds_for_guild: break # Timeout

        # --- HẾT GIỜ ---
        if countdown_message: # Xóa msg đếm ngược cuối cùng
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass

        # Kiểm tra lần cuối trước khi công bố thắng
        if channel_id in bot.active_games and bot.active_games[channel_id]["active"]:
            game = bot.active_games[channel_id]
            if game.get("last_player_id") == expected_last_player_id and \
               game.get("current_phrase_str") == expected_phrase_normalized:

                winner_id = game["last_player_id"]
                winning_phrase_display = " ".join(w.capitalize() for w in expected_phrase_normalized.split()) # Từ thắng cuộc
                
                win_embed = discord.Embed(color=discord.Color.gold())
                original_starter_for_view = winner_id # ID người chơi để nút "Chơi Lại" dùng

                if winner_id == bot.user.id: # Nếu bot là người ra từ cuối
                    win_embed.title = "⏳ Hết Giờ! ⏳"
                    win_embed.description = (
                        f"Đã hết {timeout_seconds_for_guild} giây! Không ai nối được từ \"**{winning_phrase_display}**\" của Bot.\n"
                        f"Game kết thúc không có người thắng."
                    )
                    participants_list = list(game.get("participants_since_start", []))
                    # Nút "Chơi Lại" sẽ do người đầu tiên trong list người chơi bắt đầu (nếu có)
                    original_starter_for_view = participants_list[0] if participants_list else bot.user.id
                else: # Người chơi thắng
                    winner_name_display = f"User ID {winner_id}" # Tên hiển thị fallback
                    winner_avatar_url = None
                    try:
                        winner_user = await bot.fetch_user(winner_id)
                        winner_name_display = winner_user.name # Dùng .name cho DB
                        winner_avatar_url = winner_user.display_avatar.url
                        # Cập nhật stat thắng cho người chơi
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display)
                        
                        # Reset win streak cho những người tham gia khác
                        for pid in game.get("participants_since_start", set()):
                            if pid != winner_id and pid != bot.user.id:
                                await database.reset_win_streak_for_user(bot.db_pool, pid, guild_id)

                        win_embed.title = f"🎉 Chúc Mừng {discord.utils.escape_markdown(winner_name_display)}! 🎉"
                        win_embed.description = (
                            f"{winner_user.mention} đã chiến thắng!\n"
                            f"Không ai nối tiếp được từ \"**{winning_phrase_display}**\" của bạn trong {timeout_seconds_for_guild} giây."
                        )
                        if winner_avatar_url: win_embed.set_thumbnail(url=winner_avatar_url)

                        user_stats = await database.get_user_stats_entry(bot.db_pool, winner_id, guild_id, winner_name_display)
                        if user_stats: # Thêm thông tin stat vào embed
                             win_embed.add_field(name="Thành Tích", value=f"Thắng: {user_stats['wins']} | Chuỗi: {user_stats['current_win_streak']} (Max: {user_stats['max_win_streak']})", inline=False)
                        original_starter_for_view = winner_id 
                    except discord.NotFound: # Ko tìm thấy user
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}")
                        win_embed.title = "🎉 Người Chơi Thắng Cuộc! 🎉"
                        win_embed.description = f"Người chơi ID {winner_id} đã thắng với từ \"**{winning_phrase_display}**\"! (Không thể lấy thông tin chi tiết)."
                    except discord.HTTPException: # Lỗi API Discord
                         await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)")
                         win_embed.title = "🎉 Một Người Chơi Thắng! 🎉"
                         win_embed.description = f"Một người chơi đã thắng với từ \"**{winning_phrase_display}**\"! (Lỗi khi lấy thông tin người chơi)."
                
                view = PostGameView(
                    channel=message_channel, 
                    original_starter_id=original_starter_for_view, 
                    command_prefix_for_guild=command_prefix_for_guild,
                    bot_instance=bot, # Truyền bot instance
                    internal_start_game_callable=internal_start_game # Truyền hàm để "Chơi Lại"
                )
                msg_with_view = await message_channel.send(embed=win_embed, view=view)
                view.message_to_edit = msg_with_view # Gán message để view có thể edit (disable nút)

                # Dọn dẹp game state nếu timeout này kết thúc game
                if channel_id in bot.active_games and \
                   bot.active_games[channel_id].get("last_player_id") == expected_last_player_id and \
                   bot.active_games[channel_id].get("current_phrase_str") == expected_phrase_normalized:
                    del bot.active_games[channel_id]
    
    except asyncio.CancelledError: # Task bị hủy (do có người chơi mới hoặc game dừng)
        if countdown_message: 
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass
    except Exception as e:
        print(f"Lỗi nghiêm trọng trong check_game_timeout cho kênh {channel_id} (từ: {expected_phrase_normalized}): {e}")
        traceback.print_exc()
        if countdown_message: 
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass


async def internal_start_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member, 
                              guild_id: int, start_phrase_input: str = None, interaction: discord.Interaction = None):
    # Hàm gửi response nội bộ
    async def send_response(msg_content: str, ephemeral_flag: bool = False):
        if interaction:
            if interaction.response.is_done(): # Đã defer/reply
                await interaction.followup.send(msg_content, ephemeral=ephemeral_flag)
            else: 
                await interaction.response.send_message(msg_content, ephemeral=ephemeral_flag)
        else: # Context lệnh prefix
            await channel.send(msg_content, delete_after=15 if ephemeral_flag else None)

    # Kiểm tra các tài nguyên của bot
    if not bot.http_session or bot.http_session.closed:
        await send_response("⚠️ Bot chưa sẵn sàng (Session HTTP). Vui lòng thử lại sau giây lát.", ephemeral_flag=True)
        return
    if not bot.db_pool:
        await send_response("⚠️ Bot chưa sẵn sàng (Kết nối Database). Vui lòng thử lại sau giây lát.", ephemeral_flag=True)
        return

    timeout_s, min_p = await utils.get_guild_game_settings(bot, guild_id) # Lấy cài đặt game
    guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
    prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

    # Kiểm tra game đang chạy
    if channel.id in bot.active_games:
        existing_game_state = bot.active_games[channel.id]
        if existing_game_state.get("active", False): 
            if "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
                existing_game_state["timeout_task"].cancel() # Hủy timeout cũ
            
            msg = f"⚠️ Một game Nối Từ đã đang diễn ra trong kênh này. Dùng lệnh `{prefix}stop` hoặc `/stop` để dừng game cũ trước."
            await send_response(msg, ephemeral_flag=True)
            return
        elif "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
             existing_game_state["timeout_task"].cancel() # Dọn dẹp timeout task nếu game ko active nhưng task còn

    current_phrase_words: list[str]
    current_phrase_normalized: str
    player_id_for_first_move = author.id 
    participants_since_start = set() 

    sent_game_start_message: discord.Message = None # Message thông báo bắt đầu game

    if not start_phrase_input: # Bot chọn từ
        possible_starts = ["ấm áp", "bầu trời", "dòng sông", "cây cầu", "máy tính", "điện thoại", "học sinh", "sinh viên", "viên phấn", "nhà cửa", "cơm nước", "xe cộ", "tình yêu", "hạnh phúc", "nỗi buồn", "áo quần", "quần đảo", "đảo xa"]
        random.shuffle(possible_starts)
        chosen_start_phrase = ""
        for phrase_attempt in possible_starts: # Tìm từ hợp lệ
            if await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(phrase_attempt, bot.http_session, bot.wiktionary_cache):
                 chosen_start_phrase = phrase_attempt
                 break
        if not chosen_start_phrase: # Ko tìm thấy từ nào
            msg = "⚠️ Bot không tìm được từ bắt đầu ngẫu nhiên hợp lệ. Bạn có thể thử bắt đầu game bằng một cụm từ cụ thể!"
            await send_response(msg, ephemeral_flag=True)
            return

        current_phrase_normalized = chosen_start_phrase
        current_phrase_words = current_phrase_normalized.split()
        original_input_display = " ".join(word.capitalize() for word in current_phrase_words) # Hiển thị viết hoa
        response_msg_content = f"🤖 Bot đã chọn từ bắt đầu: **{original_input_display}**\n👉 Chữ cần nối tiếp theo là: **{current_phrase_words[1].capitalize()}**"
        
        if interaction: # Gửi response qua interaction
            if interaction.response.is_done(): 
                 sent_game_start_message = await interaction.followup.send(response_msg_content, wait=True)
            else: 
                 await interaction.response.send_message(response_msg_content)
                 sent_game_start_message = await interaction.original_response()
        else: # Gửi qua channel (prefix command)
            sent_game_start_message = await channel.send(response_msg_content)

        player_id_for_first_move = bot.user.id # Bot là người đi đầu
    else: # Người chơi cung cấp từ
        original_input_display = start_phrase_input.strip()
        temp_words = utils.get_words_from_input(original_input_display)

        if len(temp_words) != 2: # Phải đúng 2 chữ
            msg = f"⚠️ Cụm từ bắt đầu \"**{original_input_display}**\" phải có **đúng 2 chữ**."
            await send_response(msg, ephemeral_flag=True)
            return

        current_phrase_normalized = f"{temp_words[0]} {temp_words[1]}"
        # Kiểm tra Wiktionary
        if not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(current_phrase_normalized, bot.http_session, bot.wiktionary_cache):
            msg = f"⚠️ Cụm từ \"**{original_input_display.title()}**\" không hợp lệ theo Wiktionary."
            await send_response(msg, ephemeral_flag=True)
            return
        
        current_phrase_words = temp_words
        capitalized_display = " ".join(w.capitalize() for w in current_phrase_words)
        response_msg_content = f"🎮 Game được bắt đầu bởi {author.mention} với cụm từ: **{capitalized_display}**\n👉 Chữ cần nối tiếp theo là: **{current_phrase_words[1].capitalize()}**"

        if interaction:
            if interaction.response.is_done():
                sent_game_start_message = await interaction.followup.send(response_msg_content, wait=True)
            else:
                await interaction.response.send_message(response_msg_content)
                sent_game_start_message = await interaction.original_response()
        else:
            sent_game_start_message = await channel.send(response_msg_content)
        
        if player_id_for_first_move != bot.user.id: # Người chơi bắt đầu -> thêm vào participants
             participants_since_start.add(player_id_for_first_move)

    # Lưu trạng thái game
    bot.active_games[channel.id] = {
        "current_phrase_str": current_phrase_normalized,
        "word_to_match_next": current_phrase_words[1],
        "used_phrases": {current_phrase_normalized}, # Set các từ đã dùng
        "last_player_id": player_id_for_first_move,
        "active": True, # Game đang hoạt động
        "last_correct_message_id": sent_game_start_message.id if sent_game_start_message else 0,
        "timeout_task": None, # Task kiểm tra timeout
        "participants_since_start": participants_since_start, 
        "timeout_can_be_activated": len(participants_since_start) >= min_p, 
        "guild_id": guild_id, 
        "min_players_for_timeout": min_p 
    }

    game_state = bot.active_games[channel.id]

    # Bắt đầu timeout nếu đủ người và người chơi đi đầu (ko phải bot)
    if game_state["timeout_can_be_activated"] and player_id_for_first_move != bot.user.id:
        new_timeout_task = asyncio.create_task(
            check_game_timeout( # Gọi hàm check timeout
                bot, channel.id, guild_id,
                game_state["last_player_id"],
                game_state["current_phrase_str"]
            )
        )
        game_state["timeout_task"] = new_timeout_task
        if channel: 
            try: # Thông báo timeout đã kích hoạt
                await channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi (tối thiểu: {min_p}). "
                    f"Thời gian chờ {timeout_s} giây cho mỗi lượt sẽ được áp dụng.",
                    delete_after=20 
                )
            except discord.HTTPException: pass


async def internal_stop_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member, 
                             guild_id: int, interaction: discord.Interaction = None):
    if channel.id in bot.active_games: # Nếu có game đang chạy
        game_to_stop = bot.active_games.pop(channel.id) # Lấy và xóa game state

        if "timeout_task" in game_to_stop and game_to_stop["timeout_task"] and not game_to_stop["timeout_task"].done():
            game_to_stop["timeout_task"].cancel() # Hủy timeout task
        
        # Reset win streak của người chơi cuối nếu game bị dừng đột ngột
        if game_to_stop.get("active") and game_to_stop.get("last_player_id") != bot.user.id:
            last_player_id = game_to_stop.get("last_player_id")
            last_player_guild_id = game_to_stop.get("guild_id", guild_id) 
            if last_player_id and last_player_guild_id and bot.db_pool:
                 await database.reset_win_streak_for_user(bot.db_pool, last_player_id, last_player_guild_id)

        embed = discord.Embed(description=f"👋 Game Nối Từ đã được dừng bởi {author.mention}.", color=discord.Color.orange())
        
        guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
        prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

        # Tạo view với nút "Chơi Lại", "Xem BXH"
        view = PostGameView(
            channel=channel, 
            original_starter_id=author.id, 
            command_prefix_for_guild=prefix,
            bot_instance=bot, # Truyền bot instance
            internal_start_game_callable=internal_start_game # Truyền hàm để "Chơi Lại"
        )
        
        msg_to_set_view: discord.Message = None
        try: # Gửi tin nhắn dừng game
            if interaction:
                if interaction.response.is_done(): 
                    msg_to_set_view = await interaction.followup.send(embed=embed, view=view, wait=True)
                else: 
                    await interaction.response.send_message(embed=embed, view=view)
                    msg_to_set_view = await interaction.original_response()
            else: 
                msg_to_set_view = await channel.send(embed=embed, view=view)
        except discord.HTTPException as e:
            print(f"Lỗi HTTP khi gửi tin nhắn dừng game: {e}")
            if interaction and channel : # Fallback nếu gửi qua interaction lỗi
                try: msg_to_set_view = await channel.send(embed=embed, view=view)
                except discord.HTTPException as e_ch: print(f"Lỗi HTTP fallback gửi tin nhắn dừng game: {e_ch}")
        
        if msg_to_set_view: view.message_to_edit = msg_to_set_view # Gán message cho view

    else: # Ko có game nào
        msg_content = "🤷 Hiện không có game Nối Từ nào đang diễn ra trong kênh này."
        if interaction:
            if not interaction.response.is_done(): await interaction.response.send_message(msg_content, ephemeral=True)
            else: await interaction.followup.send(msg_content, ephemeral=True)
        else: await channel.send(msg_content, delete_after=10)


async def process_game_message(bot: commands.Bot, message: discord.Message):
    # Xử lý tin nhắn trong game (gọi từ on_message event)
    channel_id = message.channel.id
    guild_id = message.guild.id 

    if not bot.http_session or bot.http_session.closed: return # Bot chưa sẵn sàng
    if not bot.db_pool: return

    if channel_id not in bot.active_games or not bot.active_games[channel_id].get("active", False):
        return # Ko có game active

    game_state = bot.active_games[channel_id]
    current_player_id = message.author.id
    current_player_name = message.author.name 

    # Kiểm tra guild_id của game state khớp với guild_id của message
    if game_state.get("guild_id") != guild_id:
        print(f"Lỗi: Game state kênh {channel_id} có guild_id {game_state.get('guild_id')} ko khớp {guild_id}.")
        if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
            game_state["timeout_task"].cancel() # Dọn dẹp task
        del bot.active_games[channel_id]
        return

    # Kiểm tra sai lượt
    if current_player_id == game_state["last_player_id"]:
        try:
            await message.add_reaction(bot_cfg.WRONG_TURN_REACTION)
            guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
            prefix_val = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX
            
            await message.channel.send(
                f"{bot_cfg.WRONG_TURN_REACTION} {message.author.mention}, bạn vừa đi rồi! Hãy đợi người khác. "
                f"(Dùng `{prefix_val}stop` hoặc `/stop` để dừng).",
                delete_after=bot_cfg.DELETE_WRONG_TURN_MESSAGE_AFTER
            )
            await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "wrong_turn", current_player_name)
        except (discord.Forbidden, discord.HTTPException): pass # Bỏ qua nếu ko react/send dc
        return

    user_input_original_str = message.content.strip()
    if not user_input_original_str: return # Bỏ qua msg rỗng

    user_phrase_words_lower = utils.get_words_from_input(user_input_original_str)

    if len(user_phrase_words_lower) != 2: # Ko phải cụm 2 chữ thì bỏ qua
        return

    word1_user, word2_user = user_phrase_words_lower[0], user_phrase_words_lower[1]
    expected_first_word = game_state["word_to_match_next"] # Chữ đầu dự kiến

    error_occurred = False # Cờ báo lỗi
    error_type_for_stat = None # Loại lỗi để ghi stat

    if word1_user != expected_first_word: # Sai chữ nối
        error_occurred = True; error_type_for_stat = "wrong_word_link"
    
    user_phrase_normalized = f"{word1_user} {word2_user}" # Từ chuẩn hóa

    # Kiểm tra Wiktionary nếu chưa có lỗi
    if not error_occurred and not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(user_phrase_normalized, bot.http_session, bot.wiktionary_cache):
        error_occurred = True; error_type_for_stat = "invalid_wiktionary"

    # Kiểm tra từ đã dùng nếu chưa có lỗi
    if not error_occurred and user_phrase_normalized in game_state["used_phrases"]:
        error_occurred = True; error_type_for_stat = "used_word_error"

    if error_occurred: # Nếu có lỗi
        try: await message.add_reaction(bot_cfg.ERROR_REACTION)
        except (discord.Forbidden, discord.HTTPException): pass
        if error_type_for_stat: # Cập nhật stat lỗi
            await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, error_type_for_stat, current_player_name)
        return 

    # --- ĐÚNG LƯỢT ---
    try: await message.add_reaction(bot_cfg.CORRECT_REACTION)
    except (discord.Forbidden, discord.HTTPException): pass
    await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "correct_moves", current_player_name)

    # Hủy timeout của người chơi trước
    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
        game_state["timeout_task"].cancel()

    # Cập nhật game state
    game_state["current_phrase_str"] = user_phrase_normalized
    game_state["word_to_match_next"] = word2_user
    game_state["used_phrases"].add(user_phrase_normalized)
    game_state["last_player_id"] = current_player_id
    game_state["last_correct_message_id"] = message.id

    if current_player_id != bot.user.id: # Thêm người chơi vào participants
        game_state["participants_since_start"].add(current_player_id)

    timeout_s_config, min_p_config = await utils.get_guild_game_settings(bot, guild_id)
    game_state["min_players_for_timeout"] = min_p_config # Cập nhật min_players (có thể admin đổi giữa game)

    # Kích hoạt timeout nếu đủ người và chưa active
    if not game_state["timeout_can_be_activated"] and \
       len(game_state["participants_since_start"]) >= game_state["min_players_for_timeout"]:
        game_state["timeout_can_be_activated"] = True
        if msg_channel := bot.get_channel(channel_id): 
            try: # Thông báo timeout kích hoạt
                await msg_channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi ({game_state['min_players_for_timeout']} tối thiểu). "
                    f"Timeout {timeout_s_config} giây sẽ áp dụng.",
                    delete_after=20
                )
            except discord.HTTPException: pass 

    # Bắt đầu timeout cho người chơi hiện tại nếu timeout_can_be_activated
    if game_state["timeout_can_be_activated"]:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(bot, channel_id, guild_id, game_state["last_player_id"], game_state["current_phrase_str"])
        )
        game_state["timeout_task"] = new_timeout_task