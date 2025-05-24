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


async def check_game_timeout(bot: commands.Bot, channel_id: int, guild_id: int, expected_last_player_id: int, expected_phrase_normalized: str, game_lang: str):
    if not bot.db_pool: return

    timeout_seconds_for_guild, _ , _ = await utils.get_channel_game_settings(bot, guild_id, channel_id)

    guild_cfg_for_prefix = await database.get_guild_config(bot.db_pool, guild_id)
    command_prefix_for_guild = guild_cfg_for_prefix.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_for_prefix else bot_cfg.DEFAULT_COMMAND_PREFIX

    countdown_message: discord.Message = None
    message_channel = bot.get_channel(channel_id)
    if not message_channel or not isinstance(message_channel, discord.TextChannel):
        if channel_id in bot.active_games: del bot.active_games[channel_id]
        return

    display_phrase_for_countdown = expected_phrase_normalized.title() if game_lang == "VN" else expected_phrase_normalized

    initial_countdown_text_base = ""
    if expected_last_player_id == bot.user.id:
        initial_countdown_text_base = f"⏳ {bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã ra từ \"**{display_phrase_for_countdown}**\". "
    else:
        try:
            winner_user_to_be = await bot.fetch_user(expected_last_player_id)
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} {winner_user_to_be.mention} đã ra từ \"**{display_phrase_for_countdown}**\". "
        except discord.NotFound:
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} Người chơi ID {expected_last_player_id} đã ra từ \"**{display_phrase_for_countdown}**\". "
        except discord.HTTPException:
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} Một người chơi đã ra từ \"**{display_phrase_for_countdown}**\". "

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

        if countdown_message:
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass

        if channel_id in bot.active_games and bot.active_games[channel_id]["active"]:
            game = bot.active_games[channel_id]
            if game.get("last_player_id") == expected_last_player_id and \
               game.get("current_phrase_str") == expected_phrase_normalized:

                winner_id = game["last_player_id"]
                current_game_lang = game.get("game_language", "VN")

                winning_phrase_display = ""
                if current_game_lang == "VN":
                    winning_phrase_display = " ".join(w.capitalize() for w in expected_phrase_normalized.split())
                else:
                    winning_phrase_display = game.get("current_phrase_display_form", expected_phrase_normalized)

                win_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_WIN)
                original_starter_for_view = winner_id
                game_lang_display = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if current_game_lang == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"

                if winner_id == bot.user.id:
                    win_embed.title = f"{bot_cfg.TIMEOUT_WIN_ICON} Hết Giờ! Không Ai Nối Từ Của Bot {bot_cfg.TIMEOUT_WIN_ICON}"
                    win_embed.description = (
                        f"Đã hết **{timeout_seconds_for_guild} giây**! Không ai nối được từ \"**{winning_phrase_display}**\" của {bot_cfg.BOT_PLAYER_START_EMOJI} Bot.\n"
                        f"Game Nối Từ ({game_lang_display}) kết thúc không có người thắng."
                    )
                    participants_list = list(game.get("participants_since_start", []))
                    original_starter_for_view = participants_list[0] if participants_list else bot.user.id
                    if bot.user.display_avatar: win_embed.set_thumbnail(url=bot.user.display_avatar.url)
                else:
                    winner_name_display = f"User ID {winner_id}"
                    winner_user_obj = None
                    try:
                        winner_user_obj = await bot.fetch_user(winner_id)
                        winner_name_display = winner_user_obj.name
                        if winner_user_obj.display_avatar: win_embed.set_thumbnail(url=winner_user_obj.display_avatar.url)

                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display, game_language=current_game_lang)
                        for pid in game.get("participants_since_start", set()):
                            if pid != winner_id and pid != bot.user.id:
                                await database.reset_win_streak_for_user(bot.db_pool, pid, guild_id, game_language=current_game_lang)

                        win_embed.title = f"{bot_cfg.WIN_ICON} {discord.utils.escape_markdown(winner_name_display)} Chiến Thắng! {bot_cfg.WIN_ICON}"
                        win_embed.description = (
                            f"{winner_user_obj.mention} đã chiến thắng game Nối Từ ({game_lang_display})!\n"
                            f"Không ai nối tiếp được từ \"**{winning_phrase_display}**\" của bạn trong **{timeout_seconds_for_guild} giây**."
                        )
                        user_stats = await database.get_user_stats_entry(bot.db_pool, winner_id, guild_id, current_game_lang, winner_name_display)
                        if user_stats:
                             stats_text = (
                                 f"🏅 Tổng thắng: **{user_stats['wins']}**\n"
                                 f"🔥 Chuỗi thắng hiện tại: **{user_stats['current_win_streak']}** (Max: **{user_stats['max_win_streak']}**)"
                             )
                             win_embed.add_field(name="Thành Tích Cá Nhân", value=stats_text, inline=False)
                        original_starter_for_view = winner_id
                    except discord.NotFound:
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}", game_language=current_game_lang)
                        win_embed.title = f"{bot_cfg.WIN_ICON} Người Chơi ID {winner_id} Thắng Cuộc! {bot_cfg.WIN_ICON}"
                        win_embed.description = f"Người chơi ID {winner_id} đã thắng game ({game_lang_display}) với từ \"**{winning_phrase_display}**\"! (Không thể lấy thông tin chi tiết)."
                    except discord.HTTPException:
                         await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)", game_language=current_game_lang)
                         win_embed.title = f"{bot_cfg.WIN_ICON} Một Người Chơi Thắng! {bot_cfg.WIN_ICON}"
                         win_embed.description = f"Một người chơi đã thắng game ({game_lang_display}) với từ \"**{winning_phrase_display}**\"! (Lỗi khi lấy thông tin người chơi)."

                win_embed.set_footer(text=f"Kênh: #{message_channel.name} | Server: {message_channel.guild.name}")

                view = PostGameView(
                    channel=message_channel,
                    original_starter_id=original_starter_for_view,
                    command_prefix_for_guild=command_prefix_for_guild,
                    bot_instance=bot,
                    internal_start_game_callable=internal_start_game
                )
                msg_with_view = await message_channel.send(embed=win_embed, view=view)
                if msg_with_view: view.message_to_edit = msg_with_view

                if message_channel.guild:
                    await utils.send_random_guild_emoji_if_any(message_channel, message_channel.guild)

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

    async def send_response(msg_content: str, ephemeral_flag: bool = True, embed=None):
        target = interaction if interaction else commands.Context(message=None, bot=bot, view=None, prefix=None)
        if interaction:
            target = interaction
        elif hasattr(channel, 'last_message') and channel.last_message:
             mock_msg = await channel.fetch_message(channel.last_message_id) if channel.last_message_id else None
             if mock_msg:
                target = await bot.get_context(mock_msg)
                target.author = author
             else:
                await channel.send(msg_content, embed=embed, delete_after=15 if ephemeral_flag else None)
                return
        else:
            await channel.send(msg_content, embed=embed, delete_after=15 if ephemeral_flag else None)
            return

        await utils._send_message_smart(target, content=msg_content, embed=embed, ephemeral=ephemeral_flag)

    if not bot.http_session or bot.http_session.closed:
        await send_response("⚠️ Bot chưa sẵn sàng (Session HTTP). Vui lòng thử lại sau giây lát.")
        return
    if not bot.db_pool:
        await send_response("⚠️ Bot chưa sẵn sàng (Kết nối Database). Vui lòng thử lại sau giây lát.")
        return

    timeout_s, min_p, game_lang_for_channel = await utils.get_channel_game_settings(bot, guild_id, channel.id)

    if not game_lang_for_channel:
        await send_response(f"⚠️ Kênh này chưa được cấu hình để chơi Nối Từ. Admin có thể dùng `/config set_vn_channel` hoặc `/config set_jp_channel`.")
        return

    if game_lang_for_channel == "JP" and not bot.kakasi:
        await send_response("⚠️ Không thể bắt đầu game Tiếng Nhật do bot chưa được cấu hình đúng (PyKakasi).")
        return

    guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
    prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

    if channel.id in bot.active_games:
        existing_game_state = bot.active_games[channel.id]
        if existing_game_state.get("active", False):
            if "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
                existing_game_state["timeout_task"].cancel()
            current_game_lang_name = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if existing_game_state.get('game_language') == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"
            msg = f"⚠️ Một game Nối Từ ({current_game_lang_name}) đã đang diễn ra. Dùng `{prefix}stop` hoặc `/stop` để dừng."
            await send_response(msg)
            return
        elif "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
             existing_game_state["timeout_task"].cancel()

    current_phrase_str: str = ""
    word_to_match_next: str = ""
    current_phrase_display_form: str = ""

    player_id_for_first_move = author.id
    participants_since_start = set()
    sent_game_start_message: discord.Message = None

    if interaction and not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=False)
        except discord.HTTPException as e:
            print(f"Warning: Failed to defer interaction in internal_start_game: {e}")

    game_start_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_GAME_START)
    game_author_name = ""
    game_author_icon_url = bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None

    if not start_phrase_input:
        player_id_for_first_move = bot.user.id # Bot starts
        if game_lang_for_channel == "VN":
            game_author_name = f"{bot_cfg.GAME_VN_ICON} Nối Từ Tiếng Việt"
            chosen_start_phrase_vn = ""
            
            if bot.local_dictionary_vn:
                two_word_phrases_vn = [
                    phrase for phrase in list(bot.local_dictionary_vn) # Chuyển set -> list để shuffle
                    if len(phrase.split()) == 2
                ]
                if two_word_phrases_vn: # Kiểm tra nếu có cụm 2 chữ
                    random.shuffle(two_word_phrases_vn)
                    # Không check Wiktionary lại nếu từ điển local được coi là đáng tin
                    chosen_start_phrase_vn = two_word_phrases_vn[0] 
            
            if not chosen_start_phrase_vn: # Fallback nếu ko tìm đc từ file hoặc file rỗng/ko có cụm 2 từ
                possible_starts_vn_fallback = ["bầu trời", "dòng sông", "học sinh", "sinh viên", "nhà cửa", "tình yêu", "hạnh phúc"]
                random.shuffle(possible_starts_vn_fallback)
                for phrase_attempt_fallback in possible_starts_vn_fallback:
                     if await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                        phrase_attempt_fallback, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
                    ):
                        chosen_start_phrase_vn = phrase_attempt_fallback
                        break
            
            if not chosen_start_phrase_vn: # Nếu cả file và fallback đều không được
                await send_response("⚠️ Bot không tìm được từ bắt đầu Tiếng Việt ngẫu nhiên hợp lệ từ từ điển."); return

            current_phrase_str = chosen_start_phrase_vn.lower() 
            current_phrase_words = current_phrase_str.split()
            if len(current_phrase_words) != 2: 
                await send_response("⚠️ Bot chọn từ bắt đầu không hợp lệ (không phải 2 chữ). Vui lòng thử lại."); return

            word_to_match_next = current_phrase_words[1]
            current_phrase_display_form = " ".join(word.capitalize() for word in current_phrase_words)
            game_start_embed.description = f"{bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã chọn: **{current_phrase_display_form}**\n\n🔗 Tiếp theo: **{word_to_match_next.capitalize()}**"

        else: # JP game, bot chọn từ
            game_author_name = f"{bot_cfg.GAME_JP_ICON} Shiritori (しりとり)"
            if not bot.local_dictionary_jp:
                await send_response("⚠️ Bot không có từ điển Tiếng Nhật để chọn từ bắt đầu."); return

            valid_jp_starts = [
                entry for entry in bot.local_dictionary_jp
                if entry.get('hira') and not entry['hira'].endswith('ん')
            ]
            if not valid_jp_starts: # Nếu ko có từ ko kết thúc bằng 'ん', lấy bất kỳ từ nào
                valid_jp_starts = [entry for entry in bot.local_dictionary_jp if entry.get('hira')]

            if not valid_jp_starts:
                 await send_response("⚠️ Bot không tìm được từ Tiếng Nhật ngẫu nhiên hợp lệ từ từ điển."); return

            chosen_entry = random.choice(valid_jp_starts)
            current_phrase_str = chosen_entry['hira']
            current_phrase_display_form = chosen_entry.get('kanji', current_phrase_str)

            linking_mora_jp = utils.get_shiritori_linking_mora_from_previous_word(current_phrase_str)
            if not linking_mora_jp:
                await send_response("⚠️ Lỗi xử lý từ bắt đầu Tiếng Nhật của Bot."); return
            word_to_match_next = linking_mora_jp
            game_start_embed.description = f"{bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã chọn: **{current_phrase_display_form}** (`{current_phrase_str}`)\n\n🔗 Tiếp theo: **{word_to_match_next}**"

    else: # User provided start_phrase_input
        start_phrase_input_cleaned = start_phrase_input.strip()
        if game_lang_for_channel == "VN":
            game_author_name = f"{bot_cfg.GAME_VN_ICON} Nối Từ Tiếng Việt"
            temp_words = utils.get_words_from_input(start_phrase_input_cleaned)
            if len(temp_words) != 2:
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned}**\" phải có **đúng 2 chữ** (Tiếng Việt)."); return

            phrase_to_check_vn = f"{temp_words[0]} {temp_words[1]}"
            if not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                phrase_to_check_vn, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
            ):
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned.title()}**\" không hợp lệ theo từ điển VN."); return

            current_phrase_str = phrase_to_check_vn
            word_to_match_next = temp_words[1]
            current_phrase_display_form = " ".join(w.capitalize() for w in temp_words)
            game_start_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} bắt đầu với: **{current_phrase_display_form}**\n\n🔗 Tiếp theo: **{word_to_match_next.capitalize()}**"

        else: # JP game, user providing word
            game_author_name = f"{bot_cfg.GAME_JP_ICON} Shiritori (しりとり)"
            if not bot.kakasi:
                 await send_response("⚠️ Lỗi: Không thể xử lý từ Tiếng Nhật do thiếu thư viện trên bot."); return

            is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
                start_phrase_input_cleaned, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
            )
            if not is_valid_jp or not hira_form_jp:
                await send_response(f"⚠️ Từ \"**{start_phrase_input_cleaned}**\" không hợp lệ theo từ điển JP."); return

            if hira_form_jp.endswith('ん'):
                await send_response(f"⚠️ Từ bắt đầu \"**{start_phrase_input_cleaned}**\" (`{hira_form_jp}`) kết thúc bằng 'ん'. Vui lòng chọn từ khác."); return

            current_phrase_str = hira_form_jp
            current_phrase_display_form = start_phrase_input_cleaned

            linking_mora_jp = utils.get_shiritori_linking_mora_from_previous_word(current_phrase_str)
            if not linking_mora_jp:
                await send_response(f"⚠️ Lỗi xử lý từ \"**{start_phrase_input_cleaned}**\"."); return
            word_to_match_next = linking_mora_jp
            game_start_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} bắt đầu với: **{current_phrase_display_form}** (`{current_phrase_str}`)\n\n🔗 Tiếp theo: **{word_to_match_next}**"

        if player_id_for_first_move != bot.user.id:
             participants_since_start.add(player_id_for_first_move)

    game_start_embed.set_author(name=game_author_name, icon_url=game_author_icon_url)
    game_start_embed.set_footer(text=f"Kênh: #{channel.name} | Server: {channel.guild.name}")

    target_for_start_message = interaction if interaction else channel
    sent_game_start_message = await utils._send_message_smart(target_for_start_message, embed=game_start_embed, ephemeral=False)

    if not sent_game_start_message:
        print(f"Lỗi nghiêm trọng: Không thể gửi tin nhắn bắt đầu game cho kênh {channel.id}")
        if channel.id in bot.active_games:
            del bot.active_games[channel.id]
        return

    bot.active_games[channel.id] = {
        "game_language": game_lang_for_channel,
        "current_phrase_str": current_phrase_str,
        "current_phrase_display_form": current_phrase_display_form,
        "word_to_match_next": word_to_match_next,
        "used_phrases": {current_phrase_str},
        "last_player_id": player_id_for_first_move,
        "active": True,
        "last_correct_message_id": sent_game_start_message.id,
        "timeout_task": None,
        "participants_since_start": participants_since_start,
        "timeout_can_be_activated": len(participants_since_start) >= min_p,
        "guild_id": guild_id,
        "min_players_for_timeout": min_p,
        "timeout_seconds": timeout_s
    }

    game_state = bot.active_games[channel.id]

    if game_state["timeout_can_be_activated"] and player_id_for_first_move != bot.user.id:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(
                bot, channel.id, guild_id,
                game_state["last_player_id"],
                game_state["current_phrase_str"],
                game_state["game_language"]
            )
        )
        game_state["timeout_task"] = new_timeout_task


async def internal_stop_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member,
                             guild_id: int, interaction: discord.Interaction = None):

    if interaction and not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=False)
        except discord.HTTPException as e:
            print(f"Warning: Failed to defer interaction in internal_stop_game: {e}")

    if channel.id in bot.active_games:
        game_to_stop = bot.active_games.pop(channel.id)

        if "timeout_task" in game_to_stop and game_to_stop["timeout_task"] and not game_to_stop["timeout_task"].done():
            game_to_stop["timeout_task"].cancel()

        current_game_lang = game_to_stop.get("game_language", "VN")
        if game_to_stop.get("active") and game_to_stop.get("last_player_id") != bot.user.id:
            last_player_id = game_to_stop.get("last_player_id")
            last_player_guild_id = game_to_stop.get("guild_id", guild_id)
            if last_player_id and last_player_guild_id and bot.db_pool:
                 await database.reset_win_streak_for_user(bot.db_pool, last_player_id, last_player_guild_id, game_language=current_game_lang)

        game_lang_stopped_name = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if current_game_lang == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"

        stop_embed = discord.Embed(
            title=f"{bot_cfg.STOP_ICON} Game Đã Dừng {bot_cfg.STOP_ICON}",
            description=f"Game Nối Từ ({game_lang_stopped_name}) trong kênh {channel.mention} đã được {bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} dừng lại.",
            color=bot_cfg.EMBED_COLOR_STOP
        )
        if author.display_avatar:
            stop_embed.set_thumbnail(url=author.display_avatar.url)
        stop_embed.set_footer(text=f"Kênh: #{channel.name} | Server: {channel.guild.name}")


        guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
        prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

        view = PostGameView(
            channel=channel,
            original_starter_id=author.id,
            command_prefix_for_guild=prefix,
            bot_instance=bot,
            internal_start_game_callable=internal_start_game
        )

        target_for_stop_message = interaction if interaction else channel
        msg_to_set_view = await utils._send_message_smart(target_for_stop_message, embed=stop_embed, view=view, ephemeral=False)

        if msg_to_set_view:
            view.message_to_edit = msg_to_set_view
            if channel.guild:
                await utils.send_random_guild_emoji_if_any(channel, channel.guild)


    else:
        msg_content = "🤷 Hiện không có game Nối Từ nào đang diễn ra trong kênh này."
        target_for_no_game_message = interaction if interaction else channel
        await utils._send_message_smart(target_for_no_game_message, content=msg_content, ephemeral=True)


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
    game_lang = game_state.get("game_language", "VN").upper()

    if game_lang == "JP" and not bot.kakasi:
        print(f"WARNING: Kakasi ko sẵn sàng cho game JP ở kênh {channel_id}, game {game_state.get('game_language')}")
        return

    if game_state.get("guild_id") != guild_id:
        print(f"Lỗi: Game state kênh {channel_id} có guild_id {game_state.get('guild_id')} ko khớp {guild_id}.")
        if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
            game_state["timeout_task"].cancel()
        del bot.active_games[channel_id]
        return

    user_input_original_str = message.content.strip()
    if not user_input_original_str: return

    phrase_to_validate: str = ""
    display_form_for_current_move: str = user_input_original_str

    expected_linking_mora = game_state["word_to_match_next"] # Đổi tên biến cho rõ ràng

    error_occurred = False
    error_type_for_stat = None

    if game_lang == "VN":
        user_phrase_words_lower = utils.get_words_from_input(user_input_original_str)
        if len(user_phrase_words_lower) != 2:
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
                await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "wrong_turn", current_player_name, game_language=game_lang)
            except (discord.Forbidden, discord.HTTPException): pass
            return

        word1_user, word2_user = user_phrase_words_lower[0], user_phrase_words_lower[1]
        phrase_to_validate = f"{word1_user} {word2_user}"
        display_form_for_current_move = " ".join(w.capitalize() for w in user_phrase_words_lower)

        if word1_user != expected_linking_mora: # So sánh với âm tiết nối mong đợi
            error_occurred = True; error_type_for_stat = "wrong_word_link"

        if not error_occurred and not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
            phrase_to_validate, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
        ):
            error_occurred = True; error_type_for_stat = "invalid_wiktionary"

    else: # JP game
        is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
            user_input_original_str, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
        )

        if hira_form_jp is None and not is_valid_jp:
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
                await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "wrong_turn", current_player_name, game_language=game_lang)
            except (discord.Forbidden, discord.HTTPException): pass
            return

        if not is_valid_jp:
             error_occurred = True
             error_type_for_stat = "invalid_wiktionary"

        if not error_occurred and is_valid_jp:
            if not hira_form_jp:
                print(f"LOGIC_ERROR: is_valid_jp=True nhưng hira_form_jp is None cho input '{user_input_original_str}'")
                error_occurred = True; error_type_for_stat = "internal_error"
            else:
                phrase_to_validate = hira_form_jp

                first_mora_current = utils.get_first_mora_of_current_word(phrase_to_validate)
                if not first_mora_current or first_mora_current != expected_linking_mora:
                    error_occurred = True
                    error_type_for_stat = "wrong_word_link"

                if not error_occurred and phrase_to_validate.endswith('ん'):
                    try: await message.add_reaction(bot_cfg.SHIRITORI_LOSS_REACTION)
                    except (discord.Forbidden, discord.HTTPException): pass

                    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
                        game_state["timeout_task"].cancel()

                    winner_id = game_state["last_player_id"]
                    loser_id = current_player_id

                    await database.update_stat(bot.db_pool, bot.user.id, loser_id, guild_id, "lost_by_n_ending", current_player_name, game_language=game_lang)
                    await database.reset_win_streak_for_user(bot.db_pool, loser_id, guild_id, game_language=game_lang)

                    loss_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_LOSS)
                    original_starter_for_view = winner_id

                    if winner_id == bot.user.id:
                        loss_embed.title = f"{bot_cfg.PLAYER_LOSS_ICON} {message.author.name} Thua Cuộc! {bot_cfg.PLAYER_LOSS_ICON}"
                        loss_embed.description = (
                            f"{message.author.mention} đã dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'!\n"
                            f"Theo luật Shiritori, {bot_cfg.BOT_PLAYER_START_EMOJI} Bot (người chơi trước) chiến thắng!"
                        )
                        if bot.user.display_avatar: loss_embed.set_thumbnail(url=bot.user.display_avatar.url)
                    else:
                        try:
                            winner_user = await bot.fetch_user(winner_id)
                            winner_name_display = winner_user.name

                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display, game_language=game_lang)

                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Chúc Mừng {discord.utils.escape_markdown(winner_name_display)}! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = (
                                f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} đã dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'.\n"
                                f"Theo luật Shiritori, {bot_cfg.USER_PLAYER_START_EMOJI} {winner_user.mention} (người chơi trước) chiến thắng!"
                            )
                            if winner_user.display_avatar: loss_embed.set_thumbnail(url=winner_user.display_avatar.url)

                            user_stats_db = await database.get_user_stats_entry(bot.db_pool, winner_id, guild_id, game_lang, winner_name_display)
                            if user_stats_db:
                                 stats_text = (
                                     f"🏅 Tổng thắng: **{user_stats_db['wins']}**\n"
                                     f"🔥 Chuỗi thắng hiện tại: **{user_stats_db['current_win_streak']}** (Max: **{user_stats_db['max_win_streak']}**)"
                                 )
                                 loss_embed.add_field(name="Thành Tích Người Thắng", value=stats_text, inline=False)

                        except discord.NotFound:
                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}", game_language=game_lang)
                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Người Chơi ID {winner_id} Thắng Cuộc! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} thua do dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'."
                        except discord.HTTPException:
                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)", game_language=game_lang)
                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Một Người Chơi Thắng! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} thua do dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'. (Lỗi lấy thông tin người thắng)."

                    loss_embed.set_footer(text=f"Luật 'ん' Shiritori | Kênh: #{message.channel.name}")
                    guild_cfg_for_prefix_db = await database.get_guild_config(bot.db_pool, guild_id)
                    command_prefix_for_guild_val = guild_cfg_for_prefix_db.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_for_prefix_db else bot_cfg.DEFAULT_COMMAND_PREFIX

                    view_instance = PostGameView(
                        channel=message.channel,
                        original_starter_id=original_starter_for_view,
                        command_prefix_for_guild=command_prefix_for_guild_val,
                        bot_instance=bot,
                        internal_start_game_callable=internal_start_game
                    )
                    msg_with_view_instance = await message.channel.send(embed=loss_embed, view=view_instance)
                    if msg_with_view_instance :
                        view_instance.message_to_edit = msg_with_view_instance
                        if message.guild:
                           await utils.send_random_guild_emoji_if_any(message.channel, message.guild)

                    if channel_id in bot.active_games:
                        del bot.active_games[channel_id]
                    return

    if not error_occurred and phrase_to_validate and phrase_to_validate in game_state["used_phrases"]:
        error_occurred = True; error_type_for_stat = "used_word_error"

    if error_occurred:
        try: await message.add_reaction(bot_cfg.ERROR_REACTION)
        except (discord.Forbidden, discord.HTTPException): pass
        if error_type_for_stat:
            await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, error_type_for_stat, current_player_name, game_language=game_lang)
        return

    if not phrase_to_validate and game_lang == "JP":
        if hira_form_jp and is_valid_jp:
             phrase_to_validate = hira_form_jp
        else:
            if not is_valid_jp: return
            print(f"LOGIC_WARN: JP move, not error, but phrase_to_validate empty. Input: {user_input_original_str}, Hira: {hira_form_jp}, Valid: {is_valid_jp}")
            return


    try: await message.add_reaction(bot_cfg.CORRECT_REACTION)
    except (discord.Forbidden, discord.HTTPException): pass
    await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "correct_moves", current_player_name, game_language=game_lang)

    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
        game_state["timeout_task"].cancel()

    game_state["current_phrase_str"] = phrase_to_validate
    game_state["current_phrase_display_form"] = display_form_for_current_move

    if game_lang == "VN":
        game_state["word_to_match_next"] = phrase_to_validate.split()[1]
    else: # JP
        linking_mora_jp_current = utils.get_shiritori_linking_mora_from_previous_word(phrase_to_validate)
        if not linking_mora_jp_current:
            print(f"LỖI NGHIÊM TRỌNG: Không thể lấy âm tiết nối của từ JP hợp lệ: {phrase_to_validate}")
            await message.channel.send(f"⚠️ Bot gặp lỗi xử lý từ \"{display_form_for_current_move}\". Lượt này có thể không được tính đúng.")
            return
        else:
            game_state["word_to_match_next"] = linking_mora_jp_current

    game_state["used_phrases"].add(phrase_to_validate)
    game_state["last_player_id"] = current_player_id
    game_state["last_correct_message_id"] = message.id

    if current_player_id != bot.user.id:
        game_state["participants_since_start"].add(current_player_id)

    timeout_s_config = game_state.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS)
    min_p_config = game_state.get("min_players_for_timeout", bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT)

    if not game_state["timeout_can_be_activated"] and \
       len(game_state["participants_since_start"]) >= min_p_config:
        game_state["timeout_can_be_activated"] = True
        if msg_channel := bot.get_channel(channel_id):
            try:
                await msg_channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi ({min_p_config} tối thiểu). "
                    f"Timeout {timeout_s_config} giây sẽ áp dụng.",
                    delete_after=20
                )
            except discord.HTTPException: pass

    if game_state["timeout_can_be_activated"]:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(
                bot, channel_id, guild_id,
                game_state["last_player_id"], game_state["current_phrase_str"],
                game_lang
            )
        )
        game_state["timeout_task"] = new_timeout_task