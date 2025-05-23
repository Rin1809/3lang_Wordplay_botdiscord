# Noitu/cogs/game_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import traceback

from .. import utils
from .. import database
from ..game import logic as game_logic # Import logic chính của game

class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot # Lưu bot instance

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or not message.guild: # Bỏ qua bot và DM
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid and ctx.command: # Nếu message gọi 1 command hợp lệ -> ko phải lượt đi game
            return

        await game_logic.process_game_message(self.bot, message) # Truyền self.bot


    @commands.command(name='bxh', aliases=['leaderboard', 'xephang'])
    async def leaderboard_command_prefix(self, ctx: commands.Context):
        if not ctx.guild: # Chỉ dùng trong server
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        # Tạo embed BXH, truyền self.bot trước, sau đó là ctx.guild
        embed, error_msg = await utils.generate_leaderboard_embed(self.bot, ctx.guild) # Sửa thứ tự tham số
        if error_msg: # Có lỗi
            is_db_error = "DB chưa sẵn sàng" in error_msg 
            await utils._send_message_smart(ctx, error_msg, ephemeral=True, delete_after=10 if is_db_error else None)
        else: # Gửi embed BXH
            await utils._send_message_smart(ctx, embed=embed)

    @app_commands.command(name="bxh", description="Hiển thị bảng xếp hạng Nối Từ của server.")
    async def slash_bxh(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild or not isinstance(interaction.channel, discord.abc.GuildChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh của server.", ephemeral=True); return
        
        try:
            await interaction.response.defer(ephemeral=False) 
            # Truyền self.bot trước, sau đó là interaction.guild
            embed, error_msg = await utils.generate_leaderboard_embed(self.bot, interaction.guild) # Sửa thứ tự tham số
            if error_msg:
                await interaction.followup.send(error_msg, ephemeral=True) 
            else:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Lỗi không mong muốn trong /bxh: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Đã xảy ra lỗi khi hiển thị BXH.", ephemeral=True)
                except discord.HTTPException: pass
            else:
                try: await interaction.followup.send("Đã xảy ra lỗi khi hiển thị BXH.", ephemeral=True)
                except discord.HTTPException: pass

    @commands.command(name='start', aliases=['batdau', 'choi', 'noitu'])
    async def start_command_prefix(self, ctx: commands.Context, *, start_phrase_input: str = None):
        if not ctx.guild:
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True); return
        if not isinstance(ctx.channel, discord.TextChannel): 
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong kênh text.", ephemeral=True); return
        
        await game_logic.internal_start_game(self.bot, ctx.channel, ctx.author, ctx.guild.id, start_phrase_input, interaction=getattr(ctx, 'interaction', None))

    @app_commands.command(name="start", description="Bắt đầu game Nối Từ.")
    @app_commands.describe(phrase="Cụm từ bắt đầu (2 chữ). Bot sẽ chọn nếu bỏ trống.")
    async def slash_start(self, interaction: discord.Interaction, phrase: str = None):
        if not interaction.guild_id or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return

        if not interaction.response.is_done(): 
            await interaction.response.defer() 
        
        await game_logic.internal_start_game(self.bot, interaction.channel, interaction.user, interaction.guild_id, phrase, interaction=interaction)

    @commands.command(name='stop', aliases=['dunglai', 'stopnoitu'])
    async def stop_command_prefix(self, ctx: commands.Context):
        if not ctx.guild:
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True); return
        if not isinstance(ctx.channel, discord.TextChannel):
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong kênh text.", ephemeral=True); return
        await game_logic.internal_stop_game(self.bot, ctx.channel, ctx.author, ctx.guild.id, interaction=getattr(ctx, 'interaction', None))

    @app_commands.command(name="stop", description="Dừng game Nối Từ hiện tại.")
    async def slash_stop(self, interaction: discord.Interaction):
        if not interaction.guild_id or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return

        if not interaction.response.is_done(): 
            await interaction.response.defer(ephemeral=False) 
        
        await game_logic.internal_stop_game(self.bot, interaction.channel, interaction.user, interaction.guild_id, interaction=interaction)


async def setup(bot: commands.Bot): 
    await bot.add_cog(GameCog(bot))