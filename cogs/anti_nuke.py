"""
Cog Anti-Nuke thật sự.

Mục tiêu: phát hiện và chặn kiểu tấn công "bot giả danh anti-nuke" -
tức là một bot/tài khoản được cấp quyền cao rồi âm thầm xóa kênh,
xóa role, ban/kick hàng loạt để phá server.

Cơ chế:
1. Lắng nghe audit log real-time (on_audit_log_entry_create) để bắt
   các hành động nguy hiểm ngay khi chúng xảy ra.
2. Đếm số hành động nguy hiểm của từng "kẻ thực hiện" (executor) trong
   một cửa sổ thời gian ngắn. Vượt ngưỡng -> coi là raid/nuke.
3. Nếu executor không nằm trong danh sách TRUSTED_IDS -> phản ứng ngay:
   - Tước toàn bộ role nguy hiểm (Administrator, Manage Server, ...)
   - Kick/ban executor nếu có thể
   - Khóa server tạm thời (lockdown role @everyone)
   - Gửi cảnh báo tới kênh log + webhook ngoài
4. Giám sát riêng việc cấp quyền Administrator: bất kỳ ai được cấp
   quyền Administrator mà không nằm trong whitelist sẽ bị tước quyền
   NGAY LẬP TỨC, không cần chờ đủ ngưỡng.
"""
from __future__ import annotations

import time
import logging
from collections import defaultdict, deque

import discord
from discord.ext import commands

from utils import antinuke_config as config

logger = logging.getLogger("anti_nuke")

# Các loại hành động audit log bị coi là "nguy hiểm" nếu làm hàng loạt
DANGEROUS_ACTIONS = {
    discord.AuditLogAction.channel_delete,
    discord.AuditLogAction.role_delete,
    discord.AuditLogAction.kick,
    discord.AuditLogAction.ban,
    discord.AuditLogAction.webhook_create,
    discord.AuditLogAction.webhook_update,
    discord.AuditLogAction.integration_create,
}


class AntiNuke(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # executor_id -> deque[timestamp] các hành động nguy hiểm gần đây
        self.action_log: dict[int, deque] = defaultdict(deque)
        # server đang trong trạng thái lockdown
        self.locked_guilds: set[int] = set()

    # ------------------------------------------------------------------
    # Tiện ích
    # ------------------------------------------------------------------

    def is_trusted(self, user_id: int) -> bool:
        return user_id in config.TRUSTED_IDS or user_id == (
            self.bot.owner_id or 0
        )

    async def get_log_channel(self, guild: discord.Guild):
        if config.LOG_CHANNEL_ID:
            ch = guild.get_channel(config.LOG_CHANNEL_ID)
            if ch:
                return ch
        return None

    async def send_alert(self, guild: discord.Guild, message: str):
        logger.warning(f"[{guild.name}] {message}")
        ch = await self.get_log_channel(guild)
        if ch:
            try:
                await ch.send(f"🚨 **CẢNH BÁO ANTI-NUKE** 🚨\n{message}")
            except discord.HTTPException:
                pass

        if config.ALERT_WEBHOOK_URL:
            try:
                webhook = discord.Webhook.from_url(
                    config.ALERT_WEBHOOK_URL, session=self.bot.http_session
                )
                await webhook.send(
                    f"🚨 [{guild.name}] {message}", username="Anti-Nuke Sentinel"
                )
            except Exception as e:
                logger.error(f"Không gửi được webhook cảnh báo: {e}")

    # ------------------------------------------------------------------
    # Phản ứng khi phát hiện kẻ tấn công
    # ------------------------------------------------------------------

    async def neutralize(self, guild: discord.Guild, user_id: int, reason: str):
        """Tước quyền, cấm, và khóa server để ngăn thiệt hại thêm."""
        member = guild.get_member(user_id)

        # 1) Tước mọi role nguy hiểm ngay lập tức
        if member:
            dangerous_roles = [
                r
                for r in member.roles
                if r.permissions.administrator
                or r.permissions.manage_guild
                or r.permissions.manage_roles
                or r.permissions.manage_channels
                or r.permissions.ban_members
                or r.permissions.kick_members
            ]
            if dangerous_roles:
                try:
                    await member.remove_roles(
                        *dangerous_roles, reason=f"Anti-Nuke: {reason}"
                    )
                except discord.HTTPException as e:
                    logger.error(f"Không thể tước role: {e}")

            # 2) Cấm khỏi server
            try:
                await guild.ban(
                    member, reason=f"Anti-Nuke: {reason}", delete_message_days=0
                )
            except discord.HTTPException as e:
                logger.error(f"Không thể ban executor: {e}")
        else:
            # Nếu là bot/user đã rời server hoặc không lấy được member object,
            # vẫn cố ban theo ID để chặn quay lại
            try:
                await guild.ban(
                    discord.Object(id=user_id),
                    reason=f"Anti-Nuke: {reason}",
                    delete_message_days=0,
                )
            except discord.HTTPException:
                pass

        await self.send_alert(
            guild,
            f"Đã trung hòa đối tượng `{user_id}` — lý do: {reason}. "
            f"Đã tước quyền và cấm khỏi server.",
        )

        await self.lockdown(guild)

    async def lockdown(self, guild: discord.Guild):
        """Khóa tạm thời quyền gửi tin/tạo thay đổi của @everyone để chặn thiệt hại lan rộng."""
        if guild.id in self.locked_guilds:
            return
        self.locked_guilds.add(guild.id)

        everyone = guild.default_role
        try:
            overwrite = everyone.permissions
            overwrite.update(
                send_messages=False,
                create_instant_invite=False,
            )
            await guild.default_role.edit(
                permissions=overwrite, reason="Anti-Nuke: lockdown tự động"
            )
            await self.send_alert(
                guild,
                "Server đã được KHÓA TẠM THỜI (chặn gửi tin/tạo invite mới). "
                "Dùng `?antinukeunlock` sau khi đã kiểm tra an toàn.",
            )
        except discord.HTTPException as e:
            logger.error(f"Không thể lockdown: {e}")

    # ------------------------------------------------------------------
    # Lắng nghe audit log real-time
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry: discord.AuditLogEntry):
        guild = entry.guild
        executor = entry.user
        if executor is None:
            return

        # Không bao giờ tự chặn chính bot này
        if executor.id == self.bot.user.id:
            return

        # Đã tin tưởng thì bỏ qua
        if self.is_trusted(executor.id):
            return

        # --- Giám sát riêng: cấp quyền Administrator cho ai đó ---
        if entry.action == discord.AuditLogAction.member_role_update:
            target = entry.target
            after_roles = getattr(entry.after, "roles", None)
            if after_roles:
                gained_admin = any(r.permissions.administrator for r in after_roles)
                if gained_admin and target and not self.is_trusted(target.id):
                    await self.neutralize(
                        guild,
                        executor.id,
                        f"Cấp quyền Administrator trái phép cho <@{target.id}>",
                    )
                    return

        if entry.action == discord.AuditLogAction.bot_add:
            target = entry.target
            if target and not self.is_trusted(executor.id):
                await self.send_alert(
                    guild,
                    f"⚠️ Bot mới `{target}` vừa được thêm vào server bởi "
                    f"<@{executor.id}>. Hãy kiểm tra quyền của bot này ngay.",
                )

        # --- Đếm hành động nguy hiểm theo cửa sổ thời gian ---
        if entry.action in DANGEROUS_ACTIONS:
            now = time.time()
            dq = self.action_log[executor.id]
            dq.append(now)
            while dq and now - dq[0] > config.ACTION_WINDOW_SECONDS:
                dq.popleft()

            if len(dq) >= config.ACTION_THRESHOLD:
                await self.neutralize(
                    guild,
                    executor.id,
                    f"Thực hiện {len(dq)} hành động nguy hiểm "
                    f"({entry.action.name}) trong {config.ACTION_WINDOW_SECONDS}s",
                )
                dq.clear()

    # ------------------------------------------------------------------
    # Lệnh quản trị thủ công (chỉ dành cho người trong whitelist)
    # ------------------------------------------------------------------

    def trusted_only():
        async def predicate(ctx: commands.Context):
            return ctx.bot.get_cog("AntiNuke").is_trusted(ctx.author.id)

        return commands.check(predicate)

    @commands.command(name="antinukeunlock", aliases=["nukeunlock"])
    @trusted_only()
    async def unlock(self, ctx: commands.Context):
        """Mở khóa server (lockdown do Anti-Nuke kích hoạt) sau khi đã kiểm tra an toàn.

        Lưu ý: đây KHÁC với lệnh `unlock` trong cogs/moderation.py (lệnh đó chỉ mở khóa
        1 kênh cụ thể). Lệnh này mở khóa toàn bộ server sau khi Anti-Nuke tự động lockdown.
        """
        guild = ctx.guild
        everyone = guild.default_role
        overwrite = everyone.permissions
        overwrite.update(send_messages=True, create_instant_invite=True)
        await everyone.edit(permissions=overwrite, reason="Anti-Nuke: mở khóa thủ công")
        self.locked_guilds.discard(guild.id)
        await ctx.send("✅ Đã mở khóa server.")

    @commands.command(name="trust")
    @trusted_only()
    async def trust_add(self, ctx: commands.Context, user_id: int):
        """Thêm ID vào danh sách tin tưởng (chỉ trong bộ nhớ, sửa .env để lưu vĩnh viễn)."""
        config.TRUSTED_IDS.add(user_id)
        await ctx.send(
            f"✅ Đã thêm `{user_id}` vào danh sách tin tưởng tạm thời. "
            f"Nhớ cập nhật TRUSTED_IDS trong .env để giữ sau khi restart."
        )

    @commands.command(name="status")
    async def status(self, ctx: commands.Context):
        """Xem trạng thái bảo vệ hiện tại của server."""
        locked = "🔒 ĐANG KHÓA" if ctx.guild.id in self.locked_guilds else "🔓 Bình thường"
        await ctx.send(
            f"**Trạng thái Anti-Nuke:** {locked}\n"
            f"**Số ID tin tưởng:** {len(config.TRUSTED_IDS)}\n"
            f"**Ngưỡng cảnh báo:** {config.ACTION_THRESHOLD} hành động / "
            f"{config.ACTION_WINDOW_SECONDS}s"
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiNuke(bot))
