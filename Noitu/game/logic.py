# Noitu/game/logic.py
import discord
from discord.ext import commands
import random
import asyncio
import traceback # Đảm bảo traceback đã được import

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

    # xd tu hien thi va romaji info cho JP
    game_state_details = bot.active_games.get(channel_id) # lay state game hien tai

    displayed_word_for_countdown = ""
    romaji_info_for_countdown = ""

    if game_lang == "VN":
        displayed_word_for_countdown = expected_phrase_normalized.title()
    elif game_lang == "JP":
        if game_state_details:
            # dung display_form goc (kanji/kana/roma ma nd nhap) neu co, ko thi dung hira
            displayed_word_for_countdown = game_state_details.get("current_phrase_display_form", expected_phrase_normalized)
        else:
            displayed_word_for_countdown = expected_phrase_normalized # fallback ve hira neu state game ko tim thay

        # luon cv hira (expected_phrase_normalized) sang romaji
        if bot.kakasi and expected_phrase_normalized:
            try:
                conversion_result = bot.kakasi.convert(expected_phrase_normalized)
                if conversion_result:
                    # lay phan 'hepburn' (romaji) tu kq cv
                    romaji_parts = [item['hepburn'] for item in conversion_result if 'hepburn' in item and item['hepburn']]
                    full_romaji = "".join(romaji_parts).strip()
                    if full_romaji:
                        # chi them "(romaji: ...)" neu tu hien thi ko phai la romaji do roi
                        if displayed_word_for_countdown.strip().lower() != full_romaji.strip().lower():
                            romaji_info_for_countdown = f" (romaji: {full_romaji})"
                        # nguoc lai: tu hien thi da la romaji, ko can them
            except Exception as e_kks:
                print(f"Loi pykakasi khi cv romaji cho '{expected_phrase_normalized}' trong countdown: {e_kks}")
                traceback.print_exc() # in chi tiet loi de debug
    else: # truong hop game_lang ko phai VN hay JP (ko nen xay ra)
        displayed_word_for_countdown = expected_phrase_normalized

    initial_countdown_text_base = ""
    if expected_last_player_id == bot.user.id:
        initial_countdown_text_base = f"⏳ {bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã ra từ \"**{displayed_word_for_countdown}**{romaji_info_for_countdown}\". "
    else:
        try:
            winner_user_to_be = await bot.fetch_user(expected_last_player_id)
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} {winner_user_to_be.mention} đã ra từ \"**{displayed_word_for_countdown}**{romaji_info_for_countdown}\". "
        except discord.NotFound:
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} Người chơi ID {expected_last_player_id} đã ra từ \"**{displayed_word_for_countdown}**{romaji_info_for_countdown}\". "
        except discord.HTTPException:
            initial_countdown_text_base = f"⏳ {bot_cfg.USER_PLAYER_START_EMOJI} Một người chơi đã ra từ \"**{displayed_word_for_countdown}**{romaji_info_for_countdown}\". "

    try:
        countdown_message = await message_channel.send(f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {timeout_seconds_for_guild} giây.")
    except discord.HTTPException as e:
        print(f"Lỗi gửi msg đếm ngược: {e}")
        countdown_message = None

    time_slept = 0
    edit_interval = 1 # giay

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
                    game.get("current_phrase_str") == expected_phrase_normalized): # tu da thay doi
                if countdown_message:
                    try: await countdown_message.delete()
                    except (discord.NotFound, discord.HTTPException): pass
                return

            if countdown_message:
                remaining_time = max(0, timeout_seconds_for_guild - time_slept)
                new_text = f"{initial_countdown_text_base}Thời gian cho người tiếp theo: {remaining_time} giây."
                if remaining_time > 0 : # chi edit neu con thoi gian
                    try: await countdown_message.edit(content=new_text)
                    except (discord.NotFound, discord.HTTPException): countdown_message = None # msg da bi xoa hoac loi

            if time_slept >= timeout_seconds_for_guild: break # het gio

        if countdown_message: # xoa msg dem nguoc sau khi vong lap ket thuc
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass

        # ktra lai game state truoc khi cong bo thang
        if channel_id in bot.active_games and bot.active_games[channel_id]["active"]:
            game = bot.active_games[channel_id]
            if game.get("last_player_id") == expected_last_player_id and \
               game.get("current_phrase_str") == expected_phrase_normalized: # van la tu do, nguoi do thang

                winner_id = game["last_player_id"]
                current_game_lang = game.get("game_language", "VN") # mac dinh VN neu ko co

                # su dung displayed_word_for_countdown va romaji_info_for_countdown cho tin nhan thang cuoc
                winning_phrase_final_display = displayed_word_for_countdown
                if game_lang == "JP" and romaji_info_for_countdown: # them romaji neu co
                    winning_phrase_final_display += romaji_info_for_countdown
                elif game_lang == "VN": # VN thi title() la du
                     winning_phrase_final_display = expected_phrase_normalized.title()


                win_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_WIN)
                original_starter_for_view = winner_id # de nut "choi lai" biet ai start
                game_lang_display = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if current_game_lang == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"

                if winner_id == bot.user.id: # bot thang
                    win_embed.title = f"{bot_cfg.TIMEOUT_WIN_ICON} Hết Giờ! Không Ai Nối Từ Của Bot {bot_cfg.TIMEOUT_WIN_ICON}"
                    win_embed.description = (
                        f"Đã hết **{timeout_seconds_for_guild} giây**! Không ai nối được từ \"**{winning_phrase_final_display}**\" của {bot_cfg.BOT_PLAYER_START_EMOJI} Bot.\n"
                        f"Game Nối Từ ({game_lang_display}) kết thúc không có người thắng."
                    )
                    participants_list = list(game.get("participants_since_start", []))
                    original_starter_for_view = participants_list[0] if participants_list else bot.user.id
                    if bot.user.display_avatar: win_embed.set_thumbnail(url=bot.user.display_avatar.url)
                else: # nd thang
                    winner_name_display = f"User ID {winner_id}" # fallback
                    winner_user_obj = None
                    try:
                        winner_user_obj = await bot.fetch_user(winner_id)
                        winner_name_display = winner_user_obj.name
                        if winner_user_obj.display_avatar: win_embed.set_thumbnail(url=winner_user_obj.display_avatar.url)

                        # cap nhat DB
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display, game_language=current_game_lang)
                        # reset streak cua nhung nguoi khac trong game
                        for pid in game.get("participants_since_start", set()):
                            if pid != winner_id and pid != bot.user.id: # ko reset cho nguoi thang & bot
                                await database.reset_win_streak_for_user(bot.db_pool, pid, guild_id, game_language=current_game_lang)

                        win_embed.title = f"{bot_cfg.WIN_ICON} {discord.utils.escape_markdown(winner_name_display)} Chiến Thắng! {bot_cfg.WIN_ICON}"
                        win_embed.description = (
                            f"{winner_user_obj.mention} đã chiến thắng game Nối Từ ({game_lang_display})!\n"
                            f"Không ai nối tiếp được từ \"**{winning_phrase_final_display}**\" của bạn trong **{timeout_seconds_for_guild} giây**."
                        )
                        # hien thi them stats cua nguoi thang
                        user_stats = await database.get_user_stats_entry(bot.db_pool, winner_id, guild_id, current_game_lang, winner_name_display)
                        if user_stats:
                             stats_text = (
                                 f"🏅 Tổng thắng: **{user_stats['wins']}**\n"
                                 f"🔥 Chuỗi thắng hiện tại: **{user_stats['current_win_streak']}** (Max: **{user_stats['max_win_streak']}**)"
                             )
                             win_embed.add_field(name="Thành Tích Cá Nhân", value=stats_text, inline=False)
                        original_starter_for_view = winner_id
                    except discord.NotFound: # ko tim thay user
                        await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}", game_language=current_game_lang)
                        win_embed.title = f"{bot_cfg.WIN_ICON} Người Chơi ID {winner_id} Thắng Cuộc! {bot_cfg.WIN_ICON}"
                        win_embed.description = f"Người chơi ID {winner_id} đã thắng game ({game_lang_display}) với từ \"**{winning_phrase_final_display}**\"! (Không thể lấy thông tin chi tiết)."
                    except discord.HTTPException: # loi API khac
                         await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)", game_language=current_game_lang)
                         win_embed.title = f"{bot_cfg.WIN_ICON} Một Người Chơi Thắng! {bot_cfg.WIN_ICON}"
                         win_embed.description = f"Một người chơi đã thắng game ({game_lang_display}) với từ \"**{winning_phrase_final_display}**\"! (Lỗi khi lấy thông tin người chơi)."

                win_embed.set_footer(text=f"Kênh: #{message_channel.name} | Server: {message_channel.guild.name}")

                view = PostGameView(
                    channel=message_channel,
                    original_starter_id=original_starter_for_view,
                    command_prefix_for_guild=command_prefix_for_guild,
                    bot_instance=bot,
                    internal_start_game_callable=internal_start_game
                )
                msg_with_view = await message_channel.send(embed=win_embed, view=view)
                if msg_with_view: view.message_to_edit = msg_with_view # de view tu disable nut

                # gui them emoji neu server co
                if message_channel.guild:
                    await utils.send_random_guild_emoji_if_any(message_channel, message_channel.guild)

                # xoa game khoi active_games sau khi da xu ly xong
                if channel_id in bot.active_games and \
                   bot.active_games[channel_id].get("last_player_id") == expected_last_player_id and \
                   bot.active_games[channel_id].get("current_phrase_str") == expected_phrase_normalized:
                    del bot.active_games[channel_id]

    except asyncio.CancelledError: # task bi huy (do game stop hoac co nguoi noi tiep)
        if countdown_message:
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass
        # ko lam gi them, task da duoc cancel la dung
    except Exception as e:
        print(f"Lỗi nghiêm trọng trong check_game_timeout cho kênh {channel_id} (từ: {expected_phrase_normalized}): {e}")
        traceback.print_exc()
        if countdown_message: # co gang xoa msg dem nguoc neu co loi
            try: await countdown_message.delete()
            except (discord.NotFound, discord.HTTPException): pass
        # co the can reset game state o day neu loi qua nghiem trong


async def internal_start_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member,
                              guild_id: int, start_phrase_input: str = None, interaction: discord.Interaction = None):

    # ham noi bo de gui phan hoi, uu tien interaction
    async def send_response(msg_content: str, ephemeral_flag: bool = True, embed=None):
        target = interaction if interaction else commands.Context(message=None, bot=bot, view=None, prefix=None) # tao target ao
        if interaction: # neu co interaction that, dung no
            target = interaction
        elif hasattr(channel, 'last_message') and channel.last_message: # neu la lenh prefix, tao context tu msg cuoi
             mock_msg = await channel.fetch_message(channel.last_message_id) if channel.last_message_id else None
             if mock_msg:
                target = await bot.get_context(mock_msg)
                target.author = author # gan author dung
             else: # ko co last_message, gui truc tiep vao channel
                await channel.send(msg_content, embed=embed, delete_after=15 if ephemeral_flag else None)
                return
        else: # ko co cach nao tao context/interaction, gui truc tiep
            await channel.send(msg_content, embed=embed, delete_after=15 if ephemeral_flag else None)
            return

        await utils._send_message_smart(target, content=msg_content, embed=embed, ephemeral=ephemeral_flag)

    # ktra cac dieu kien san sang cua bot
    if not bot.http_session or bot.http_session.closed:
        await send_response("⚠️ Bot chưa sẵn sàng (Session HTTP). Vui lòng thử lại sau giây lát.")
        return
    if not bot.db_pool:
        await send_response("⚠️ Bot chưa sẵn sàng (Kết nối Database). Vui lòng thử lại sau giây lát.")
        return

    timeout_s, min_p, game_lang_for_channel = await utils.get_channel_game_settings(bot, guild_id, channel.id)

    if not game_lang_for_channel: # kenh chua config
        await send_response(f"⚠️ Kênh này chưa được cấu hình để chơi Nối Từ. Admin có thể dùng `/config set_vn_channel` hoặc `/config set_jp_channel`.")
        return

    if game_lang_for_channel == "JP" and not bot.kakasi: # JP ma ko co kakasi
        await send_response("⚠️ Không thể bắt đầu game Tiếng Nhật do bot chưa được cấu hình đúng (PyKakasi).")
        return

    guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id)
    prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

    if channel.id in bot.active_games: # game da ton tai
        existing_game_state = bot.active_games[channel.id]
        if existing_game_state.get("active", False): # game dang active
            if "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
                existing_game_state["timeout_task"].cancel() # huy timeout task cu neu co
            current_game_lang_name = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if existing_game_state.get('game_language') == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"
            msg = f"⚠️ Một game Nối Từ ({current_game_lang_name}) đã đang diễn ra. Dùng `{prefix}stop` hoặc `/stop` để dừng."
            await send_response(msg)
            return
        elif "timeout_task" in existing_game_state and existing_game_state["timeout_task"] and not existing_game_state["timeout_task"].done():
             existing_game_state["timeout_task"].cancel() # game ko active nhung task con, huy luon

    current_phrase_str: str = "" # tu hien tai (da chuan hoa, vd: lowercase, hiragana)
    word_to_match_next: str = "" # chu/am tiet can noi tiep
    current_phrase_display_form: str = "" # tu hien tai (dang hien thi, vd: Title Case, Kanji)

    player_id_for_first_move = author.id # mac dinh la nguoi goi lenh
    participants_since_start = set() # ds nguoi choi tu luc bat dau game
    sent_game_start_message: discord.Message = None # msg thong bao game start

    # Defer interaction neu co va chua defer
    if interaction and not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=False) # game start msg la public
        except discord.HTTPException as e:
            print(f"Warning: Failed to defer interaction in internal_start_game: {e}")
            # Ko can return, co the van gui msg dc qua followup hoac channel.send

    game_start_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_GAME_START)
    game_author_name = "" # Ten game, vd: "Noi Tu Tieng Viet"
    game_author_icon_url = bot.user.display_avatar.url if bot.user and bot.user.display_avatar else None

    if not start_phrase_input: # Bot chon tu
        player_id_for_first_move = bot.user.id # Bot di dau
        if game_lang_for_channel == "VN":
            game_author_name = f"{bot_cfg.GAME_VN_ICON} Nối Từ Tiếng Việt"
            chosen_start_phrase_vn = ""
            
            # uu tien tu dien local
            if bot.local_dictionary_vn:
                two_word_phrases_vn = [
                    phrase for phrase in list(bot.local_dictionary_vn) # chuyen set -> list de shuffle
                    if len(phrase.split()) == 2 # chi lay cum 2 chu
                ]
                if two_word_phrases_vn: # ktra neu co cum 2 chu
                    random.shuffle(two_word_phrases_vn)
                    # ko check Wiktionary lai neu tu dien local duoc coi la dang tin
                    chosen_start_phrase_vn = two_word_phrases_vn[0] 
            
            if not chosen_start_phrase_vn: # fallback neu ko tim dc tu file hoac file rong/ko co cum 2 tu
                possible_starts_vn_fallback = ["bầu trời", "dòng sông", "học sinh", "sinh viên", "nhà cửa", "tình yêu", "hạnh phúc"]
                random.shuffle(possible_starts_vn_fallback)
                for phrase_attempt_fallback in possible_starts_vn_fallback:
                     # ktra lai qua API de dam bao
                     if await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                        phrase_attempt_fallback, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
                    ):
                        chosen_start_phrase_vn = phrase_attempt_fallback
                        break # tim dc roi thi thoi
            
            if not chosen_start_phrase_vn: # neu ca file va fallback deu ko duoc
                await send_response("⚠️ Bot không tìm được từ bắt đầu Tiếng Việt ngẫu nhiên hợp lệ từ từ điển."); return

            current_phrase_str = chosen_start_phrase_vn.lower() # luu lowercase
            current_phrase_words = current_phrase_str.split()
            if len(current_phrase_words) != 2: # double check, du phong
                await send_response("⚠️ Bot chọn từ bắt đầu không hợp lệ (không phải 2 chữ). Vui lòng thử lại."); return

            word_to_match_next = current_phrase_words[1] # chu thu 2 de noi tiep
            current_phrase_display_form = " ".join(word.capitalize() for word in current_phrase_words) # hien thi Title Case
            game_start_embed.description = f"{bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã chọn: **{current_phrase_display_form}**\n\n🔗 Tiếp theo: **{word_to_match_next.capitalize()}**"

        else: # JP game, bot chon tu
            game_author_name = f"{bot_cfg.GAME_JP_ICON} Shiritori (しりとり)"
            if not bot.local_dictionary_jp: # ko co tu dien JP
                await send_response("⚠️ Bot không có từ điển Tiếng Nhật để chọn từ bắt đầu."); return

            # loc cac tu ko ket thuc bang 'ん'
            valid_jp_starts = [
                entry for entry in bot.local_dictionary_jp
                if entry.get('hira') and not entry['hira'].endswith('ん')
            ]
            if not valid_jp_starts: # neu ko co tu ko ket thuc bang 'ん', lay bat ky tu nao (it xay ra)
                valid_jp_starts = [entry for entry in bot.local_dictionary_jp if entry.get('hira')]

            if not valid_jp_starts: # van ko co
                 await send_response("⚠️ Bot không tìm được từ Tiếng Nhật ngẫu nhiên hợp lệ từ từ điển."); return

            chosen_entry = random.choice(valid_jp_starts)
            current_phrase_str = chosen_entry['hira'] # luu hira
            current_phrase_display_form = chosen_entry.get('kanji', current_phrase_str) # hien thi kanji neu co, ko thi hira

            linking_mora_jp = utils.get_shiritori_linking_mora_from_previous_word(current_phrase_str)
            if not linking_mora_jp: # loi xu ly am tiet
                await send_response("⚠️ Lỗi xử lý từ bắt đầu Tiếng Nhật của Bot."); return
            word_to_match_next = linking_mora_jp
            game_start_embed.description = f"{bot_cfg.BOT_PLAYER_START_EMOJI} Bot đã chọn: **{current_phrase_display_form}** (`{current_phrase_str}`)\n\n🔗 Tiếp theo: **{word_to_match_next}**"

    else: # Nd cung cap tu bat dau
        start_phrase_input_cleaned = start_phrase_input.strip()
        if game_lang_for_channel == "VN":
            game_author_name = f"{bot_cfg.GAME_VN_ICON} Nối Từ Tiếng Việt"
            temp_words = utils.get_words_from_input(start_phrase_input_cleaned) # lay cac chu, lowercase
            if len(temp_words) != 2:
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned}**\" phải có **đúng 2 chữ** (Tiếng Việt)."); return

            phrase_to_check_vn = f"{temp_words[0]} {temp_words[1]}" # tao lai cum tu chuan
            # ktra tinh hop le
            if not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
                phrase_to_check_vn, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
            ):
                await send_response(f"⚠️ Cụm từ \"**{start_phrase_input_cleaned.title()}**\" không hợp lệ theo từ điển VN."); return

            current_phrase_str = phrase_to_check_vn # da la lowercase
            word_to_match_next = temp_words[1]
            current_phrase_display_form = " ".join(w.capitalize() for w in temp_words)
            game_start_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} bắt đầu với: **{current_phrase_display_form}**\n\n🔗 Tiếp theo: **{word_to_match_next.capitalize()}**"

        else: # JP game, nd cung cap tu
            game_author_name = f"{bot_cfg.GAME_JP_ICON} Shiritori (しりとり)"
            if not bot.kakasi: # can kakasi de xu ly
                 await send_response("⚠️ Lỗi: Không thể xử lý từ Tiếng Nhật do thiếu thư viện trên bot."); return

            # ktra tinh hop le, tra ve (is_valid, hiragana_form)
            is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
                start_phrase_input_cleaned, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
            )
            if not is_valid_jp or not hira_form_jp: # ko hop le hoac ko co hira form
                await send_response(f"⚠️ Từ \"**{start_phrase_input_cleaned}**\" không hợp lệ theo từ điển JP."); return

            if hira_form_jp.endswith('ん'): # ko dc bat dau bang tu ket thuc 'ん'
                await send_response(f"⚠️ Từ bắt đầu \"**{start_phrase_input_cleaned}**\" (`{hira_form_jp}`) kết thúc bằng 'ん'. Vui lòng chọn từ khác."); return

            current_phrase_str = hira_form_jp # luu hira form
            current_phrase_display_form = start_phrase_input_cleaned # hien thi input goc cua nd

            linking_mora_jp = utils.get_shiritori_linking_mora_from_previous_word(current_phrase_str)
            if not linking_mora_jp:
                await send_response(f"⚠️ Lỗi xử lý từ \"**{start_phrase_input_cleaned}**\"."); return
            word_to_match_next = linking_mora_jp
            game_start_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} bắt đầu với: **{current_phrase_display_form}** (`{current_phrase_str}`)\n\n🔗 Tiếp theo: **{word_to_match_next}**"

        # them nd vao ds participants neu nd bat dau
        if player_id_for_first_move != bot.user.id:
             participants_since_start.add(player_id_for_first_move)

    game_start_embed.set_author(name=game_author_name, icon_url=game_author_icon_url)
    game_start_embed.set_footer(text=f"Kênh: #{channel.name} | Server: {channel.guild.name}")

    # gui msg bat dau game
    target_for_start_message = interaction if interaction else channel # uu tien interaction
    sent_game_start_message = await utils._send_message_smart(target_for_start_message, embed=game_start_embed, ephemeral=False)

    if not sent_game_start_message: # ko gui dc msg -> ko the bat dau game
        print(f"Lỗi nghiêm trọng: Không thể gửi tin nhắn bắt đầu game cho kênh {channel.id}")
        if channel.id in bot.active_games: # don dep neu co state rac
            del bot.active_games[channel.id]
        return

    # luu state game
    bot.active_games[channel.id] = {
        "game_language": game_lang_for_channel,
        "current_phrase_str": current_phrase_str,
        "current_phrase_display_form": current_phrase_display_form,
        "word_to_match_next": word_to_match_next,
        "used_phrases": {current_phrase_str}, # them tu dau tien vao ds da dung
        "last_player_id": player_id_for_first_move,
        "active": True,
        "last_correct_message_id": sent_game_start_message.id, # msg hop le cuoi cung
        "timeout_task": None, # task de theo doi timeout
        "participants_since_start": participants_since_start,
        "timeout_can_be_activated": len(participants_since_start) >= min_p, # timeout kich hoat neu du ng choi
        "guild_id": guild_id,
        "min_players_for_timeout": min_p, # luu lai config tai thoi diem game start
        "timeout_seconds": timeout_s
    }

    game_state = bot.active_games[channel.id] # lay lai state vua tao

    # kich hoat timeout neu du dk va ko phai bot start
    if game_state["timeout_can_be_activated"] and player_id_for_first_move != bot.user.id:
        new_timeout_task = asyncio.create_task(
            check_game_timeout( # goi ham check timeout
                bot, channel.id, guild_id,
                game_state["last_player_id"],
                game_state["current_phrase_str"],
                game_state["game_language"]
            )
        )
        game_state["timeout_task"] = new_timeout_task # luu task vao state


async def internal_stop_game(bot: commands.Bot, channel: discord.TextChannel, author: discord.User | discord.Member,
                             guild_id: int, interaction: discord.Interaction = None):

    # Defer interaction neu co
    if interaction and not interaction.response.is_done():
        try:
            await interaction.response.defer(ephemeral=False) # msg stop la public
        except discord.HTTPException as e:
            print(f"Warning: Failed to defer interaction in internal_stop_game: {e}")

    if channel.id in bot.active_games: # game co ton tai de stop
        game_to_stop = bot.active_games.pop(channel.id) # lay ra va xoa khoi dict

        # huy timeout task neu co
        if "timeout_task" in game_to_stop and game_to_stop["timeout_task"] and not game_to_stop["timeout_task"].done():
            game_to_stop["timeout_task"].cancel()

        current_game_lang = game_to_stop.get("game_language", "VN")
        # neu game dang active va nguoi choi cuoi cung ko phai bot, reset streak cua ho
        if game_to_stop.get("active") and game_to_stop.get("last_player_id") != bot.user.id:
            last_player_id = game_to_stop.get("last_player_id")
            last_player_guild_id = game_to_stop.get("guild_id", guild_id) # lay guild_id tu game state
            if last_player_id and last_player_guild_id and bot.db_pool: # dam bao co du ttin
                 await database.reset_win_streak_for_user(bot.db_pool, last_player_id, last_player_guild_id, game_language=current_game_lang)

        game_lang_stopped_name = f"{bot_cfg.GAME_VN_ICON} Tiếng Việt" if current_game_lang == "VN" else f"{bot_cfg.GAME_JP_ICON} Tiếng Nhật"

        stop_embed = discord.Embed(
            title=f"{bot_cfg.STOP_ICON} Game Đã Dừng {bot_cfg.STOP_ICON}",
            description=f"Game Nối Từ ({game_lang_stopped_name}) trong kênh {channel.mention} đã được {bot_cfg.USER_PLAYER_START_EMOJI} {author.mention} dừng lại.",
            color=bot_cfg.EMBED_COLOR_STOP
        )
        if author.display_avatar: # them avatar nguoi stop
            stop_embed.set_thumbnail(url=author.display_avatar.url)
        stop_embed.set_footer(text=f"Kênh: #{channel.name} | Server: {channel.guild.name}")


        guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id) # lay prefix cho nut
        prefix = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

        # them nut "Choi Lai" va "Xem BXH"
        view = PostGameView(
            channel=channel,
            original_starter_id=author.id, # nguoi stop co the choi lai
            command_prefix_for_guild=prefix,
            bot_instance=bot,
            internal_start_game_callable=internal_start_game
        )

        target_for_stop_message = interaction if interaction else channel # uu tien interaction
        msg_to_set_view = await utils._send_message_smart(target_for_stop_message, embed=stop_embed, view=view, ephemeral=False)

        if msg_to_set_view:
            view.message_to_edit = msg_to_set_view # de view tu disable nut
            if channel.guild: # gui emoji neu co
                await utils.send_random_guild_emoji_if_any(channel, channel.guild)


    else: # ko co game nao dang dien ra
        msg_content = "🤷 Hiện không có game Nối Từ nào đang diễn ra trong kênh này."
        target_for_no_game_message = interaction if interaction else channel
        await utils._send_message_smart(target_for_no_game_message, content=msg_content, ephemeral=True)


async def process_game_message(bot: commands.Bot, message: discord.Message): # xu ly tin nhan game
    channel_id = message.channel.id
    guild_id = message.guild.id

    # ktra bot san sang
    if not bot.http_session or bot.http_session.closed: return
    if not bot.db_pool: return

    # ktra game co active trong kenh nay ko
    if channel_id not in bot.active_games or not bot.active_games[channel_id].get("active", False):
        return

    game_state = bot.active_games[channel_id]
    current_player_id = message.author.id
    current_player_name = message.author.name
    game_lang = game_state.get("game_language", "VN").upper() # mac dinh VN

    # ktra kakasi neu la game JP
    if game_lang == "JP" and not bot.kakasi:
        print(f"WARNING: Kakasi ko sẵn sàng cho game JP ở kênh {channel_id}, game {game_state.get('game_language')}")
        return # ko xu ly neu thieu kakasi cho game JP

    # ktra guild_id trong game state co khop ko (phong ngua loi logic)
    if game_state.get("guild_id") != guild_id:
        print(f"Lỗi: Game state kênh {channel_id} có guild_id {game_state.get('guild_id')} ko khớp {guild_id}.")
        # don dep game state loi
        if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
            game_state["timeout_task"].cancel()
        del bot.active_games[channel_id]
        return

    user_input_original_str = message.content.strip() # lay input cua nd
    if not user_input_original_str: return # bo qua msg rong

    phrase_to_validate: str = "" # tu/cum tu sau khi chuan hoa de ktra
    display_form_for_current_move: str = user_input_original_str # dang de hien thi cua luot nay

    expected_linking_mora = game_state["word_to_match_next"] # chu/am tiet can noi tiep

    error_occurred = False # co loi xay ra ko
    error_type_for_stat = None # loai loi de ghi stat

    if game_lang == "VN":
        user_phrase_words_lower = utils.get_words_from_input(user_input_original_str) # tach tu, lowercase
        if len(user_phrase_words_lower) != 2: # VN phai la 2 chu
            return # bo qua neu ko phai 2 chu, ko can bao loi vi co the la chat binh thuong

        # ktra nd co di lien tiep ko
        if current_player_id == game_state["last_player_id"]:
            try:
                await message.add_reaction(bot_cfg.WRONG_TURN_REACTION) # reaction
                guild_cfg_obj = await database.get_guild_config(bot.db_pool, guild_id) # lay prefix
                prefix_val = guild_cfg_obj.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_obj else bot_cfg.DEFAULT_COMMAND_PREFIX

                await message.channel.send(
                    f"{bot_cfg.WRONG_TURN_REACTION} {message.author.mention}, bạn vừa đi rồi! Hãy đợi người khác. "
                    f"(Dùng `{prefix_val}stop` hoặc `/stop` để dừng).",
                    delete_after=bot_cfg.DELETE_WRONG_TURN_MESSAGE_AFTER # tu dong xoa msg
                )
                await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "wrong_turn", current_player_name, game_language=game_lang)
            except (discord.Forbidden, discord.HTTPException): pass # bo qua neu ko co quyen
            return # ket thuc xu ly

        word1_user, word2_user = user_phrase_words_lower[0], user_phrase_words_lower[1]
        phrase_to_validate = f"{word1_user} {word2_user}" # cum tu da chuan hoa
        display_form_for_current_move = " ".join(w.capitalize() for w in user_phrase_words_lower) # dang Title Case

        if word1_user != expected_linking_mora: # ktra chu dau co khop ko
            error_occurred = True; error_type_for_stat = "wrong_word_link"

        # ktra Wiktionary neu chua co loi
        if not error_occurred and not await wiktionary_api.is_vietnamese_phrase_or_word_valid_api(
            phrase_to_validate, bot.http_session, bot.wiktionary_cache_vn, bot.local_dictionary_vn
        ):
            error_occurred = True; error_type_for_stat = "invalid_wiktionary"

    else: # JP game
        # ktra tinh hop le va lay hira form
        is_valid_jp, hira_form_jp = await wiktionary_api.is_japanese_word_valid_api(
            user_input_original_str, bot.http_session, bot.wiktionary_cache_jp, bot.local_dictionary_jp, bot.kakasi
        )

        # neu ca hira form la None VA is_valid_jp la False -> input ko the xu ly/ko phai tieng Nhat ro rang
        # -> bo qua, coi nhu chat bt
        if hira_form_jp is None and not is_valid_jp:
            return

        # ktra nd di lien tiep
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

        if not is_valid_jp: # neu ko hop le theo Wiktionary/local dict
             error_occurred = True
             error_type_for_stat = "invalid_wiktionary"

        if not error_occurred and is_valid_jp: # neu hop le
            if not hira_form_jp: # day la truong hop bat thuong, valid nhung ko co hira form
                print(f"LOGIC_ERROR: is_valid_jp=True nhưng hira_form_jp is None cho input '{user_input_original_str}'")
                error_occurred = True; error_type_for_stat = "internal_error" # loi noi bo
            else:
                phrase_to_validate = hira_form_jp # dung hira form de xu ly logic

                # ktra am tiet noi
                first_mora_current = utils.get_first_mora_of_current_word(phrase_to_validate)
                if not first_mora_current or first_mora_current != expected_linking_mora:
                    error_occurred = True
                    error_type_for_stat = "wrong_word_link"

                # ktra luat 'ん' (chi ktra neu chua co loi truoc do)
                if not error_occurred and phrase_to_validate.endswith('ん'):
                    try: await message.add_reaction(bot_cfg.SHIRITORI_LOSS_REACTION) # reaction thua
                    except (discord.Forbidden, discord.HTTPException): pass

                    # huy timeout task cua nguoi choi truoc
                    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
                        game_state["timeout_task"].cancel()

                    winner_id = game_state["last_player_id"] # nguoi choi truoc thang
                    loser_id = current_player_id # nguoi choi hien tai thua

                    # cap nhat stat cho nguoi thua
                    await database.update_stat(bot.db_pool, bot.user.id, loser_id, guild_id, "lost_by_n_ending", current_player_name, game_language=game_lang)
                    await database.reset_win_streak_for_user(bot.db_pool, loser_id, guild_id, game_language=game_lang) # reset streak nguoi thua

                    loss_embed = discord.Embed(color=bot_cfg.EMBED_COLOR_LOSS)
                    original_starter_for_view = winner_id # de nut "choi lai"

                    if winner_id == bot.user.id: # bot thang
                        loss_embed.title = f"{bot_cfg.PLAYER_LOSS_ICON} {message.author.name} Thua Cuộc! {bot_cfg.PLAYER_LOSS_ICON}"
                        loss_embed.description = (
                            f"{message.author.mention} đã dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'!\n"
                            f"Theo luật Shiritori, {bot_cfg.BOT_PLAYER_START_EMOJI} Bot (người chơi trước) chiến thắng!"
                        )
                        if bot.user.display_avatar: loss_embed.set_thumbnail(url=bot.user.display_avatar.url)
                    else: # nd khac thang
                        try:
                            winner_user = await bot.fetch_user(winner_id)
                            winner_name_display = winner_user.name

                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", winner_name_display, game_language=game_lang) # cap nhat win cho nguoi thang

                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Chúc Mừng {discord.utils.escape_markdown(winner_name_display)}! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = (
                                f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} đã dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'.\n"
                                f"Theo luật Shiritori, {bot_cfg.USER_PLAYER_START_EMOJI} {winner_user.mention} (người chơi trước) chiến thắng!"
                            )
                            if winner_user.display_avatar: loss_embed.set_thumbnail(url=winner_user.display_avatar.url)

                            # hien thi stat nguoi thang
                            user_stats_db = await database.get_user_stats_entry(bot.db_pool, winner_id, guild_id, game_lang, winner_name_display)
                            if user_stats_db:
                                 stats_text = (
                                     f"🏅 Tổng thắng: **{user_stats_db['wins']}**\n"
                                     f"🔥 Chuỗi thắng hiện tại: **{user_stats_db['current_win_streak']}** (Max: **{user_stats_db['max_win_streak']}**)"
                                 )
                                 loss_embed.add_field(name="Thành Tích Người Thắng", value=stats_text, inline=False)

                        except discord.NotFound: # ko tim thay user thang
                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id}", game_language=game_lang)
                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Người Chơi ID {winner_id} Thắng Cuộc! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} thua do dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'."
                        except discord.HTTPException: # loi API
                            await database.update_stat(bot.db_pool, bot.user.id, winner_id, guild_id, "wins", f"User ID {winner_id} (API Err)", game_language=game_lang)
                            loss_embed.title = f"{bot_cfg.SHIRITORI_LOSS_WIN_ICON} Một Người Chơi Thắng! {bot_cfg.SHIRITORI_LOSS_WIN_ICON}"
                            loss_embed.description = f"{bot_cfg.USER_PLAYER_START_EMOJI} {message.author.mention} thua do dùng từ \"**{display_form_for_current_move}**\" (`{phrase_to_validate}`) kết thúc bằng 'ん'. (Lỗi lấy thông tin người thắng)."

                    loss_embed.set_footer(text=f"Luật 'ん' Shiritori | Kênh: #{message.channel.name}")
                    guild_cfg_for_prefix_db = await database.get_guild_config(bot.db_pool, guild_id) # lay prefix
                    command_prefix_for_guild_val = guild_cfg_for_prefix_db.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_for_prefix_db else bot_cfg.DEFAULT_COMMAND_PREFIX

                    # them nut "Choi Lai"
                    view_instance = PostGameView(
                        channel=message.channel,
                        original_starter_id=original_starter_for_view,
                        command_prefix_for_guild=command_prefix_for_guild_val,
                        bot_instance=bot,
                        internal_start_game_callable=internal_start_game
                    )
                    msg_with_view_instance = await message.channel.send(embed=loss_embed, view=view_instance)
                    if msg_with_view_instance :
                        view_instance.message_to_edit = msg_with_view_instance # de view tu disable nut
                        if message.guild: # gui emoji
                           await utils.send_random_guild_emoji_if_any(message.channel, message.guild)

                    # xoa game khoi active_games
                    if channel_id in bot.active_games:
                        del bot.active_games[channel_id]
                    return # ket thuc xu ly vi game da ket thuc

    # ktra tu da dung chua (ap dung cho ca VN va JP, chi ktra neu chua co loi truoc do)
    if not error_occurred and phrase_to_validate and phrase_to_validate in game_state["used_phrases"]:
        error_occurred = True; error_type_for_stat = "used_word_error"

    # xu ly neu co loi
    if error_occurred:
        try: await message.add_reaction(bot_cfg.ERROR_REACTION) # reaction loi
        except (discord.Forbidden, discord.HTTPException): pass
        if error_type_for_stat: # cap nhat stat loi
            await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, error_type_for_stat, current_player_name, game_language=game_lang)
        return # ket thuc xu ly

    # Dam bao phrase_to_validate co gia tri neu la JP va khong co loi
    # (de phong truong hop logic phia tren co van de khien phrase_to_validate rong nhung khong error)
    if not phrase_to_validate and game_lang == "JP":
        if hira_form_jp and is_valid_jp: # neu co hira_form hop le, gan lai
             phrase_to_validate = hira_form_jp
        else:
            # Neu ko valid JP thi da return o tren roi, day la truong hop hi huu
            if not is_valid_jp: return # da xu ly o tren, bo qua
            print(f"LOGIC_WARN: JP move, not error, but phrase_to_validate empty. Input: {user_input_original_str}, Hira: {hira_form_jp}, Valid: {is_valid_jp}")
            return # bo qua luot nay


    # ---- TU HOP LE ----
    try: await message.add_reaction(bot_cfg.CORRECT_REACTION) # reaction dung
    except (discord.Forbidden, discord.HTTPException): pass
    # cap nhat stat luot dung
    await database.update_stat(bot.db_pool, bot.user.id, current_player_id, guild_id, "correct_moves", current_player_name, game_language=game_lang)

    # huy timeout task cua nguoi choi truoc
    if "timeout_task" in game_state and game_state["timeout_task"] and not game_state["timeout_task"].done():
        game_state["timeout_task"].cancel()

    # cap nhat game state
    game_state["current_phrase_str"] = phrase_to_validate
    game_state["current_phrase_display_form"] = display_form_for_current_move # luu dang hien thi

    if game_lang == "VN":
        game_state["word_to_match_next"] = phrase_to_validate.split()[1] # chu thu 2 cua cum VN
    else: # JP
        linking_mora_jp_current = utils.get_shiritori_linking_mora_from_previous_word(phrase_to_validate)
        if not linking_mora_jp_current: # loi nghiem trong neu tu hop le ma ko lay dc am tiet noi
            print(f"LỖI NGHIÊM TRỌNG: Không thể lấy âm tiết nối của từ JP hợp lệ: {phrase_to_validate}")
            await message.channel.send(f"⚠️ Bot gặp lỗi xử lý từ \"{display_form_for_current_move}\". Lượt này có thể không được tính đúng.")
            # Co the can reset game o day hoac bo qua luot
            return
        else:
            game_state["word_to_match_next"] = linking_mora_jp_current

    game_state["used_phrases"].add(phrase_to_validate) # them vao ds da dung
    game_state["last_player_id"] = current_player_id
    game_state["last_correct_message_id"] = message.id # luu id msg dung cuoi

    # them nguoi choi vao ds participants (neu ko phai bot)
    if current_player_id != bot.user.id:
        game_state["participants_since_start"].add(current_player_id)

    # lay config timeout/min_players tu game_state (da luu luc start game)
    timeout_s_config = game_state.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS)
    min_p_config = game_state.get("min_players_for_timeout", bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT)

    # ktra xem da du ng choi de kich hoat timeout chua (neu truoc do chua du)
    if not game_state["timeout_can_be_activated"] and \
       len(game_state["participants_since_start"]) >= min_p_config:
        game_state["timeout_can_be_activated"] = True # danh dau da kich hoat dc
        if msg_channel := bot.get_channel(channel_id): # gui thong bao
            try:
                await msg_channel.send(
                    f"ℹ️ Đã có {len(game_state['participants_since_start'])} người chơi ({min_p_config} tối thiểu). "
                    f"Timeout {timeout_s_config} giây sẽ áp dụng.",
                    delete_after=20 # tu xoa sau 20s
                )
            except discord.HTTPException: pass # bo qua neu ko gui dc

    # tao timeout task moi cho nguoi choi tiep theo (neu timeout da kich hoat dc)
    if game_state["timeout_can_be_activated"]:
        new_timeout_task = asyncio.create_task(
            check_game_timeout(
                bot, channel_id, guild_id,
                game_state["last_player_id"], game_state["current_phrase_str"], # nd vua di, tu vua di
                game_lang # ngon ngu game
            )
        )
        game_state["timeout_task"] = new_timeout_task # luu task