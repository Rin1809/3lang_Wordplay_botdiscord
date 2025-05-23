# Noitu/game/views.py
import discord
from discord.ui import Button, View
import traceback
from typing import Callable, Coroutine, Any
from .. import utils 
from discord.ext import commands


class PostGameView(View):
    def __init__(self, channel: discord.TextChannel, original_starter_id: int, 
                 command_prefix_for_guild: str, bot_instance: commands.Bot, # Nhận bot_instance
                 internal_start_game_callable: Callable[..., Coroutine[Any, Any, None]],
                 timeout=180):
        super().__init__(timeout=timeout)
        self.channel = channel
        self.original_starter_id = original_starter_id
        self.command_prefix_for_guild = command_prefix_for_guild
        self.bot = bot_instance # Lưu bot instance
        self.internal_start_game_callable = internal_start_game_callable # Lưu hàm để gọi lại
        self.game_starter_used = False # Cờ cho nút "Chơi Lại"
        self.message_to_edit: discord.Message = None # Message chứa view này

    async def handle_command_invocation(self, interaction: discord.Interaction, command_name: str, *cmd_args):
        # Tạo context giả để invoke lệnh prefix từ button
        command_parts = [f"{self.command_prefix_for_guild}{command_name}"]
        command_parts.extend(cmd_args)
        actual_command_to_parse = " ".join(command_parts)

        # Gửi msg tạm để bot parse context
        temp_msg_for_context = await self.channel.send(actual_command_to_parse) 

        mock_context = await self.bot.get_context(temp_msg_for_context) # Dùng self.bot
        mock_context.author = interaction.user 
        mock_context.channel = interaction.channel # Kênh của interaction
        mock_context.interaction = interaction # Gắn interaction vào context

        await temp_msg_for_context.delete() # Xóa msg tạm

        cmd_obj = self.bot.get_command(command_name) # Dùng self.bot
        if cmd_obj:
            try:
                await cmd_obj.invoke(mock_context) # Invoke lệnh
            except Exception as e:
                print(f"Lỗi invoke '{command_name}' từ button PostGameView: {e}")
                traceback.print_exc()
                try: # Thử gửi lỗi cho user
                    await interaction.followup.send(f"Lỗi khi thực hiện lệnh '{command_name}'. Vui lòng thử lại.", ephemeral=True)
                except discord.HTTPException:
                    print(f"Không thể gửi followup error cho invoke '{command_name}'.")
        else: # Lệnh ko tìm thấy
            try:
                await interaction.followup.send(f"Lệnh '{command_name}' không tìm thấy.", ephemeral=True)
            except discord.HTTPException:
                 print(f"Không thể gửi followup error cho lệnh không tìm thấy '{command_name}'.")

    @discord.ui.button(label="Chơi Lại", style=discord.ButtonStyle.success, emoji="🔁")
    async def play_again_button(self, interaction: discord.Interaction, button: Button):
        if self.game_starter_used: # Đã dùng nút này rồi
            await interaction.response.send_message("Nút 'Chơi Lại' đã được sử dụng hoặc game mới đã bắt đầu.", ephemeral=True)
            return
        
        await interaction.response.defer() # Defer trước
        
        self.game_starter_used = True # Đánh dấu đã dùng
        button.disabled = True # Vô hiệu hóa nút
        # Vô hiệu hóa nút "Xem BXH" nếu có
        if len(self.children) > 1 and isinstance(self.children[1], Button) and self.children[1].label == "Xem BXH":
            self.children[1].disabled = True 

        if self.message_to_edit: # Cập nhật view trên message gốc
            try: 
                await self.message_to_edit.edit(view=self)
            except discord.NotFound: pass # Message đã bị xóa
            except discord.HTTPException as e_edit: 
                print(f"Lỗi edit message PostGameView play_again: {e_edit}")

        if not isinstance(interaction.channel, discord.TextChannel): # Kênh ko hợp lệ
            await interaction.followup.send("Lỗi: không thể bắt đầu game ở kênh này.", ephemeral=True)
            return
        if not interaction.guild_id: # Ko có guild ID
             await interaction.followup.send("Lỗi: Không thể xác định server (guild ID).", ephemeral=True)
             return

        try:
            # Gọi hàm bắt đầu game, truyền self.bot
            await self.internal_start_game_callable(
                bot=self.bot, # Quan trọng: truyền bot instance
                channel=interaction.channel,
                author=interaction.user, 
                guild_id=interaction.guild_id,
                start_phrase_input=None, # Bot chọn từ
                interaction=interaction
            )
        except Exception as e:
            print(f"Lỗi gọi internal_start_game từ PostGameView.play_again_button: {e}")
            traceback.print_exc()
            try: # Báo lỗi cho user
                await interaction.followup.send("Lỗi khi bắt đầu game (chơi lại). Vui lòng thử lại sau.", ephemeral=True)
            except discord.HTTPException:
                print("Không thể gửi followup error cho play_again_button.")

    @discord.ui.button(label="Xem BXH", style=discord.ButtonStyle.primary, emoji="🏆")
    async def view_leaderboard_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer() # Defer trước
        await self.handle_command_invocation(interaction, "bxh") # Giả sử lệnh là "bxh"

    async def on_timeout(self): # Khi view hết hạn
        for item in self.children: # Vô hiệu hóa tất cả item
            item.disabled = True
        if self.message_to_edit: # Cập nhật message gốc
            try:
                content = self.message_to_edit.content
                new_content = content + "\n*(Các nút đã hết hạn)*" if content and "Các nút đã hết hạn" not in content else "*(Các nút đã hết hạn)*"
                embed = self.message_to_edit.embeds[0] if self.message_to_edit.embeds else None
                if embed: # Nếu có embed, thêm vào footer
                    footer_text = "Các nút đã hết hạn."
                    if embed.footer and embed.footer.text:
                        if "Các nút đã hết hạn." not in embed.footer.text:
                             footer_text = embed.footer.text + " | " + footer_text
                        else: 
                            footer_text = embed.footer.text # Đã có text timeout
                    embed.set_footer(text=footer_text)
                    await self.message_to_edit.edit(embed=embed, view=self)
                else: # Ko có embed, chỉ cập nhật content
                    await self.message_to_edit.edit(content=new_content, view=self)
            except discord.NotFound: pass
            except discord.HTTPException as e_edit: print(f"Lỗi edit message on_timeout PostGameView: {e_edit}")
            except Exception as e: print(f"Lỗi không xác định on_timeout PostGameView: {e}")


class HelpView(View):
    def __init__(self, command_prefix_for_guild: str, bot_instance: commands.Bot, # Nhận bot_instance
                 internal_start_game_callable: Callable[..., Coroutine[Any, Any, None]],
                 timeout=180):
        super().__init__(timeout=timeout)
        self.command_prefix_for_guild = command_prefix_for_guild
        self.bot = bot_instance # Lưu bot instance
        self.internal_start_game_callable = internal_start_game_callable # Lưu hàm
        self.message_to_edit: discord.Message = None

    @discord.ui.button(label="Bắt Đầu Nhanh (Bot chọn từ)", style=discord.ButtonStyle.green, emoji="🎮")
    async def quick_start_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer() # Defer trước

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("Lỗi: không thể bắt đầu game ở kênh này.", ephemeral=True)
            return
        if not interaction.guild_id:
             await interaction.followup.send("Lỗi: Không thể xác định server (guild ID).", ephemeral=True)
             return

        try:
            # Gọi hàm bắt đầu game, truyền self.bot
            await self.internal_start_game_callable(
                bot=self.bot, # Quan trọng: truyền bot instance
                channel=interaction.channel,
                author=interaction.user,
                guild_id=interaction.guild_id,
                start_phrase_input=None, # Bot chọn từ
                interaction=interaction
            )
        except Exception as e:
            print(f"Lỗi khi gọi internal_start_game từ HelpView button: {e}")
            traceback.print_exc()
            try:
                await interaction.followup.send("Lỗi khi bắt đầu game nhanh. Vui lòng thử lại sau.", ephemeral=True)
            except discord.HTTPException:
                print("Không thể gửi followup error cho quick_start_button.")

        button.disabled = True # Vô hiệu hóa nút sau khi dùng
        if self.message_to_edit: # Cập nhật view
            try:
                await self.message_to_edit.edit(view=self)
            except discord.NotFound: pass
            except discord.HTTPException as e_edit:
                print(f"Lỗi khi edit message trong HelpView on quick_start: {e_edit}")

    async def on_timeout(self): # Khi view hết hạn
        for item in self.children: # Vô hiệu hóa tất cả item
            item.disabled = True
        if self.message_to_edit: # Cập nhật message gốc
            try:
                if self.message_to_edit.embeds: # Nếu có embed
                    embed = self.message_to_edit.embeds[0]
                    footer_text = "(Nút hết hạn)"
                    if embed.footer and embed.footer.text:
                        if "(Nút hết hạn)" not in embed.footer.text:
                            footer_text = embed.footer.text + " | " + footer_text
                        else:
                            footer_text = embed.footer.text 
                    embed.set_footer(text=footer_text)
                    await self.message_to_edit.edit(embed=embed, view=self)
                else: 
                    await self.message_to_edit.edit(view=self) # Chỉ cập nhật view
            except discord.NotFound: pass
            except discord.HTTPException as e_edit: print(f"Lỗi edit message on_timeout HelpView: {e_edit}")
            except Exception as e: print(f"Lỗi không xác định on_timeout HelpView: {e}")