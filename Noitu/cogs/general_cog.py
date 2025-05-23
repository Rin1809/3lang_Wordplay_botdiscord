# Noitu/cogs/general_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import traceback

from .. import utils
from .. import database
from .. import config as bot_cfg 
from ..game import views as game_views 
from ..game import logic as game_logic 


class GeneralCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name='help', aliases=['h', 'luat', 'helpnoitu', 'luatnoitu'])
    async def help_command_prefix(self, ctx: commands.Context):
        if not ctx.guild: 
            await utils._send_message_smart(ctx, content="Lệnh này chỉ dùng trong server.", ephemeral=True)
            return
        if not isinstance(ctx.channel, discord.TextChannel):
            await utils._send_message_smart(ctx, content="Lệnh này chỉ dùng trong kênh text.", ephemeral=True)
            return

        guild_cfg_db = await database.get_guild_config(self.bot.db_pool, ctx.guild.id)
        prefix = guild_cfg_db.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_db else bot_cfg.DEFAULT_COMMAND_PREFIX

        embed, error_msg = await utils.generate_help_embed(self.bot, ctx.guild, prefix, ctx.channel.id)

        if error_msg: 
            await utils._send_message_smart(ctx, content=error_msg, ephemeral=True)
        elif embed: 
            # Only show quick start button if the channel is configured for a game
            _t, _m, game_lang_for_channel = await utils.get_channel_game_settings(self.bot, ctx.guild.id, ctx.channel.id)
            view = None
            if game_lang_for_channel: # Channel is configured, show button
                view = game_views.HelpView(
                    command_prefix_for_guild=prefix,
                    bot_instance=self.bot, 
                    internal_start_game_callable=game_logic.internal_start_game 
                )
            
            msg = await utils._send_message_smart(ctx, embed=embed, view=view)
            if msg and view: view.message_to_edit = msg 
        else: 
            await utils._send_message_smart(ctx, content="Lỗi khi tạo tin nhắn hướng dẫn.", ephemeral=True)

    @app_commands.command(name="help", description="Hiển thị hướng dẫn chơi Nối Từ cho kênh này.")
    async def slash_help(self, interaction: discord.Interaction):
        if not interaction.guild_id or not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("Lệnh này chỉ dùng trong kênh text của server.", ephemeral=True); return

        try:
            # Defer response as public
            # await interaction.response.defer(ephemeral=False) # Defer is handled by _send_message_smart

            guild_cfg_db = await database.get_guild_config(self.bot.db_pool, interaction.guild_id)
            prefix = guild_cfg_db.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg_db else bot_cfg.DEFAULT_COMMAND_PREFIX

            embed, error_msg = await utils.generate_help_embed(self.bot, interaction.guild, prefix, interaction.channel_id)

            if error_msg:
                # await interaction.followup.send(error_msg, ephemeral=True)
                await utils._send_message_smart(interaction, content=error_msg, ephemeral=True)
            elif embed:
                _t, _m, game_lang_for_channel = await utils.get_channel_game_settings(self.bot, interaction.guild_id, interaction.channel_id)
                view = None
                if game_lang_for_channel:
                    view = game_views.HelpView(
                        command_prefix_for_guild=prefix,
                        bot_instance=self.bot, 
                        internal_start_game_callable=game_logic.internal_start_game 
                    )
                # msg = await interaction.followup.send(embed=embed, view=view, wait=True)
                msg = await utils._send_message_smart(interaction, embed=embed, view=view)
                if msg and view: view.message_to_edit = msg 
            else:
                # await interaction.followup.send("Lỗi khi tạo tin nhắn hướng dẫn.", ephemeral=True)
                await utils._send_message_smart(interaction, content="Lỗi khi tạo tin nhắn hướng dẫn.", ephemeral=True)

        except Exception as e:
            print(f"Lỗi không mong muốn trong /help: {e}")
            traceback.print_exc()
            error_message = "Đã xảy ra lỗi khi hiển thị hướng dẫn."
            await utils._send_message_smart(interaction, content=error_message, ephemeral=True)
    
    @app_commands.command(name="ping", description="Kiểm tra độ trễ của bot.")
    async def slash_ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.bot.latency * 1000)}ms")

async def setup(bot: commands.Bot): 
    await bot.add_cog(GeneralCog(bot))