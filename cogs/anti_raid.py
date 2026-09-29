import time
import difflib
from collections import defaultdict, deque

import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.guild_config import get_guild_config, set_guild_config, is_autodefense_on

# Tên các bot mod/security phổ biến hay bị giả mạo trong các đợt raid
KNOWN_BOT_NAMES = [
    "dyno", "mee6", "wick", "securitybot", "security bot", "carl-bot",
    "carlbot", "probot", "arcane", "ticket tool", "giveaway bot",
]


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


def name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


class AntiRaid(commands.Cog):
    """
    Phát hiện raid (join ồ ạt) và bot giả dạng, kèm chế độ auto-defense 24/7 bật/tắt theo lệnh.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Lưu thời điểm join gần nhất theo từng guild để tính tốc độ join
        self._join_times: dict[int, deque] = defaultdict(deque)
        # Chống spam cảnh báo lock lặp lại liên tục
        self._locked_recently: set[int] = set()

    async def _log(self, guild: discord.Guild, embed: discord.Embed):
        cfg = get_guild_config(guild.id)
        channel_id = cfg.get("mod_log_channel")
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if channel:
            try:
                await channel.send(embed=embed)
            except discord.HTTPException:
                pass

    # -----------------------------------------------------------------
    # Phát hiện bot giả dạng khi có bot mới join
    # -----------------------------------------------------------------
    def _looks_like_fake_bot(self, member: discord.Member, trusted_ids: list) -> str | None:
        if member.id in trusted_ids:
            return None
        # Bot có tick "verified bot" của Discord thường an toàn hơn nhiều
        if member.public_flags.verified_bot:
            return None

        for known in KNOWN_BOT_NAMES:
            score = name_similarity(member.name, known)
            if score >= 0.75:
                return f"Tên **{member.name}** giống **{known}** ({int(score*100)}%) nhưng không có tick verified bot."

        account_age_days = (discord.utils.utcnow() - member.created_at).days
        if account_age_days < 3:
            return f"Tài khoản bot vừa tạo {account_age_days} ngày trước — nghi ngờ bot spam/raid."

        return None

    # -----------------------------------------------------------------
    # Sự kiện: có thành viên (hoặc bot) mới join
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        cfg = get_guild_config(guild.id)

        # --- 1. Kiểm tra bot giả dạng ---
        if member.bot:
            reason = self._looks_like_fake_bot(member, cfg.get("trusted_bot_ids", []))
            if reason:
                embed = mod_embed(
                    f"{e('fakebot')} Nghi ngờ bot giả dạng",
                    f"**Bot:** {member.mention} (`{member.id}`)\n**Lý do:** {reason}",
                    discord.Color.red(),
                )
                if cfg.get("autodefense"):
                    try:
                        await member.kick(reason="Auto-defense: nghi ngờ bot giả dạng")
                        embed.add_field(name="Hành động", value=f"{e('kick')} Đã tự động kick (autodefense đang bật)")
                    except discord.Forbidden:
                        embed.add_field(name="Hành động", value=f"{e('error')} Không thể kick — thiếu quyền")
                else:
                    embed.add_field(name="Hành động", value=f"{e('info')} Chỉ cảnh báo (autodefense đang tắt, dùng `?autodefense on` để tự xử lý)")
                await self._log(guild, embed)
            return  # bot join thì không tính vào raid join-rate của member thường

        # --- 2. Kiểm tra raid join ồ ạt (chỉ tính member thường) ---
        if not cfg.get("autodefense"):
            return

        now = time.time()
        window = cfg.get("join_window_seconds", 10)
        threshold = cfg.get("join_threshold", 6)

        dq = self._join_times[guild.id]
        dq.append(now)
        while dq and now - dq[0] > window:
            dq.popleft()

        if len(dq) >= threshold and guild.id not in self._locked_recently:
            self._locked_recently.add(guild.id)
            await self._trigger_lockdown(guild, len(dq), window)

    async def _trigger_lockdown(self, guild: discord.Guild, join_count: int, window: int):
        embed = mod_embed(
            f"{e('raid')} PHÁT HIỆN RAID — Đã tự động khoá server",
            f"**{join_count}** thành viên join trong **{window} giây**.\n"
            f"Đã set verification level lên `high` để chặn tài khoản mới/spam.\n"
            f"Dùng `?autodefense status` để xem, hoặc hạ verification level thủ công khi ổn.",
            discord.Color.dark_red(),
        )
        try:
            await guild.edit(verification_level=discord.VerificationLevel.high, reason="Auto-defense: phát hiện raid")
        except discord.Forbidden:
            embed.add_field(name=f"{e('error')} Lỗi", value="Bot thiếu quyền Manage Server để tự khoá.")

        await self._log(guild, embed)

        # Cho phép trigger lại sau 60s để không bị kẹt trạng thái mãi
        async def _reset():
            import asyncio
            await asyncio.sleep(60)
            self._locked_recently.discard(guild.id)

        self.bot.loop.create_task(_reset())

    # -----------------------------------------------------------------
    # Lệnh: bật/tắt auto-defense 24/7
    # -----------------------------------------------------------------
    @commands.hybrid_group(name="autodefense", description="Bật/tắt chế độ tự động phòng vệ 24/7 (anti-raid + anti-fakebot)", fallback="status")
    @commands.has_permissions(administrator=True)
    async def autodefense(self, ctx: commands.Context):
        cfg = get_guild_config(ctx.guild.id)
        state = "BẬT" if cfg.get("autodefense") else "TẮT"
        icon = "shield" if cfg.get("autodefense") else "info"
        modlog_id = cfg.get("mod_log_channel")
        modlog_text = f"<#{modlog_id}>" if modlog_id else "Chưa đặt (dùng `?setmodlog #kênh`)"
        embed = mod_embed(
            f"{e(icon)} Trạng thái Auto-Defense",
            f"**Trạng thái:** `{state}`\n"
            f"**Ngưỡng raid:** {cfg.get('join_threshold')} người / {cfg.get('join_window_seconds')} giây\n"
            f"**Kênh mod-log:** {modlog_text}",
            discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @autodefense.command(name="on", description="Bật chế độ tự động phòng vệ 24/7")
    @commands.has_permissions(administrator=True)
    async def autodefense_on(self, ctx: commands.Context):
        set_guild_config(ctx.guild.id, autodefense=True)
        embed = mod_embed(f"{e('shield')} Đã BẬT Auto-Defense 24/7", "Bot sẽ tự động phát hiện raid (join ồ ạt) và bot giả dạng, tự xử lý ngay khi phát hiện.", discord.Color.green())
        await ctx.send(embed=embed)

    @autodefense.command(name="off", description="Tắt chế độ tự động phòng vệ 24/7")
    @commands.has_permissions(administrator=True)
    async def autodefense_off(self, ctx: commands.Context):
        set_guild_config(ctx.guild.id, autodefense=False)
        embed = mod_embed(f"{e('info')} Đã TẮT Auto-Defense", "Bot sẽ chỉ cảnh báo qua mod-log, không tự kick/khoá nữa.", discord.Color.greyple())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="setmodlog", description="Đặt kênh nhận cảnh báo raid / bot giả dạng")
    @app_commands.describe(channel="Kênh sẽ nhận cảnh báo")
    @commands.has_permissions(administrator=True)
    async def setmodlog(self, ctx: commands.Context, channel: discord.TextChannel):
        set_guild_config(ctx.guild.id, mod_log_channel=channel.id)
        embed = mod_embed(f"{e('success')} Đã đặt kênh mod-log", f"Cảnh báo raid / bot giả dạng sẽ gửi vào {channel.mention}.", discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="trustbot", description="Thêm 1 bot vào danh sách tin cậy (bỏ qua kiểm tra bot giả dạng)")
    @app_commands.describe(bot_member="Bot cần thêm vào whitelist")
    @commands.has_permissions(administrator=True)
    async def trustbot(self, ctx: commands.Context, bot_member: discord.Member):
        cfg = get_guild_config(ctx.guild.id)
        trusted = set(cfg.get("trusted_bot_ids", []))
        trusted.add(bot_member.id)
        set_guild_config(ctx.guild.id, trusted_bot_ids=list(trusted))
        embed = mod_embed(f"{e('success')} Đã thêm vào whitelist", f"{bot_member.mention} sẽ không bị kiểm tra bot giả dạng nữa.", discord.Color.green())
        await ctx.send(embed=embed)

    @autodefense_on.error
    @autodefense_off.error
    @setmodlog.error
    @trustbot.error
    async def raid_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Cần quyền Administrator để dùng lệnh này.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiRaid(bot))
