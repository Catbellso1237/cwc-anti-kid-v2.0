import re
import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.guild_config import get_guild_config, set_guild_config
from utils.storage import add_warning

INVITE_PATTERN = re.compile(
    r"(discord\.gg/|discord(?:app)?\.com/invite/)[a-zA-Z0-9\-]+", re.IGNORECASE
)
URL_PATTERN = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


def extract_domain(url: str) -> str:
    """Lấy domain gốc từ 1 URL, VD https://www.youtube.com/abc -> youtube.com"""
    domain = re.sub(r"^https?://", "", url, flags=re.IGNORECASE)
    domain = domain.split("/")[0].split("?")[0].lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


class AntiLink(commands.Cog):
    """Chặn spam link: invite Discord (mặc định) hoặc mọi link trừ whitelist."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _is_violation(self, content: str, cfg: dict) -> str | None:
        """Trả về lý do vi phạm nếu có, None nếu tin nhắn hợp lệ."""
        if INVITE_PATTERN.search(content):
            return "invite Discord server khác"

        if cfg.get("antilink_mode") == "all_links":
            urls = URL_PATTERN.findall(content)
            whitelist = set(cfg.get("antilink_whitelist_domains", []))
            for url in urls:
                domain = extract_domain(url)
                if domain not in whitelist and not any(domain.endswith("." + w) for w in whitelist):
                    return f"link ngoài whitelist (`{domain}`)"

        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        cfg = get_guild_config(message.guild.id)
        if not cfg.get("antilink_enabled"):
            return

        # Bypass: mod (có quyền Manage Messages) hoặc kênh nằm trong whitelist
        if message.author.guild_permissions.manage_messages:
            return
        if message.channel.id in cfg.get("antilink_whitelist_channels", []):
            return

        reason = self._is_violation(message.content, cfg)
        if not reason:
            return

        try:
            await message.delete()
        except discord.HTTPException:
            pass

        # Ghi nhận như 1 lần warn, tận dụng lại hệ thống warning có sẵn
        total = add_warning(message.guild.id, message.author.id, self.bot.user.id, f"Anti-link: {reason}")

        warn_embed = mod_embed(
            f"{e('link')} Đã xoá tin nhắn chứa link không hợp lệ",
            f"{message.author.mention}, tin nhắn của bạn chứa **{reason}** nên đã bị xoá.\n"
            f"Tổng số cảnh báo: **{total}**",
            discord.Color.orange(),
        )
        try:
            notice = await message.channel.send(embed=warn_embed)
            await notice.delete(delay=8)
        except discord.HTTPException:
            pass

        # Log vào mod-log nếu đã cấu hình
        log_channel_id = cfg.get("mod_log_channel")
        if log_channel_id:
            log_channel = message.guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = mod_embed(
                    f"{e('link')} Anti-link kích hoạt",
                    f"**Người dùng:** {message.author.mention} (`{message.author.id}`)\n"
                    f"**Kênh:** {message.channel.mention}\n"
                    f"**Lý do:** {reason}\n"
                    f"**Tổng cảnh báo:** {total}",
                    discord.Color.orange(),
                )
                try:
                    await log_channel.send(embed=log_embed)
                except discord.HTTPException:
                    pass

    # -----------------------------------------------------------------
    # Lệnh bật/tắt + cấu hình
    # -----------------------------------------------------------------
    @commands.hybrid_group(name="antilink", description="Bật/tắt và cấu hình chống spam link", fallback="status")
    @commands.has_permissions(administrator=True)
    async def antilink(self, ctx: commands.Context):
        cfg = get_guild_config(ctx.guild.id)
        state = "BẬT" if cfg.get("antilink_enabled") else "TẮT"
        mode = cfg.get("antilink_mode", "invite_only")
        mode_text = "Chỉ chặn invite Discord" if mode == "invite_only" else "Chặn mọi link trừ whitelist"
        whitelist_domains = cfg.get("antilink_whitelist_domains", [])
        whitelist_channels = cfg.get("antilink_whitelist_channels", [])

        embed = mod_embed(
            f"{e('link')} Trạng thái Anti-Link",
            f"**Trạng thái:** `{state}`\n"
            f"**Chế độ:** {mode_text}\n"
            f"**Domain whitelist:** {', '.join(whitelist_domains) if whitelist_domains else 'Chưa có'}\n"
            f"**Kênh miễn kiểm tra:** {', '.join(f'<#{c}>' for c in whitelist_channels) if whitelist_channels else 'Chưa có'}\n\n"
            f"Mod (có quyền Manage Messages) luôn được miễn kiểm tra.",
            discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @antilink.command(name="on", description="Bật chống spam link")
    @commands.has_permissions(administrator=True)
    async def antilink_on(self, ctx: commands.Context):
        set_guild_config(ctx.guild.id, antilink_enabled=True)
        embed = mod_embed(f"{e('success')} Đã bật Anti-Link", "Tin nhắn chứa link vi phạm sẽ tự động bị xoá + cảnh báo.", discord.Color.green())
        await ctx.send(embed=embed)

    @antilink.command(name="off", description="Tắt chống spam link")
    @commands.has_permissions(administrator=True)
    async def antilink_off(self, ctx: commands.Context):
        set_guild_config(ctx.guild.id, antilink_enabled=False)
        embed = mod_embed(f"{e('info')} Đã tắt Anti-Link", "", discord.Color.greyple())
        await ctx.send(embed=embed)

    @antilink.command(name="mode", description="Đổi chế độ: chỉ chặn invite, hoặc chặn mọi link trừ whitelist")
    @app_commands.describe(mode="invite_only = chỉ chặn invite Discord | all_links = chặn mọi link trừ whitelist")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Chỉ chặn invite Discord", value="invite_only"),
        app_commands.Choice(name="Chặn mọi link trừ whitelist", value="all_links"),
    ])
    @commands.has_permissions(administrator=True)
    async def antilink_mode(self, ctx: commands.Context, mode: str):
        if mode not in ("invite_only", "all_links"):
            embed = mod_embed(f"{e('error')} Sai giá trị", "Chỉ nhận `invite_only` hoặc `all_links`.", discord.Color.red())
            return await ctx.send(embed=embed, ephemeral=True)
        set_guild_config(ctx.guild.id, antilink_mode=mode)
        embed = mod_embed(f"{e('success')} Đã đổi chế độ Anti-Link", f"Chế độ hiện tại: `{mode}`", discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="antilinkwhitelist", description="Thêm/xoá domain được phép (dùng khi antilink mode = all_links)")
    @app_commands.describe(action="add hoặc remove", domain="Domain, VD: youtube.com")
    @app_commands.choices(action=[
        app_commands.Choice(name="Thêm", value="add"),
        app_commands.Choice(name="Xoá", value="remove"),
    ])
    @commands.has_permissions(administrator=True)
    async def antilinkwhitelist(self, ctx: commands.Context, action: str, domain: str):
        cfg = get_guild_config(ctx.guild.id)
        domains = set(cfg.get("antilink_whitelist_domains", []))
        domain = domain.lower()
        if domain.startswith("www."):
            domain = domain[4:]

        if action == "add":
            domains.add(domain)
        else:
            domains.discard(domain)

        set_guild_config(ctx.guild.id, antilink_whitelist_domains=list(domains))
        embed = mod_embed(f"{e('success')} Đã cập nhật whitelist", f"Domain whitelist hiện tại: {', '.join(domains) if domains else 'Trống'}", discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="antilinkchannel", description="Thêm/xoá kênh miễn kiểm tra anti-link")
    @app_commands.describe(action="add hoặc remove", channel="Kênh cần thêm/xoá")
    @app_commands.choices(action=[
        app_commands.Choice(name="Thêm", value="add"),
        app_commands.Choice(name="Xoá", value="remove"),
    ])
    @commands.has_permissions(administrator=True)
    async def antilinkchannel(self, ctx: commands.Context, action: str, channel: discord.TextChannel):
        cfg = get_guild_config(ctx.guild.id)
        channels = set(cfg.get("antilink_whitelist_channels", []))

        if action == "add":
            channels.add(channel.id)
        else:
            channels.discard(channel.id)

        set_guild_config(ctx.guild.id, antilink_whitelist_channels=list(channels))
        embed = mod_embed(f"{e('success')} Đã cập nhật kênh miễn kiểm tra", f"{channel.mention} đã được {'thêm vào' if action == 'add' else 'xoá khỏi'} danh sách miễn kiểm tra.", discord.Color.green())
        await ctx.send(embed=embed)

    @antilink_on.error
    @antilink_off.error
    @antilink_mode.error
    @antilinkwhitelist.error
    @antilinkchannel.error
    async def antilink_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Cần quyền Administrator để dùng lệnh này.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(AntiLink(bot))
