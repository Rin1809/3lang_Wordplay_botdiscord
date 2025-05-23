# Noitu/cogs/game_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import traceback

from .. import utils
from .. import database
from ..game import logic as game_logic
from .. import config as bot_cfg

class GameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot 

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or not message.guild: 
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid and ctx.command: # Ignore if it's a valid command invocation
            return

        await game_logic.process_game_message(self.bot, message) 

    @commands.command(name='bxh', aliases=['leaderboard', 'xephang'])
    async def leaderboard_command_prefix(self, ctx: commands.Context):
        if not ctx.guild: 
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True)
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong kênh text.", ephemeral=True)
            return

        _t, _m, game_lang_for_channel = await utils.get_channel_game_settings(self.bot, ctx.guild.id, ctx.channel.id)
        if not game_lang_for_channel:
            await utils._send_message_smart(ctx, "Kênh này chưa được cấu hình để chơi Nối Từ. Không thể xem BXH.", ephemeral=True)
            return
            
        embed, error_msg = await utils.generate_leaderboard_embed(self.bot, ctx.guild, game_lang_for_channel)
        if error_msg: 
            is_db_error = "DB chưa sẵn sàng" in error_msg 
            await utils._send_message_smart(ctx, error_msg, ephemeral=True, delete_after=10 if is_db_error else None)
        else: 
            await utils._send_message_smart(ctx, embed=embed)

    @app_commands.command(name="bxh", description="Hiển thị bảng xếp hạng Nối Từ của server cho ngôn ngữ của kênh này.")
    async def slash_bxh(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return
        
        try:
            await interaction.response.defer(ephemeral=False)
            _t, _m, game_lang_for_channel = await utils.get_channel_game_settings(self.bot, interaction.guild_id, interaction.channel_id)
            
            if not game_lang_for_channel:
                await interaction.followup.send("Kênh này chưa được cấu hình để chơi Nối Từ. Không thể xem BXH.", ephemeral=True)
                return

            embed, error_msg = await utils.generate_leaderboard_embed(self.bot, interaction.guild, game_lang_for_channel)
            if error_msg:
                await interaction.followup.send(error_msg, ephemeral=True) 
            else:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Lỗi không mong muốn trong /bxh: {e}")
            traceback.print_exc()
            error_message = "Đã xảy ra lỗi khi hiển thị BXH."
            if not interaction.response.is_done():
                try: await interaction.response.send_message(error_message, ephemeral=True)
                except discord.HTTPException: pass
            else:
                try: await interaction.followup.send(error_message, ephemeral=True)
                except discord.HTTPException: pass

    @commands.command(name='start', aliases=['batdau', 'choi', 'noitu'])
    async def start_command_prefix(self, ctx: commands.Context, *, start_phrase_input: str = None):
        if not ctx.guild:
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True); return
        if not isinstance(ctx.channel, discord.TextChannel): 
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong kênh text.", ephemeral=True); return
        
        await game_logic.internal_start_game(self.bot, ctx.channel, ctx.author, ctx.guild.id, start_phrase_input, interaction=getattr(ctx, 'interaction', None))

    @app_commands.command(name="start", description="Bắt đầu game Nối Từ trong kênh này.")
    @app_commands.describe(phrase="Cụm từ/từ bắt đầu (tùy theo ngôn ngữ kênh). Bot sẽ chọn nếu bỏ trống.")
    async def slash_start(self, interaction: discord.Interaction, phrase: str = None):
        if not interaction.guild_id or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return
        
        await game_logic.internal_start_game(self.bot, interaction.channel, interaction.user, interaction.guild_id, phrase, interaction=interaction)

    @commands.command(name='stop', aliases=['dunglai', 'stopnoitu'])
    async def stop_command_prefix(self, ctx: commands.Context):
        if not ctx.guild:
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong server.", ephemeral=True); return
        if not isinstance(ctx.channel, discord.TextChannel):
            await utils._send_message_smart(ctx, "Lệnh này chỉ dùng trong kênh text.", ephemeral=True); return
        await game_logic.internal_stop_game(self.bot, ctx.channel, ctx.author, ctx.guild.id, interaction=getattr(ctx, 'interaction', None))

    @app_commands.command(name="stop", description="Dừng game Nối Từ hiện tại trong kênh này.")
    async def slash_stop(self, interaction: discord.Interaction):
        if not interaction.guild_id or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return        
        await game_logic.internal_stop_game(self.bot, interaction.channel, interaction.user, interaction.guild_id, interaction=interaction)

async def setup(bot: commands.Bot): 
    await bot.add_cog(GameCog(bot))