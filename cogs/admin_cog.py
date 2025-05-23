# Noitu/cogs/admin_cog.py
import discord
from discord.ext import commands
from discord import app_commands
import traceback

from .. import utils 
from .. import database
from .. import config as bot_cfg 

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot 

    # --- SLASH CONFIG COMMANDS ---
    config_slash_group = app_commands.Group(name="config", description="Cấu hình bot Nối Từ cho server này.", guild_only=True)


    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await database.get_guild_config(self.bot.db_pool, guild.id) 
        print(f"Đã tham gia server mới: {guild.name} (ID: {guild.id}). Cấu hình mặc định đã được áp dụng nếu chưa có.")

    # --- PREFIX CONFIG COMMANDS ---
    @commands.group(name="config", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True) 
    @commands.guild_only() 
    async def config_group_prefix(self, ctx: commands.Context):
        guild_cfg = await database.get_guild_config(self.bot.db_pool, ctx.guild.id)
        prefix = guild_cfg.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX) if guild_cfg else bot_cfg.DEFAULT_COMMAND_PREFIX
        help_msg = (f"Dùng: `{prefix}config prefix <kí tự>`, `{prefix}config timeout <giây>`, "
                    f"`{prefix}config minplayers <số>`, `{prefix}config language <vn|jp>`.\nHoặc dùng lệnh slash `/config ...`.") # Thêm language
        await utils._send_message_smart(ctx, help_msg) 

    @config_group_prefix.error 
    async def config_prefix_error(self, ctx, error):
        msg = ""
        if isinstance(error, commands.MissingPermissions):
            msg = "Bạn không có quyền `Quản lý Server`."
        elif isinstance(error, commands.NoPrivateMessage): 
            msg = "Lệnh này không dùng trong DM."
        elif isinstance(error, commands.BadArgument): 
            msg = f"Giá trị không hợp lệ: {error}"
        elif isinstance(error, commands.CommandInvokeError): 
            print(f"Lỗi config (prefix): {error.original}")
            traceback.print_exc()
            msg = f"Lỗi khi thực thi: {error.original}"
        else: 
            print(f"Lỗi config (prefix) không rõ: {error}")
            msg = f"Lỗi không xác định: {error}"
        await utils._send_message_smart(ctx, msg, ephemeral=True)

    @config_group_prefix.command(name="prefix")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def config_prefix_set(self, ctx: commands.Context, new_prefix: str):
        if not (1 <= len(new_prefix) <= 5): 
            await utils._send_message_smart(ctx, "Prefix phải từ 1-5 ký tự.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, ctx.guild.id, "command_prefix", new_prefix)
        await utils._send_message_smart(ctx, f"✅ Đã đổi prefix server thành: `{new_prefix}`", ephemeral=True)

    @config_group_prefix.command(name="timeout")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def config_timeout_set(self, ctx: commands.Context, seconds: int):
        if not 10 <= seconds <= 300: 
            await utils._send_message_smart(ctx, "Timeout phải từ 10-300s.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, ctx.guild.id, "timeout_seconds", seconds)
        await utils._send_message_smart(ctx, f"✅ Đã đổi timeout thắng thành: `{seconds}` giây.", ephemeral=True)

    @config_group_prefix.command(name="minplayers")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def config_minplayers_set(self, ctx: commands.Context, count: int):
        if not 1 <= count <= 10: 
            await utils._send_message_smart(ctx, "Số người chơi tối thiểu phải từ 1-10.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, ctx.guild.id, "min_players_for_timeout", count)
        await utils._send_message_smart(ctx, f"✅ Đã đổi số người chơi tối thiểu kích hoạt timeout thành: `{count}`.", ephemeral=True)

    @config_group_prefix.command(name="language") # Lệnh prefix mới
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def config_language_set(self, ctx: commands.Context, lang_code: str):
        lang_code_upper = lang_code.upper()
        if lang_code_upper not in ["VN", "JP"]:
            await utils._send_message_smart(ctx, "Mã ngôn ngữ không hợp lệ. Dùng 'VN' hoặc 'JP'.", ephemeral=True); return
        if lang_code_upper == "JP" and not self.bot.kakasi:
            await utils._send_message_smart(ctx, "⚠️ Không thể chuyển sang Tiếng Nhật do thiếu thư viện PyKakasi trên bot.", ephemeral=True); return

        await database.set_guild_config_value(self.bot.db_pool, ctx.guild.id, "game_language", lang_code_upper)
        lang_name = "Tiếng Việt" if lang_code_upper == "VN" else "Tiếng Nhật"
        await utils._send_message_smart(ctx, f"✅ Đã đổi ngôn ngữ game của server thành: **{lang_name}**.", ephemeral=True)


    # --- Lệnh con của config_slash_group ---
    @config_slash_group.command(name="view", description="Xem cấu hình Nối Từ hiện tại của server.")
    @app_commands.checks.has_permissions(manage_guild=True) 
    async def slash_config_view(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True) 

        cfg = await database.get_guild_config(self.bot.db_pool, interaction.guild_id)
        prefix = cfg.get("command_prefix", bot_cfg.DEFAULT_COMMAND_PREFIX)
        timeout = cfg.get("timeout_seconds", bot_cfg.DEFAULT_TIMEOUT_SECONDS)
        min_players = cfg.get("min_players_for_timeout", bot_cfg.DEFAULT_MIN_PLAYERS_FOR_TIMEOUT)
        game_lang_code = cfg.get("game_language", bot_cfg.DEFAULT_GAME_LANGUAGE) # Lấy ngôn ngữ
        game_lang_name = "Tiếng Việt" if game_lang_code == "VN" else "Tiếng Nhật"
        
        embed = discord.Embed(title=f"⚙️ Cấu hình Nối Từ - {interaction.guild.name}", color=discord.Color.blue())
        embed.add_field(name="Ngôn Ngữ Game", value=f"`{game_lang_name} ({game_lang_code})`", inline=False) # Hiển thị ngôn ngữ
        embed.add_field(name="Prefix Lệnh", value=f"`{prefix}`", inline=False)
        embed.add_field(name="Thời Gian Timeout Thắng", value=f"`{timeout}` giây", inline=False)
        embed.add_field(name="Số Người Chơi Tối Thiểu (để kích hoạt timeout)", value=f"`{min_players}` người", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @config_slash_group.command(name="set_prefix", description="Đặt prefix lệnh mới cho bot (1-5 ký tự).")
    @app_commands.describe(new_prefix="Prefix mới (ví dụ: 'n!', '?').")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_config_set_prefix(self, interaction: discord.Interaction, new_prefix: str):
        await interaction.response.defer(ephemeral=True)
        if not (1 <= len(new_prefix) <= 5):
            await interaction.followup.send("Prefix phải từ 1-5 ký tự.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, interaction.guild_id, "command_prefix", new_prefix)
        await interaction.followup.send(f"✅ Đã đổi prefix server thành: `{new_prefix}`", ephemeral=True)

    @config_slash_group.command(name="set_timeout", description="Đặt thời gian timeout thắng mới (10-300 giây).")
    @app_commands.describe(seconds="Thời gian timeout mới (giây, ví dụ: 60).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_config_set_timeout(self, interaction: discord.Interaction, seconds: int):
        await interaction.response.defer(ephemeral=True)
        if not 10 <= seconds <= 300:
            await interaction.followup.send("Thời gian timeout phải từ 10 đến 300 giây.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, interaction.guild_id, "timeout_seconds", seconds)
        await interaction.followup.send(f"✅ Đã đổi thời gian timeout thắng thành: `{seconds}` giây.", ephemeral=True)

    @config_slash_group.command(name="set_minplayers", description="Số người chơi tối thiểu để kích hoạt timeout (1-10).")
    @app_commands.describe(count="Số người chơi tối thiểu mới (ví dụ: 2).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_config_set_minplayers(self, interaction: discord.Interaction, count: int):
        await interaction.response.defer(ephemeral=True)
        if not 1 <= count <= 10:
            await interaction.followup.send("Số người chơi tối thiểu phải từ 1 đến 10.", ephemeral=True); return
        await database.set_guild_config_value(self.bot.db_pool, interaction.guild_id, "min_players_for_timeout", count)
        await interaction.followup.send(f"✅ Đã đổi số người chơi tối thiểu để kích hoạt timeout thành: `{count}`.", ephemeral=True)

    @config_slash_group.command(name="set_language", description="Đặt ngôn ngữ game cho server (VN hoặc JP).") # Lệnh slash mới
    @app_commands.describe(language_code="Mã ngôn ngữ ('vn' hoặc 'jp').")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def slash_config_set_language(self, interaction: discord.Interaction, language_code: str):
        await interaction.response.defer(ephemeral=True)
        lang_code_upper = language_code.strip().upper()
        if lang_code_upper not in ["VN", "JP"]:
            await interaction.followup.send("Mã ngôn ngữ không hợp lệ. Dùng 'VN' hoặc 'JP'.", ephemeral=True); return
        
        if lang_code_upper == "JP" and not self.bot.kakasi:
            await interaction.followup.send(
                "⚠️ Không thể chuyển sang Tiếng Nhật do bot hiện tại chưa được cấu hình đúng (thiếu thư viện PyKakasi). "
                "Vui lòng liên hệ người quản lý bot.", 
                ephemeral=True
            )
            return

        await database.set_guild_config_value(self.bot.db_pool, interaction.guild_id, "game_language", lang_code_upper)
        lang_name = "Tiếng Việt" if lang_code_upper == "VN" else "Tiếng Nhật"
        await interaction.followup.send(f"✅ Đã đổi ngôn ngữ game của server thành: **{lang_name}**.", ephemeral=True)


    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        error_message = "Có lỗi xảy ra khi thực hiện lệnh config." 
        log_error = True 

        if isinstance(error, app_commands.MissingPermissions): 
            error_message = "Bạn không có quyền `Quản lý Server` để dùng lệnh này."
            log_error = False 
        elif isinstance(error, app_commands.CommandInvokeError) and isinstance(error.original, (ValueError, TypeError)): 
            error_message = f"Giá trị không hợp lệ: {error.original}"
            log_error = False
        elif isinstance(error, app_commands.CheckFailure): 
            error_message = "Bạn không đáp ứng điều kiện để dùng lệnh này."
            log_error = False
        elif isinstance(error, app_commands.CommandAlreadyRegistered): 
            error_message = f"Lệnh '{error.name}' đã được đăng ký rồi. Vui lòng kiểm tra lại code."
            print(f"Lỗi CommandAlreadyRegistered trong cog_app_command_error cho lệnh: {error.name}") 
            log_error = True 

        if log_error: 
            print(f"Lỗi lệnh /config (error handler for cog): {error}")
            traceback.print_exc()

        if not interaction.response.is_done():
            await interaction.response.send_message(error_message, ephemeral=True)
        else:
            try:
                await interaction.followup.send(error_message, ephemeral=True)
            except discord.HTTPException: 
                print(f"Không thể gửi followup error cho /config sau khi đã response: {error_message}")


async def setup(bot: commands.Bot): 
    cog = AdminCog(bot)
    await bot.add_cog(cog)