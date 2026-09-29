import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.guild_config import get_guild_config, set_guild_config

CATEGORY_NAME = "🛠️ Mod Area"
LOG_CHANNEL_NAME = "mod-logs"
ANNOUNCE_CHANNEL_NAME = "mod-announcements"


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class Setup(commands.Cog):
    """Lệnh setup 1 phát tạo sẵn khu vực riêng cho đội mod: kênh log + kênh thông báo."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _find_mod_role(self, guild: discord.Guild) -> discord.Role | None:
        """Tự tìm role có sẵn nghe giống role mod (tên chứa 'mod', có quyền kick/ban/timeout)."""
        candidates = [
            r for r in guild.roles
            if r != guild.default_role and not r.managed and "mod" in r.name.lower()
        ]
        if not candidates:
            return None
        for r in candidates:
            if r.permissions.kick_members or r.permissions.ban_members or r.permissions.moderate_members:
                return r
        return candidates[0]

    # -----------------------------------------------------------------
    # /setup - /!setup
    # -----------------------------------------------------------------
    @commands.hybrid_command(
        name="setup",
        description="Tự động tạo khu vực riêng cho mod: kênh log + kênh thông báo",
    )
    @app_commands.describe(
        mod_role="Role dành cho mod (để trống bot sẽ tự tìm role có sẵn hoặc tạo mới)",
        reset="Tạo lại category/kênh mới dù đã setup từ trước",
    )
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True, manage_roles=True)
    async def setup(self, ctx: commands.Context, mod_role: discord.Role = None, reset: bool = False):
        guild = ctx.guild
        cfg = get_guild_config(guild.id)

        if ctx.interaction:
            await ctx.defer()

        # Nếu đã setup trước đó và không yêu cầu reset -> báo trạng thái hiện tại, dừng lại
        if not reset and cfg.get("mod_log_channel") and cfg.get("mod_announcement_channel"):
            existing_log = guild.get_channel(cfg["mod_log_channel"])
            existing_announce = guild.get_channel(cfg["mod_announcement_channel"])
            if existing_log and existing_announce:
                embed = mod_embed(
                    f"{e('info')} Server này đã được setup rồi",
                    f"**Kênh log:** {existing_log.mention}\n"
                    f"**Kênh thông báo:** {existing_announce.mention}\n\n"
                    f"Dùng `/setup reset:true` (hoặc `?setup @role true`) nếu muốn tạo lại từ đầu.",
                    discord.Color.blurple(),
                )
                return await ctx.send(embed=embed)

        # 1. Xác định / tạo role mod
        role_created = False
        if mod_role is None:
            mod_role = self._find_mod_role(guild)
        if mod_role is None:
            mod_role = await guild.create_role(
                name="Moderator", color=discord.Color.blue(),
                reason=f"Auto-setup bởi {ctx.author}",
            )
            role_created = True

        # 2. Tạo category riêng cho mod (ẩn với @everyone, chỉ mod + bot thấy được)
        category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
        if category is None or reset:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
            }
            category = await guild.create_category(
                CATEGORY_NAME, overwrites=overwrites, reason=f"Auto-setup bởi {ctx.author}",
            )

        # 3. Kênh log (dùng chung cho lệnh moderation + cảnh báo raid/fakebot)
        log_channel = discord.utils.get(category.text_channels, name=LOG_CHANNEL_NAME)
        if log_channel is None:
            log_channel = await guild.create_text_channel(
                LOG_CHANNEL_NAME, category=category,
                topic="Log tự động: hành động moderation, cảnh báo raid, bot giả dạng.",
                reason=f"Auto-setup bởi {ctx.author}",
            )

        # 4. Kênh thông báo riêng cho đội mod
        announce_channel = discord.utils.get(category.text_channels, name=ANNOUNCE_CHANNEL_NAME)
        if announce_channel is None:
            announce_channel = await guild.create_text_channel(
                ANNOUNCE_CHANNEL_NAME, category=category,
                topic="Thông báo nội bộ dành riêng cho đội ngũ mod.",
                reason=f"Auto-setup bởi {ctx.author}",
            )

        # 5. Lưu cấu hình lại — mod-log sẽ tự nhận cảnh báo raid/fakebot luôn, không cần setmodlog nữa
        set_guild_config(
            guild.id,
            mod_log_channel=log_channel.id,
            mod_announcement_channel=announce_channel.id,
            mod_role_id=mod_role.id,
        )

        desc = (
            f"**Role mod:** {mod_role.mention} {'(vừa tạo mới)' if role_created else '(dùng role có sẵn)'}\n"
            f"**Kênh log:** {log_channel.mention} — tự nhận cảnh báo raid/bot giả dạng + log moderation\n"
            f"**Kênh thông báo:** {announce_channel.mention} — dùng lệnh `modannounce <nội dung>` để gửi vào đây\n\n"
            f"Cả 2 kênh chỉ {mod_role.mention} và bot thấy được.\n"
            f"Muốn bật phòng vệ 24/7 luôn thì chạy `autodefense on`."
        )
        embed = mod_embed(f"{e('success')} Setup hoàn tất", desc, discord.Color.green())
        await ctx.send(embed=embed)

    # -----------------------------------------------------------------
    # modannounce - gửi thông báo vào kênh mod-announcements đã tạo ở /setup
    # -----------------------------------------------------------------
    @commands.hybrid_command(name="modannounce", description="Gửi thông báo vào kênh riêng của đội mod")
    @app_commands.describe(message="Nội dung thông báo")
    @commands.has_permissions(manage_messages=True)
    async def modannounce(self, ctx: commands.Context, *, message: str):
        cfg = get_guild_config(ctx.guild.id)
        channel_id = cfg.get("mod_announcement_channel")

        if not channel_id:
            embed = mod_embed(f"{e('error')} Chưa setup", "Chưa có kênh thông báo mod. Chạy lệnh `setup` trước.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            embed = mod_embed(f"{e('error')} Kênh đã bị xoá", "Kênh thông báo không còn tồn tại. Chạy lại `setup` để tạo mới.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        announce_embed = mod_embed(f"📣 Thông báo từ {ctx.author.display_name}", message, discord.Color.gold())
        await channel.send(embed=announce_embed)

        confirm = mod_embed(f"{e('success')} Đã send thông báo", f"Đã gửi vào {channel.mention}.", discord.Color.green())
        await ctx.send(embed=confirm, ephemeral=True if ctx.interaction else False)

    # -----------------------------------------------------------------
    @setup.error
    @modannounce.error
    async def setup_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Lệnh này cần quyền Administrator (hoặc Manage Messages cho `modannounce`).", discord.Color.red())
        elif isinstance(error, commands.BotMissingPermissions):
            embed = mod_embed(f"{e('error')} Bot thiếu quyền", "Bot cần quyền `Manage Channels` và `Manage Roles` để chạy setup.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(Setup(bot))
