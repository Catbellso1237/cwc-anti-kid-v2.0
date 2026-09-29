import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta

from utils.emojis import e
from utils.storage import add_warning, get_warnings, clear_warnings


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


class Moderation(commands.Cog):
    """Các lệnh điều hành server: kick, ban, mute, warn, purge, lock..."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def react_ok(self, ctx: commands.Context, key: str = "success"):
        """Nếu lệnh được gọi bằng prefix (!), thả reaction lên tin nhắn gốc."""
        if ctx.interaction is None and ctx.message:
            try:
                await ctx.message.add_reaction(e(key))
            except discord.HTTPException:
                pass

    # ---------------------------------------------------------------
    # KICK
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="kick", description="Kick một thành viên khỏi server")
    @app_commands.describe(member="Thành viên cần kick", reason="Lý do kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Không có lý do"):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            embed = mod_embed(f"{e('error')} Không thể kick", "Bạn không thể kick người có vai trò cao hơn hoặc bằng bạn.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        await member.kick(reason=f"{reason} | Bởi {ctx.author}")
        embed = mod_embed(f"{e('kick')} Đã kick thành viên", f"**Thành viên:** {member.mention}\n**Lý do:** {reason}\n**Người thực hiện:** {ctx.author.mention}", discord.Color.orange())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "kick")

    # ---------------------------------------------------------------
    # BAN
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="ban", description="Ban một thành viên khỏi server")
    @app_commands.describe(member="Thành viên cần ban", reason="Lý do ban", delete_days="Xoá tin nhắn trong bao nhiêu ngày gần đây (0-7)")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, delete_days: app_commands.Range[int, 0, 7] = 0, *, reason: str = "Không có lý do"):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            embed = mod_embed(f"{e('error')} Không thể ban", "Bạn không thể ban người có vai trò cao hơn hoặc bằng bạn.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        await member.ban(reason=f"{reason} | Bởi {ctx.author}", delete_message_days=delete_days)
        embed = mod_embed(f"{e('ban')} Đã ban thành viên", f"**Thành viên:** {member.mention}\n**Lý do:** {reason}\n**Người thực hiện:** {ctx.author.mention}", discord.Color.red())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "ban")

    # ---------------------------------------------------------------
    # UNBAN
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="unban", description="Gỡ ban cho một user bằng ID")
    @app_commands.describe(user_id="ID của user cần gỡ ban", reason="Lý do gỡ ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: str, *, reason: str = "Không có lý do"):
        try:
            user = await self.bot.fetch_user(int(user_id))
            await ctx.guild.unban(user, reason=f"{reason} | Bởi {ctx.author}")
        except (ValueError, discord.NotFound):
            embed = mod_embed(f"{e('error')} Lỗi", "Không tìm thấy user với ID này trong danh sách ban.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        embed = mod_embed(f"{e('unban')} Đã gỡ ban", f"**Thành viên:** {user.mention}\n**Lý do:** {reason}", discord.Color.green())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "unban")

    # ---------------------------------------------------------------
    # MUTE (Timeout)
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="mute", description="Timeout (mute) một thành viên trong X phút")
    @app_commands.describe(member="Thành viên cần mute", minutes="Số phút mute (mặc định 10)", reason="Lý do mute")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, minutes: app_commands.Range[int, 1, 40320] = 10, *, reason: str = "Không có lý do"):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            embed = mod_embed(f"{e('error')} Không thể mute", "Bạn không thể mute người có vai trò cao hơn hoặc bằng bạn.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)

        await member.timeout(timedelta(minutes=minutes), reason=f"{reason} | Bởi {ctx.author}")
        embed = mod_embed(f"{e('mute')} Đã mute thành viên", f"**Thành viên:** {member.mention}\n**Thời gian:** {minutes} phút\n**Lý do:** {reason}", discord.Color.dark_grey())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "mute")

    # ---------------------------------------------------------------
    # UNMUTE
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="unmute", description="Gỡ timeout (mute) cho một thành viên")
    @app_commands.describe(member="Thành viên cần gỡ mute")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None, reason=f"Gỡ mute bởi {ctx.author}")
        embed = mod_embed(f"{e('unmute')} Đã gỡ mute", f"**Thành viên:** {member.mention}", discord.Color.green())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "unmute")

    # ---------------------------------------------------------------
    # WARN
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="warn", description="Cảnh báo một thành viên")
    @app_commands.describe(member="Thành viên cần cảnh báo", reason="Lý do cảnh báo")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "Không có lý do"):
        total = add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        embed = mod_embed(f"{e('warn')} Đã cảnh báo thành viên", f"**Thành viên:** {member.mention}\n**Lý do:** {reason}\n**Tổng số cảnh báo:** {total}", discord.Color.gold())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "warn")

        try:
            await member.send(f"{e('warn')} Bạn vừa bị cảnh báo tại **{ctx.guild.name}**.\nLý do: {reason}")
        except discord.Forbidden:
            pass

    @commands.hybrid_command(name="warnings", description="Xem danh sách cảnh báo của một thành viên")
    @app_commands.describe(member="Thành viên cần xem")
    @commands.has_permissions(moderate_members=True)
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        warns = get_warnings(ctx.guild.id, member.id)
        if not warns:
            embed = mod_embed(f"{e('info')} Không có cảnh báo", f"{member.mention} chưa có cảnh báo nào.", discord.Color.green())
            return await ctx.send(embed=embed)

        desc = "\n".join(
            f"**#{i+1}** — {w['reason']} (bởi <@{w['moderator_id']}>)"
            for i, w in enumerate(warns)
        )
        embed = mod_embed(f"{e('warn')} Cảnh báo của {member.display_name}", desc, discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarn", description="Xoá toàn bộ cảnh báo của một thành viên")
    @app_commands.describe(member="Thành viên cần xoá cảnh báo")
    @commands.has_permissions(moderate_members=True)
    async def clearwarn(self, ctx: commands.Context, member: discord.Member):
        count = clear_warnings(ctx.guild.id, member.id)
        embed = mod_embed(f"{e('success')} Đã xoá cảnh báo", f"Đã xoá {count} cảnh báo của {member.mention}.", discord.Color.green())
        await ctx.send(embed=embed)
        await self.react_ok(ctx)

    # ---------------------------------------------------------------
    # PURGE
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="purge", description="Xoá hàng loạt tin nhắn trong kênh")
    @app_commands.describe(amount="Số lượng tin nhắn cần xoá (1-100)")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: app_commands.Range[int, 1, 100]):
        await ctx.defer(ephemeral=True)
        deleted = await ctx.channel.purge(limit=amount)
        embed = mod_embed(f"{e('purge')} Đã dọn tin nhắn", f"Đã xoá **{len(deleted)}** tin nhắn.", discord.Color.blurple())
        await ctx.send(embed=embed, ephemeral=True, delete_after=5)

    # ---------------------------------------------------------------
    # LOCK / UNLOCK
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="lock", description="Khoá kênh hiện tại (chặn @everyone gửi tin nhắn)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, *, reason: str = "Không có lý do"):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite, reason=reason)
        embed = mod_embed(f"{e('lock')} Kênh đã bị khoá", f"**Lý do:** {reason}", discord.Color.dark_red())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "lock")

    @commands.hybrid_command(name="unlock", description="Mở khoá kênh hiện tại")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        embed = mod_embed(f"{e('unlock')} Kênh đã được mở khoá", "", discord.Color.green())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "unlock")

    # ---------------------------------------------------------------
    # SLOWMODE
    # ---------------------------------------------------------------
    @commands.hybrid_command(name="slowmode", description="Bật/tắt slowmode cho kênh (giây)")
    @app_commands.describe(seconds="Số giây chờ giữa các tin nhắn, 0 để tắt")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(self, ctx: commands.Context, seconds: app_commands.Range[int, 0, 21600]):
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            embed = mod_embed(f"{e('slowmode')} Đã tắt slowmode", "", discord.Color.green())
        else:
            embed = mod_embed(f"{e('slowmode')} Đã bật slowmode", f"**{seconds} giây** giữa mỗi tin nhắn.", discord.Color.blurple())
        await ctx.send(embed=embed)
        await self.react_ok(ctx, "slowmode")

    # ---------------------------------------------------------------
    # Xử lý lỗi chung cho cog này
    # ---------------------------------------------------------------
    @kick.error
    @ban.error
    @unban.error
    @mute.error
    @unmute.error
    @warn.error
    @warnings.error
    @clearwarn.error
    @purge.error
    @lock.error
    @unlock.error
    @slowmode.error
    async def mod_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Bạn không có quyền để dùng lệnh này.", discord.Color.red())
        elif isinstance(error, commands.BotMissingPermissions):
            embed = mod_embed(f"{e('error')} Bot thiếu quyền", "Bot cần thêm quyền để thực hiện hành động này.", discord.Color.red())
        elif isinstance(error, commands.MemberNotFound):
            embed = mod_embed(f"{e('error')} Không tìm thấy", "Không tìm thấy thành viên này.", discord.Color.red())
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = mod_embed(f"{e('error')} Thiếu tham số", f"Bạn cần cung cấp: `{error.param.name}`", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Đã xảy ra lỗi", f"```{error}```", discord.Color.red())

        if ctx.interaction:
            if ctx.interaction.response.is_done():
                await ctx.interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await ctx.interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await ctx.send(embed=embed)
            if ctx.message:
                try:
                    await ctx.message.add_reaction(e("error"))
                except discord.HTTPException:
                    pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
