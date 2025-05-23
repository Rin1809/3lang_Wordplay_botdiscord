# Noitu/cogs/general_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import traceback

from .. import utils
from .. import database
from .. import config as bot_cfg 
from ..game import views as game_views # Import views từ game package
from ..game import logic as game_logic # Import logic để lấy callable


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot # Lưu bot instance

    @commands.command(name='help', aliases=['h', 'luat', 'helpnoitu', 'luatnoitu'])
    async def help_command_prefix(self, ctx: commands.Context):
        if not ctx.guild: # Lệnh này chỉ dùng trong server
            await utils._send_message_smart(ctx, content="Lệnh này chỉ dùng trong server.", ephemeral=True)
            return

        # Lấy prefix hiện tại của guild
        guild_cfg = await database.get_guild_config(self.bot.db_pool, ctx.guild.id)
        prefix = guild_cfg.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg else bot_cfg.DEFAULT_COMMAND_PREFIX

        # Tạo embed hướng dẫn
        embed, error_msg = await utils.generate_help_embed(self.bot, ctx.guild, prefix) # Truyền self.bot

        if error_msg: # Có lỗi khi tạo embed
            await utils._send_message_smart(ctx, content=error_msg, ephemeral=True)
        elif embed: # Tạo view và gửi
            view = game_views.HelpView(
                command_prefix_for_guild=prefix,
                bot_instance=self.bot, # Truyền self.bot
                internal_start_game_callable=game_logic.internal_start_game # Truyền hàm bắt đầu game
            )
            msg = await utils._send_message_smart(ctx, embed=embed, view=view)
            if msg : view.message_to_edit = msg # Gán message cho view để edit
        else: # Lỗi ko xác định
            await utils._send_message_smart(ctx, content="Lỗi khi tạo tin nhắn hướng dẫn.", ephemeral=True)

    @app_commands.command(name="help", description="Hiển thị hướng dẫn chơi Nối Từ.")
    async def slash_help(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild or not interaction.channel or not isinstance(interaction.channel, discord.abc.GuildChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh của server.", ephemeral=True); return

        try:
            await interaction.response.defer(ephemeral=False) # Help msg là public

            guild_cfg = await database.get_guild_config(self.bot.db_pool, interaction.guild_id)
            prefix = guild_cfg.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg else bot_cfg.DEFAULT_COMMAND_PREFIX

            embed, error_msg = await utils.generate_help_embed(self.bot, interaction.guild, prefix) # Truyền self.bot

            if error_msg:
                await interaction.followup.send(error_msg, ephemeral=True)
            elif embed:
                view = game_views.HelpView(
                    command_prefix_for_guild=prefix,
                    bot_instance=self.bot, # Truyền self.bot
                    internal_start_game_callable=game_logic.internal_start_game 
                )
                msg = await interaction.followup.send(embed=embed, view=view, wait=True)
                if msg: view.message_to_edit = msg 
            else:
                await interaction.followup.send("Lỗi khi tạo tin nhắn hướng dẫn.", ephemeral=True)

        except Exception as e:
            print(f"Lỗi không mong muốn trong /help: {e}")
            traceback.print_exc()
            # Xử lý nếu chưa response hoặc đã response
            if not interaction.response.is_done():
                try: await interaction.response.send_message("Đã xảy ra lỗi khi hiển thị hướng dẫn.", ephemeral=True)
                except discord.HTTPException: pass # Bỏ qua nếu ko gửi dc
            else:
                try: await interaction.followup.send("Đã xảy ra lỗi khi hiển thị hướng dẫn.", ephemeral=True)
                except discord.HTTPException: pass
    
    @app_commands.command(name="ping", description="Kiểm tra độ trễ của bot.")
    async def slash_ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.bot.latency * 1000)}ms")


async def setup(bot: commands.Bot): # Hàm setup để bot load cog
    await bot.add_cog(GeneralCog(bot))