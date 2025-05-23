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
from .views import PostGameView


async def check_game_timeout(bot: commands.Bot, channel_id: int, guild_id: int, expected_last_player_id: int, expected_phrase_normalized: str): # expected_phrase_normalized là từ VN hoặc Hiragana của JP
    if not bot.db_pool: return 

    timeout_seconds_for_guild, _ , game_lang = await utils.get_guild_game_settings(bot, guild_id) # Lấy cả game_lang
    # Sửa: Lấy prefix từ DB thay vì bot_cfg
    guild_cfg_for_prefix = await database.get_guild_config(bot.db_pool, guild_id)
    command_prefix_for_guild = guild_cfg_for_prefix.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_for_prefix else bot_cfg.DEFAULT_COMMAND_PREFIX


    countdown_message: discord.Message = None
    message_channel = bot.get_channel(channel_id)
    if not message_channel or not isinstance(message_channel, discord.TextChannel):
        if channel_id in bot.active_games: del bot.active_games[channel_id] 
        return

    # Hiển thị từ cho phù hợp với ngôn ngữ
    display_phrase = expected_phrase_normalized.title() if game_lang == "VN" else expected_phrase_normalized

    initial_countdown_text_base = "" 
    if expected_last_player_id == bot.user.id:
        initial_countdown_text_base = f"⏳ Bot đã ra từ \"**{display_phrase}**\". "
    else:
        try:
            winner_user_to_be = await bot.fetch_user(expected_last_player_id)
            initial_countdown_text_base = f"⏳ {winner_user_to_be.mention} đã ra từ \"**{display_phrase}**\". "
        except discord.NotFound:
            initial_countdown_text_base = f"⏳ Người chơi ID {expected_last_player_id} đã ra từ \"**{display_phrase}**\". "
        except discord.HTTPException: 
            initial_countdown_text_base = f"⏳ Một người chơi đã ra từ \"**{display_phrase}**\". "

    try:
        countdown_message = await message_channel.send(f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {timeout_seconds_for_guild} giây.")
    except discord.HTTPException as e:
        print(f"Lỗi gửi msg đếm ngược: {e}")
        countdown_message = None

    time_slept = 0 
    edit_interval = 1 

    try:
        while time_slept < timeout_seconds_for_guild:
            await asyncio.sleep(min(edit_interval, timeout_seconds_for_guild - time_slept))
            time_slept += edit_interval

            if channel_id not in bot.active_games or not bot.active_games[channel_id]["active"]:
                if countdown_message: 
                    try: await countdown_message.delete()
                    except (discord.NotFound, discord.HTTPException): pass
                return

            game = bot.active_games[channel_id]
            # current_phrase_str giờ là từ VN hoặc Hiragana chuẩn hóa
            if not (game.get("last_player_id") == expected_last_player_id and \
                    game.get("current_phrase_str") == expected_phrase_normalized):
                if countdown_message: 
                    try: await countdown_message.delete()
                    except (discord.NotFound, discord.HTTPException): pass
                return

            if countdown_message: 
                remaining_time = max(0, timeout_seconds_for_guild - time_slept)
                new_text = f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {remaining_time} giây."
                if remaining_time > 0 :
                    try: await countdown_message.edit(content=new_text)
                    except (discord.NotFound, discord.HTTPException): countdown_message = None

            if time_slept >= timeout_seconds_for_guild: break 

        # --- HẾT GIỜ ---
        if countdown_message: 
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass

        if channel_id in bot.active_games and bot.active_games[channel_id]["active"]:
            game = bot.active_games[channel_id]
            if game.get("last_player_id") == expected_last_player_id and \
               game.get("current_phrase_str") == expected_phrase_normalized:

                winner_id = game["last_player_id"]
                
                # Hiển thị từ thắng cuộc
                winning_phrase_display = ""
                if game_lang == "VN":
                    winning_phrase_display = " ".join(w.capitalize() for w in expected_phrase_normalized.split())
                else: # JP
                    # game["current_phrase_display_form"] chứa dạng Kanji/Hira gốc mà người chơi hoặc bot đã dùng
                    winning_phrase_display = game.get("current_phrase_display_form", expected_phrase_normalized)


                win_embed = discord.Embed(color=discord.Color.gold())
                original_starter_for_view = winner_id 

                if winner_id == bot.user.id: 
                    win_embed.title = "⏳ Hết Giờ! ⏳"
                    win_embed.description = (
                        f"Đã hết {timeout_seconds_for_guild} giây! Không ai nối được từ \"**{winning_phrase_display}**\" của Bot.\n"
                        f"Game kết thúc không có người thắng."
                    )
                    participants_list = list(game.get("participants_since_start", []))
                    original_starter_for_view = participants_list[0] if participants_list else bot.user.id
                else: 
                    winner_name_display = f"User ID {winner_id}" 
                    winner_avatar_url = None
                    try:
                        winner_user = await bot.fetch_user(winner_id)
                        winner_name_display = winner_user.name 
                        winner_avatar_url = winner_user.display_avatar.url
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display)

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
                        if user_stats: 
                             win_embed.add_field(name="Thành Tích", value=f"Thắng: {user_stats['wins']} | Chuỗi: {user_stats['current_win_streak']} (Max: {user_stats['max_win_streak']})", inline=False)
                        original_starter_for_view = winner_id
                    except discord.NotFound: 
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}")
                        win_embed.title = "🎉 Người Chơi Thắng Cuộc! 🎉"
                        win_embed.description = f"Người chơi ID {winner_id} đã thắng với từ \"**{winning_phrase_display}**\"! (Không thể lấy thông tin chi tiết)."
                    except discord.HTTPException: 
                         await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)")
                         win_embed.title = "🎉 Một Người Chơi Thắng! 🎉"
                         win_embed.description = f"Một người chơi đã thắng với từ \"**{winning_phrase_display}**\"! (Lỗi khi lấy thông tin người chơi)."

                view = PostGameView(
                    channel=message_channel,
                    original_starter_id=original_starter_for_view,
                    command_prefix_for_guild=command_prefix_for_guild,
                    bot_instance=bot, 
                    internal_start_game_callable=internal_start_game 
                )
                msg_with_view = await message_channel.send(embed=win_embed, view=view)
                view.message_to_edit = msg_with_view 

                if channel_id in bot.active_games and \
                   bot.active_games[channel_id].get("last_player_id") == expected_last_player_id and \
                   bot.active_games[channel_id].get("current_phrase_str") == expected_phrase_normalized:
                    del bot.active_games[channel_id]

    except asyncio.CancelledError: 
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
    async def send_response(msg_content: str, ephemeral_flag: bool = False):
        # ... (giữ nguyên)
        if interaction:
            if interaction.response.is_done(): # Đã defer/reply
                await interaction.followup.send(msg_content, ephemeral=ephemeral_flag)
            else:
                await interaction.response.send_message(msg_content, ephemeral=ephemeral_flag)
        else: # Context lệnh prefix
            await channel.send(msg_content, delete_after=15 if ephemeral_flag else None)


    if not bot.http_session or bot.http_session.closed:
        await send_response("⚠️ Bot chưa sẵn sàng (Session HTTP). Vui lòng thử lại sau giây lát.", ephemeral_flag=True)
        return
    if not bot.db_pool:
        await send_response("⚠️ Bot chưa sẵn sàng (Kết nối Database). Vui lòng thử lại sau giây lát.", ephemeral_flag=True)
        return

    timeout_s, min_p, game_lang = await utils.get_guild_game_settings(bot, guild_id)
    if game_lang == "JP" and not bot.kakasi:
        await send_response("⚠️ Không thể bắt đầu game Tiếng Nhật do bot chưa được cấu hình đúng (PyKakasi).", ephemeral_flag=True)
        return
        
    guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
    prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

    if channel.id in bot.active_games:
        existing_game_state = bot.active_games[channel.id]
        if existing_game_state.get("active", False):
            if "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
                existing_game_state["timeout_task"].cancel() 
            msg = f"⚠️ Một game Nối Từ ({existing_game_state.get('game_language', '??').upper()}) đã đang diễn ra. Dùng `{prefix}stop` hoặc `/stop` để dừng."
            await send_response(msg, ephemeral_flag=True)
            return
        elif "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
             existing_game_state["timeout_task"].cancel() 

    # --- Biến cho game state ---
    # current_phrase_str: từ VN chuẩn hóa hoặc Hiragana chuẩn hóa của từ JP
    # word_to_match_next: chữ thứ 2 của từ VN, hoặc ký tự Hiragana cuối của từ JP
    # current_phrase_display_form: Dạng hiển thị gốc của từ (quan trọng cho JP để giữ Kanji/Kata)
    current_phrase_str: str = "" 
    word_to_match_next: str = ""
    current_phrase_display_form: str = "" # Dùng để hiển thị, đặc biệt cho JP
    
    player_id_for_first_move = author.id
    participants_since_start = set()
    sent_game_start_message: discord.Message = None

    if not start_phrase_input: # Bot chọn từ
        if game_lang == "VN":
            possible_starts_vn = ["ấm áp", "bầu trời", "dòng sông", "cây cầu", "máy tính", "điện thoại", "học sinh", "sinh viên", "viên phấn", "nhà cửa", "cơm nước", "xe cộ", "tình yêu", "hạnh phúc", "nỗi buồn", "áo quần", "quần đảo", "đảo xa"]
            random.shuffle(possible_starts_vn)
            chosen_start_phrase_vn = ""
            for phrase_attempt in possible_starts_vn:
                if await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                    phrase_attempt, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
                ):
                    chosen_start_phrase_vn = phrase_attempt
                    break
            if not chosen_start_phrase_vn:
                await send_response("⚠️ Bot không tìm được từ bắt đầu Tiếng Việt ngẫu nhiên hợp lệ.", ephemeral_flag=True); return
            
            current_phrase_str = chosen_start_phrase_vn
            current_phrase_words = current_phrase_str.split()
            word_to_match_next = current_phrase_words[1]
            current_phrase_display_form = " ".join(word.capitalize() for word in current_phrase_words)
            response_msg_content = f"🤖 Bot (VN) đã chọn: **{current_phrase_display_form}**\n👉 Chữ cần nối: **{word_to_match_next.capitalize()}**"
        
        else: # JP game, bot chọn từ
            if not bot.local_dictionary_jp:
                await send_response("⚠️ Bot không có từ điển Tiếng Nhật để chọn từ bắt đầu.", ephemeral_flag=True); return
            
            # Chọn từ JP ngẫu nhiên từ local dict, ưu tiên từ không kết thúc bằng ん trừ khi không còn lựa chọn
            valid_jp_starts = [
                entry for entry in bot.local_dictionary_jp 
                if entry.get('hira') and not entry['hira'].endswith('ん')
            ]
            if not valid_jp_starts: # Nếu tất cả đều kết thúc bằng ん hoặc dict rỗng
                valid_jp_starts = [entry for entry in bot.local_dictionary_jp if entry.get('hira')]

            if not valid_jp_starts:
                 await send_response("⚠️ Bot không tìm được từ Tiếng Nhật ngẫu nhiên hợp lệ.", ephemeral_flag=True); return

            chosen_entry = random.choice(valid_jp_starts)
            current_phrase_str = chosen_entry['hira'] # Hiragana chuẩn hóa
            current_phrase_display_form = chosen_entry.get('kanji', current_phrase_str) # Ưu tiên Kanji/Kata để hiển thị
            
            last_hira_char = utils.get_last_hiragana_char(current_phrase_str)
            if not last_hira_char: # Không thể lấy ký tự cuối (lỗi hiếm)
                await send_response("⚠️ Lỗi xử lý từ bắt đầu Tiếng Nhật của Bot.", ephemeral_flag=True); return
            word_to_match_next = last_hira_char # Ký tự Hiragana cuối

            response_msg_content = f"🤖 Bot (JP) đã chọn: **{current_phrase_display_form}** (`{current_phrase_str}`)\n👉 Âm tiết cần nối: **{word_to_match_next}**"

        player_id_for_first_move = bot.user.id
    
    else: # Người chơi cung cấp từ
        start_phrase_input_cleaned = start_phrase_input.strip()
        if game_lang == "VN":
            temp_words = utils.get_words_from_input(start_phrase_input_cleaned)
            if len(temp_words) != 2:
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned}**\" phải có **đúng 2 chữ** (Tiếng Việt).", ephemeral_flag=True); return

            phrase_to_check_vn = f"{temp_words[0]} {temp_words[1]}"
            if not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                phrase_to_check_vn, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
            ):
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned.title()}**\" không hợp lệ theo từ điển VN.", ephemeral_flag=True); return
            
            current_phrase_str = phrase_to_check_vn
            word_to_match_next = temp_words[1]
            current_phrase_display_form = " ".join(w.capitalize() for w in temp_words)
            response_msg_content = f"🎮 Game VN được bắt đầu bởi {author.mention} với: **{current_phrase_display_form}**\n👉 Chữ cần nối: **{word_to_match_next.capitalize()}**"
        
        else: # JP game, người chơi cung cấp từ
            if not bot.kakasi: # Kiểm tra lại Kakasi
                 await send_response("⚠️ Lỗi: Không thể xử lý từ Tiếng Nhật do thiếu thư viện trên bot.", ephemeral_flag=True); return

            is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
                start_phrase_input_cleaned, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
            )
            if not is_valid_jp or not hira_form_jp:
                await send_response(f"⚠️ Từ \"**{start_phrase_input_cleaned}**\" không hợp lệ theo từ điển JP.", ephemeral_flag=True); return

            # Luật Shiritori: Không được kết thúc bằng ん (n) trong lượt đầu tiên (có thể nới lỏng nếu muốn)
            # if hira_form_jp.endswith('ん'):
            #     await send_response(f"⚠️ Từ bắt đầu \"**{start_phrase_input_cleaned}**\" (`{hira_form_jp}`) kết thúc bằng 'ん'. Vui lòng chọn từ khác.", ephemeral_flag=True); return

            current_phrase_str = hira_form_jp # Hiragana chuẩn hóa
            current_phrase_display_form = start_phrase_input_cleaned # Giữ nguyên dạng input của user để hiển thị
            
            last_hira_char = utils.get_last_hiragana_char(current_phrase_str)
            if not last_hira_char:
                await send_response(f"⚠️ Lỗi xử lý từ \"**{start_phrase_input_cleaned}**\".", ephemeral_flag=True); return
            word_to_match_next = last_hira_char

            response_msg_content = f"🎮 Game JP được bắt đầu bởi {author.mention} với: **{current_phrase_display_form}** (`{current_phrase_str}`)\n👉 Âm tiết cần nối: **{word_to_match_next}**"

        if player_id_for_first_move != bot.user.id:
             participants_since_start.add(player_id_for_first_move)

    # Gửi tin nhắn bắt đầu game
    if interaction:
        if interaction.response.is_done():
             sent_game_start_message = await interaction.followup.send(response_msg_content, wait=True)
        else:
             await interaction.response.send_message(response_msg_content)
             sent_game_start_message = await interaction.original_response()
    else:
        sent_game_start_message = await channel.send(response_msg_content)


    # Lưu trạng thái game
    bot.active_games[channel.id] = {
        "game_language": game_lang, # Quan trọng: lưu ngôn ngữ của game
        "current_phrase_str": current_phrase_str, # Từ VN hoặc Hiragana của JP
        "current_phrase_display_form": current_phrase_display_form, # Dạng hiển thị
        "word_to_match_next": word_to_match_next, # Chữ VN hoặc Hiragana cuối của JP
        "used_phrases": {current_phrase_str}, # Set các từ đã dùng (dạng chuẩn hóa)
        "last_player_id": player_id_for_first_move,
        "active": True,
        "last_correct_message_id": sent_game_start_message.id if sent_game_start_message else 0,
        "timeout_task": None,
        "participants_since_start": participants_since_start,
        "timeout_can_be_activated": len(participants_since_start) >= min_p,
        "guild_id": guild_id,
        "min_players_for_timeout": min_p
    }

    game_state = bot.active_games[channel.id]

    if game_state["timeout_can_be_activated"] and player_id_for_first_move != bot.user.id:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(
                bot, channel.id, guild_id,
                game_state["last_player_id"],
                game_state["current_phrase_str"] # Truyền từ chuẩn hóa
            )
        )
        game_state["timeout_task"] = new_timeout_task
        if channel:
            try: 
                await channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi (tối thiểu: {min_p}). "
                    f"Thời gian chờ {timeout_s} giây cho mỗi lượt sẽ được áp dụng.",
                    delete_after=20
                )
            except discord.HTTPException: pass


async def internal_stop_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member,
                             guild_id: int, interaction: discord.Interaction = None):
    # ... (Giữ nguyên, PostGameView sẽ tự xử lý việc gọi lại internal_start_game,
    # và internal_start_game sẽ đọc lại game_lang từ DB)
    if channel.id in bot.active_games: 
        game_to_stop = bot.active_games.pop(channel.id) 

        if "timeout_task" in game_to_stop and game_to_stop["timeout_task"] and not game_to_stop["timeout_task"].done():
            game_to_stop["timeout_task"].cancel() 

        if game_to_stop.get("active") and game_to_stop.get("last_player_id") != bot.user.id:
            last_player_id = game_to_stop.get("last_player_id")
            last_player_guild_id = game_to_stop.get("guild_id", guild_id)
            if last_player_id and last_player_guild_id and bot.db_pool:
                 await database.reset_win_streak_for_user(bot.db_pool, last_player_id, last_player_guild_id)

        game_lang_stopped = game_to_stop.get('game_language', '??').upper()
        embed = discord.Embed(description=f"👋 Game Nối Từ ({game_lang_stopped}) đã được dừng bởi {author.mention}.", color=discord.Color.orange())


        guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
        prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

        view = PostGameView(
            channel=channel,
            original_starter_id=author.id,
            command_prefix_for_guild=prefix,
            bot_instance=bot, 
            internal_start_game_callable=internal_start_game 
        )

        msg_to_set_view: discord.Message = None
        try: 
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
            if interaction and channel : 
                try: msg_to_set_view = await channel.send(embed=embed, view=view)
                except discord.HTTPException as e_ch: print(f"Lỗi HTTP fallback gửi tin nhắn dừng game: {e_ch}")

        if msg_to_set_view: view.message_to_edit = msg_to_set_view

    else: 
        msg_content = "🤷 Hiện không có game Nối Từ nào đang diễn ra trong kênh này."
        if interaction:
            if not interaction.response.is_done(): await interaction.response.send_message(msg_content, ephemeral=True)
            else: await interaction.followup.send(msg_content, ephemeral=True)
        else: await channel.send(msg_content, delete_after=10)


async def process_game_message(bot: commands.Bot, message: discord.Message):
    channel_id = message.channel.id
    guild_id = message.guild.id

    if not bot.http_session or bot.http_session.closed: return 
    if not bot.db_pool: return

    if channel_id not in bot.active_games or not bot.active_games[channel_id].get("active", False):
        return 

    game_state = bot.active_games[channel_id]
    current_player_id = message.author.id
    current_player_name = message.author.name
    game_lang = game_state.get("game_language", "VN").upper() # Lấy ngôn ngữ game

    if game_lang == "JP" and not bot.kakasi: # Kiểm tra Kakasi cho game JP
        # Có thể gửi một thông báo lỗi một lần cho kênh này nếu muốn
        print(f"WARNING: Kakasi không sẵn sàng cho game JP ở kênh {channel_id}")
        return


    if game_state.get("guild_id") != guild_id:
        print(f"Lỗi: Game state kênh {channel_id} có guild_id {game_state.get('guild_id')} ko khớp {guild_id}.")
        if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
            game_state["timeout_task"].cancel() 
        del bot.active_games[channel_id]
        return

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
        except (discord.Forbidden, discord.HTTPException): pass 
        return

    user_input_original_str = message.content.strip()
    if not user_input_original_str: return 

    # --- Biến cho lượt đi hiện tại ---
    # phrase_to_validate: từ VN chuẩn hóa hoặc Hiragana chuẩn hóa của JP
    # display_form_for_current_move: dạng hiển thị gốc của từ (quan trọng cho JP)
    phrase_to_validate: str = ""
    display_form_for_current_move: str = user_input_original_str # Mặc định là input gốc
    
    expected_first_char_or_word = game_state["word_to_match_next"] # Chữ VN hoặc Hira JP cần nối

    error_occurred = False 
    error_type_for_stat = None 

    if game_lang == "VN":
        user_phrase_words_lower = utils.get_words_from_input(user_input_original_str)
        if len(user_phrase_words_lower) != 2: return # Không phải cụm 2 chữ VN thì bỏ qua

        word1_user, word2_user = user_phrase_words_lower[0], user_phrase_words_lower[1]
        phrase_to_validate = f"{word1_user} {word2_user}"
        display_form_for_current_move = " ".join(w.capitalize() for w in user_phrase_words_lower)

        if word1_user != expected_first_char_or_word:
            error_occurred = True; error_type_for_stat = "wrong_word_link"
        
        if not error_occurred and not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
            phrase_to_validate, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
        ):
            error_occurred = True; error_type_for_stat = "invalid_wiktionary"
    
    else: # JP game
        is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
            user_input_original_str, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
        )
        if not is_valid_jp or not hira_form_jp:
            error_occurred = True; error_type_for_stat = "invalid_wiktionary"
        else:
            phrase_to_validate = hira_form_jp # Dùng Hiragana chuẩn để check và lưu
            # display_form_for_current_move đã là user_input_original_str

            first_char_current_hira = utils.get_first_hiragana_char(hira_form_jp)
            if not first_char_current_hira or first_char_current_hira != expected_first_char_or_word:
                error_occurred = True; error_type_for_stat = "wrong_word_link"
            
            # Luật đặc biệt cho Shiritori: từ không được kết thúc bằng 'ん' (trừ khi được cấu hình khác)
            # Ở đây, ta sẽ cho phép từ kết thúc bằng ん, và từ tiếp theo phải bắt đầu bằng ん.
            # Nếu muốn cấm từ kết thúc bằng ん, thêm check ở đây:
            # if hira_form_jp.endswith('ん'):
            #     error_occurred = True; error_type_for_stat = "invalid_word_endsWithN" # Stat mới nếu cần

    # Kiểm tra từ đã dùng (áp dụng cho cả VN và JP, dùng phrase_to_validate đã chuẩn hóa)
    if not error_occurred and phrase_to_validate in game_state["used_phrases"]:
        error_occurred = True; error_type_for_stat = "used_word_error"

    if error_occurred: 
        try: await message.add_reaction(bot_cfg.ERROR_REACTION)
        except (discord.Forbidden, discord.HTTPException): pass
        if error_type_for_stat: 
            await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, error_type_for_stat, current_player_name)
        return

    # --- ĐÚNG LƯỢT ---
    try: await message.add_reaction(bot_cfg.CORRECT_REACTION)
    except (discord.Forbidden, discord.HTTPException): pass
    await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "correct_moves", current_player_name)

    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
        game_state["timeout_task"].cancel()

    # Cập nhật game state
    game_state["current_phrase_str"] = phrase_to_validate # Từ VN hoặc Hiragana JP
    game_state["current_phrase_display_form"] = display_form_for_current_move # Dạng hiển thị

    if game_lang == "VN":
        game_state["word_to_match_next"] = phrase_to_validate.split()[1]
    else: # JP
        last_hira_char_of_current = utils.get_last_hiragana_char(phrase_to_validate)
        if not last_hira_char_of_current: # Lỗi hiếm
            # Nên dừng game hoặc báo lỗi nghiêm trọng ở đây
            print(f"LỖI NGHIÊM TRỌNG: Không thể lấy ký tự cuối của từ JP hợp lệ: {phrase_to_validate}")
            # Có thể tạm thời không thay đổi word_to_match_next để tránh lỗi
            # Hoặc cố gắng rollback/báo lỗi cho người dùng
            await message.channel.send(f"⚠️ Bot gặp lỗi xử lý từ \"{display_form_for_current_move}\". Lượt này có thể không được tính đúng.")
            # Không cập nhật word_to_match_next nếu lỗi
        else:
            game_state["word_to_match_next"] = last_hira_char_of_current


    game_state["used_phrases"].add(phrase_to_validate)
    game_state["last_player_id"] = current_player_id
    game_state["last_correct_message_id"] = message.id

    if current_player_id != bot.user.id: 
        game_state["participants_since_start"].add(current_player_id)

    timeout_s_config, min_p_config, _ = await utils.get_guild_game_settings(bot, guild_id) # Lấy lại config, không cần game_lang ở đây
    game_state["min_players_for_timeout"] = min_p_config 

    if not game_state["timeout_can_be_activated"] and \
       len(game_state["participants_since_start"]) >= game_state["min_players_for_timeout"]:
        game_state["timeout_can_be_activated"] = True
        if msg_channel := bot.get_channel(channel_id):
            try: 
                await msg_channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi ({game_state['min_players_for_timeout']} tối thiểu). "
                    f"Timeout {timeout_s_config} giây sẽ áp dụng.",
                    delete_after=20
                )
            except discord.HTTPException: pass

    if game_state["timeout_can_be_activated"]:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(bot, channel_id, guild_id, game_state["last_player_id"], game_state["current_phrase_str"]) # Truyền từ chuẩn hóa
        )
        game_state["timeout_task"] = new_timeout_task