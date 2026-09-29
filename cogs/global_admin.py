import os
from typing import Union
import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.global_data import (
    add_global_ban, remove_global_ban, is_globally_banned,
    get_global_ban_info, list_global_bans,
)
from utils.guild_config import get_guild_config, set_guild_config
from utils.owner_check import hard_owner_check


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class GlobalAdmin(commands.Cog):
    """
    Lệnh cấp CHỦ BOT (owner), áp dụng xuyên suốt mọi server bot đang có mặt:
    - Global ban 1 UID trên tất cả server cùng lúc
    - Gửi announcement (thông báo) tới tất cả server đã add bot

    Chỉ chủ sở hữu ứng dụng bot (owner trong Developer Portal) mới dùng được các lệnh global*.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===================================================================
    # GLOBAL BAN — ban 1 UID trên toàn bộ server bot đang có mặt
    # ===================================================================
    @commands.command(name="globalban", description="[Chủ bot] Ban 1 UID trên TẤT CẢ server bot đang có mặt")
    @app_commands.describe(user_id="ID của user cần ban toàn cục", reason="Lý do")
    @hard_owner_check()
    async def globalban(self, ctx: commands.Context, user_id: str, *, reason: str = "Không có lý do"):
        try:
            uid = int(user_id)
        except ValueError:
            embed = mod_embed(f"{e('error')} UID không hợp lệ", "UID phải là số.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

        if ctx.interaction:
            await ctx.defer()

        add_global_ban(uid, reason, ctx.author.id)

        success, failed = 0, 0
        for guild in self.bot.guilds:
            try:
                await guild.ban(discord.Object(id=uid), reason=f"Global ban bởi {ctx.author} | {reason}")
                success += 1
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

        embed = mod_embed(
            f"{e('ban')} Đã Global Ban UID `{uid}`",
            f"**Lý do:** {reason}\n"
            f"**Ban thành công:** {success}/{len(self.bot.guilds)} server\n"
            f"**Thất bại (thiếu quyền/lỗi):** {failed} server\n\n"
            f"Từ giờ nếu UID này cố join lại bất kỳ server nào có bot, sẽ **tự động bị ban lại ngay lập tức**, "
            f"và nếu bot được add vào server mới, UID này cũng bị ban ngay tại server đó.",
            discord.Color.dark_red(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="globalunban", description="[Chủ bot] Gỡ global ban cho 1 UID")
    @app_commands.describe(user_id="ID của user cần gỡ global ban")
    @hard_owner_check()
    async def globalunban(self, ctx: commands.Context, user_id: str):
        try:
            uid = int(user_id)
        except ValueError:
            embed = mod_embed(f"{e('error')} UID không hợp lệ", "UID phải là số.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

        if not remove_global_ban(uid):
            embed = mod_embed(f"{e('info')} Không có trong danh sách", f"UID `{uid}` hiện không nằm trong global ban list.", discord.Color.blurple())
            return await ctx.send(embed=embed)

        if ctx.interaction:
            await ctx.defer()

        success = 0
        for guild in self.bot.guilds:
            try:
                await guild.unban(discord.Object(id=uid), reason=f"Global unban bởi {ctx.author}")
                success += 1
            except discord.HTTPException:
                pass

        embed = mod_embed(
            f"{e('unban')} Đã gỡ Global Ban UID `{uid}`",
            f"Đã gỡ ban thành công tại {success} server (những server không có ban UID này thì bỏ qua).",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="globalbanlist", description="[Chủ bot] Xem danh sách UID đang bị global ban")
    @hard_owner_check()
    async def globalbanlist(self, ctx: commands.Context):
        bans = list_global_bans()
        if not bans:
            embed = mod_embed(f"{e('info')} Danh sách trống", "Chưa có UID nào bị global ban.", discord.Color.blurple())
            return await ctx.send(embed=embed)

        lines = [f"`{uid}` — {info.get('reason', '?')}" for uid, info in list(bans.items())[:25]]
        embed = mod_embed(f"{e('ban')} Global Ban List ({len(bans)} UID)", "\n".join(lines), discord.Color.red())
        if len(bans) > 25:
            embed.set_footer(text=f"Chỉ hiện 25/{len(bans)} UID đầu tiên")
        await ctx.send(embed=embed)

    # -------------------------------------------------------------
    # Tự động thực thi global ban list — không cần gọi lệnh gì thêm
    # -------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """UID nào nằm trong global ban list mà cố join server có bot -> tự ban ngay."""
        if is_globally_banned(member.id):
            info = get_global_ban_info(member.id)
            try:
                await member.guild.ban(member, reason=f"Global ban: {info.get('reason', '?')}")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Bot vừa được add vào server mới -> tự áp toàn bộ global ban list vào server đó luôn."""
        bans = list_global_bans()
        for uid_str, info in bans.items():
            try:
                await guild.ban(discord.Object(id=int(uid_str)), reason=f"Đồng bộ global ban khi bot join server mới: {info.get('reason', '?')}")
            except discord.HTTPException:
                pass

    # ===================================================================
    # SERVER MANAGEMENT — tạo hàng loạt kênh + đổi tên server (chỉ owner)
    # ===================================================================
    @commands.command(name="createchannels", description="[Chủ bot] Tạo hàng loạt kênh trong server hiện tại")
    @app_commands.describe(
        amount="Số lượng kênh cần tạo (tối đa 100 mỗi lần)",
        name="Tên gốc cho kênh (tự đánh số nếu tạo nhiều hơn 1)",
        channel_type="text hoặc voice",
    )
    @app_commands.choices(channel_type=[
        app_commands.Choice(name="Text", value="text"),
        app_commands.Choice(name="Voice", value="voice"),
    ])
    @hard_owner_check()
    @commands.bot_has_permissions(manage_channels=True)
    async def createchannels(self, ctx: commands.Context, amount: int, name: str = "channel", channel_type: str = "text"):
        if not 1 <= amount <= 100:
            embed = mod_embed(f"{e('error')} Sai giá trị", "Số lượng kênh phải từ 1 đến 100.", discord.Color.red())
            return await ctx.send(embed=embed)
        if ctx.interaction:
            await ctx.defer()

        guild = ctx.guild
        created = []
        for i in range(1, amount + 1):
            cname = name if amount == 1 else f"{name}-{i}"
            try:
                if channel_type.lower() == "voice":
                    ch = await guild.create_voice_channel(cname, reason=f"Tạo hàng loạt bởi {ctx.author}")
                else:
                    ch = await guild.create_text_channel(cname, reason=f"Tạo hàng loạt bởi {ctx.author}")
                created.append(ch)
            except discord.HTTPException:
                break

        embed = mod_embed(
            f"{e('success')} Đã tạo {len(created)}/{amount} kênh",
            f"**Loại:** {channel_type}\n**Tên gốc:** `{name}`" + (f"\n\n{e('error')} Dừng sớm do lỗi API (rate limit hoặc đạt giới hạn kênh của server)." if len(created) < amount else ""),
            discord.Color.green() if len(created) == amount else discord.Color.orange(),
        )
        await ctx.send(embed=embed)

    @commands.command(name="deletechannel", description="[Chủ bot] Xoá 1 kênh cụ thể trực tiếp (không cần khớp tên)")
    @app_commands.describe(channel="Kênh cần xoá (chọn trực tiếp, không cần gõ tên/từ khoá)")
    @hard_owner_check()
    @commands.bot_has_permissions(manage_channels=True)
    async def deletechannel(self, ctx: commands.Context, channel: Union[discord.TextChannel, discord.VoiceChannel, discord.CategoryChannel]):
        if channel.id == ctx.channel.id:
            embed = mod_embed(
                f"{e('error')} Không thể xoá",
                "Không thể xoá kênh đang gõ lệnh này (sẽ mất phản hồi giữa chừng). Hãy gọi lệnh này ở kênh khác.",
                discord.Color.red(),
            )
            return await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

        name = channel.name
        try:
            await channel.delete(reason=f"Xoá trực tiếp bởi {ctx.author}")
        except discord.HTTPException as ex:
            embed = mod_embed(f"{e('error')} Không xoá được", f"```{ex}```", discord.Color.red())
            return await ctx.send(embed=embed)

        embed = mod_embed(f"{e('success')} Đã xoá kênh", f"Đã xoá kênh `{name}` (`{channel.id}`).", discord.Color.green())
        await ctx.send(embed=embed)

    @commands.command(name="deletechannels", description="[Chủ bot] Xoá hàng loạt kênh theo tên trong server hiện tại")
    @app_commands.describe(
        name_contains="Từ khoá trong tên kênh cần xoá (khớp gần đúng, không phân biệt hoa thường)",
        amount="Số lượng tối đa cần xoá (mặc định 50, tối đa 50)",
    )
    @hard_owner_check()
    @commands.bot_has_permissions(manage_channels=True)
    async def deletechannels(self, ctx: commands.Context, name_contains: str, amount: int = 50):
        if not 1 <= amount <= 50:
            embed = mod_embed(f"{e('error')} Sai giá trị", "Số lượng kênh phải từ 1 đến 50.", discord.Color.red())
            return await ctx.send(embed=embed)
        if ctx.interaction:
            await ctx.defer()

        guild = ctx.guild
        keyword = name_contains.lower()
        # Bỏ qua kênh hiện tại đang gõ lệnh để tránh tự cắt đứt phản hồi giữa chừng
        matches = [
            ch for ch in guild.channels
            if keyword in ch.name.lower() and ch.id != ctx.channel.id
        ][:amount]

        if not matches:
            embed = mod_embed(
                f"{e('info')} Không tìm thấy kênh nào",
                f"Không có kênh nào (ngoài kênh hiện tại) chứa từ khoá `{name_contains}` trong tên.",
                discord.Color.blurple(),
            )
            return await ctx.send(embed=embed)

        deleted_names = []
        for ch in matches:
            try:
                deleted_names.append(ch.name)
                await ch.delete(reason=f"Xoá hàng loạt bởi {ctx.author}")
            except discord.HTTPException:
                deleted_names.pop()
                continue

        preview = ", ".join(f"`{n}`" for n in deleted_names[:10])
        if len(deleted_names) > 10:
            preview += f" ... (+{len(deleted_names) - 10} kênh khác)"

        embed = mod_embed(
            f"{e('success')} Đã xoá {len(deleted_names)}/{len(matches)} kênh khớp từ khoá `{name_contains}`",
            preview if preview else "Không xoá được kênh nào (có thể do lỗi quyền/API).",
            discord.Color.green() if len(deleted_names) == len(matches) else discord.Color.orange(),
        )
        embed.set_footer(text="Kênh hiện tại (nơi gõ lệnh) luôn được bỏ qua để tránh mất phản hồi giữa chừng.")
        await ctx.send(embed=embed)

    @commands.command(name="renameserver", description="[Chủ bot] Đổi tên server hiện tại")
    @app_commands.describe(new_name="Tên mới cho server")
    @hard_owner_check()
    @commands.bot_has_permissions(manage_guild=True)
    async def renameserver(self, ctx: commands.Context, *, new_name: str):
        old_name = ctx.guild.name
        try:
            await ctx.guild.edit(name=new_name, reason=f"Đổi tên bởi chủ bot {ctx.author}")
        except discord.HTTPException as ex:
            embed = mod_embed(f"{e('error')} Không đổi được tên", f"```{ex}```\nDiscord giới hạn số lần đổi tên server trong 1 khoảng thời gian, thử lại sau nếu vừa đổi gần đây.", discord.Color.red())
            return await ctx.send(embed=embed)

        embed = mod_embed(
            f"{e('success')} Đã đổi tên server",
            f"**Trước:** {old_name}\n**Sau:** {new_name}",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)

    # ===================================================================
    # GLOBAL ANNOUNCEMENT — gửi thông báo tới tất cả server đã add bot
    # ===================================================================
    @commands.command(name="globalannounce", description="[Chủ bot] Gửi thông báo tới TẤT CẢ server đã add bot")
    @app_commands.describe(message="Nội dung thông báo")
    @hard_owner_check()
    async def globalannounce(self, ctx: commands.Context, *, message: str):
        if ctx.interaction:
            await ctx.defer()

        announce_embed = mod_embed("📢 Thông báo từ nhà phát triển bot", message, discord.Color.gold())
        announce_embed.set_footer(text="Thông báo tự động — gửi tới toàn bộ server đang dùng bot này")

        sent, skipped = 0, 0
        for guild in self.bot.guilds:
            cfg = get_guild_config(guild.id)
            channel = None
            channel_id = cfg.get("bot_announcement_channel")
            if channel_id:
                channel = guild.get_channel(channel_id)
            if channel is None:
                # Server chưa cấu hình kênh riêng -> thử gửi vào kênh hệ thống mặc định
                channel = guild.system_channel

            if channel is None:
                skipped += 1
                continue
            try:
                await channel.send(embed=announce_embed)
                sent += 1
            except discord.HTTPException:
                skipped += 1

        result = mod_embed(
            f"{e('success')} Đã gửi Global Announcement",
            f"**Gửi thành công:** {sent}/{len(self.bot.guilds)} server\n"
            f"**Bỏ qua (chưa cấu hình kênh hoặc không gửi được):** {skipped} server",
            discord.Color.green(),
        )
        await ctx.send(embed=result)

    @commands.hybrid_command(name="setbotannounce", description="Chọn kênh server này sẽ nhận thông báo từ chủ bot")
    @app_commands.describe(channel="Kênh sẽ nhận thông báo (update, bảo trì...) từ chủ bot")
    @commands.has_permissions(administrator=True)
    async def setbotannounce(self, ctx: commands.Context, channel: discord.TextChannel):
        set_guild_config(ctx.guild.id, bot_announcement_channel=channel.id)
        embed = mod_embed(
            f"{e('success')} Đã đặt kênh nhận thông báo",
            f"Server này sẽ nhận thông báo từ chủ bot (update, bảo trì...) tại {channel.mention}.",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)

    # -------------------------------------------------------------
    @globalban.error
    @globalunban.error
    @globalbanlist.error
    @createchannels.error
    @deletechannel.error
    @deletechannels.error
    @renameserver.error
    async def owner_only_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.BotMissingPermissions):
            embed = mod_embed(f"{e('error')} Bot thiếu quyền", f"Bot cần thêm quyền để thực hiện lệnh này: `{', '.join(error.missing_permissions)}`", discord.Color.red())
        elif isinstance(error, commands.CheckFailure):
            embed = mod_embed(f"{e('error')} Không có quyền", "Lệnh này chỉ dành riêng cho đúng UID đã cấu hình trong `BOT_OWNER_ID`.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

    @globalannounce.error
    async def globalannounce_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            embed = mod_embed(
                f"{e('error')} Không có quyền",
                "Lệnh `globalannounce` chỉ dành cho đúng 1 UID đã cấu hình trong `BOT_OWNER_ID` (biến môi trường / GitHub Secret), không phụ thuộc vào ai đang host bot.",
                discord.Color.red(),
            )
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

    @setbotannounce.error
    async def setbotannounce_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Cần quyền Administrator để đặt kênh này.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(GlobalAdmin(bot))
        
