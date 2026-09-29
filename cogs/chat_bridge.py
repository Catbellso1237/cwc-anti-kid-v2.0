import re
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.bridge_data import add_bridge, remove_bridge, get_bridge, list_bridges, get_filter_config, set_filter_config
from utils.owner_check import hard_owner_check

INVITE_PATTERN = re.compile(
    r"(discord\.gg/|discord(?:app)?\.com/invite/)[a-zA-Z0-9\-]+", re.IGNORECASE
)


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class ChatBridge(commands.Cog):
    """
    Cầu nối chat xuyên server: 1 kênh trong server này được nối trực tiếp với
    kênh tương ứng ở mọi server khác đã setup, dùng webhook để relay tin nhắn
    kèm đúng tên + avatar người gửi gốc.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    def cog_unload(self):
        if self.session and not self.session.closed:
            self.bot.loop.create_task(self.session.close())

    def _check_filter_violation(self, content: str) -> str | None:
        """Trả về lý do vi phạm nếu tin nhắn không được relay, None nếu hợp lệ."""
        cfg = get_filter_config()

        if cfg.get("block_invites", True) and INVITE_PATTERN.search(content):
            return "chứa invite link server khác"

        lowered = content.lower()
        for word in cfg.get("banned_words", []):
            if word.lower() in lowered:
                return "chứa từ ngữ không được phép trong cầu nối chat"

        return None

    # -----------------------------------------------------------------
    # Lệnh: auto setup cầu nối chat
    # -----------------------------------------------------------------
    @commands.hybrid_command(name="bridgesetup", description="Tự động thiết lập cầu nối chat với các server khác đang dùng bot")
    @app_commands.describe(channel="Kênh dùng làm cầu nối (để trống = dùng kênh hiện tại)")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_webhooks=True)
    async def bridgesetup(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        existing = get_bridge(ctx.guild.id)

        if existing:
            old_channel = ctx.guild.get_channel(existing["channel_id"])
            embed = mod_embed(
                f"{e('info')} Server này đã setup cầu nối rồi",
                f"Kênh hiện tại: {old_channel.mention if old_channel else '(kênh cũ đã bị xoá)'}\n"
                f"Dùng `bridgeoff` để huỷ trước, rồi chạy `bridgesetup` lại nếu muốn đổi kênh.",
                discord.Color.blurple(),
            )
            return await ctx.send(embed=embed)

        if ctx.interaction:
            await ctx.defer()

        webhook = await channel.create_webhook(name="Chat Bridge", reason=f"Auto setup bởi {ctx.author}")
        add_bridge(ctx.guild.id, channel.id, webhook.url)

        total_servers = len(list_bridges())
        embed = mod_embed(
            f"{e('bridge')} Đã thiết lập cầu nối chat",
            f"Kênh {channel.mention} giờ được nối với **{max(total_servers - 1, 0)}** server khác đang dùng cầu nối.\n"
            f"Mọi tin nhắn gõ trong kênh này sẽ hiện ở kênh cầu nối của các server kia, kèm tên + server gốc.\n\n"
            f"Dùng `bridgestatus` để xem trạng thái, `bridgeoff` để huỷ bất cứ lúc nào.",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bridgeoff", description="Huỷ cầu nối chat của server này")
    @commands.has_permissions(administrator=True)
    async def bridgeoff(self, ctx: commands.Context):
        removed = remove_bridge(ctx.guild.id)
        if not removed:
            embed = mod_embed(f"{e('info')} Chưa setup", "Server này chưa có cầu nối chat nào để huỷ.", discord.Color.blurple())
            return await ctx.send(embed=embed)

        embed = mod_embed(f"{e('success')} Đã huỷ cầu nối chat", "Server này sẽ không còn gửi/nhận tin nhắn cầu nối nữa. Webhook cũ có thể còn tồn tại trong kênh, xoá tay nếu muốn dọn sạch.", discord.Color.green())
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="bridgestatus", description="Xem trạng thái cầu nối chat của server này")
    async def bridgestatus(self, ctx: commands.Context):
        bridge = get_bridge(ctx.guild.id)
        total = len(list_bridges())

        if not bridge:
            embed = mod_embed(
                f"{e('info')} Chưa setup",
                f"Server này chưa tham gia cầu nối chat.\nHiện có **{total}** server khác đang dùng cầu nối. Chạy `bridgesetup` để tham gia.",
                discord.Color.blurple(),
            )
        else:
            channel = ctx.guild.get_channel(bridge["channel_id"])
            embed = mod_embed(
                f"{e('bridge')} Đang kết nối",
                f"**Kênh:** {channel.mention if channel else '(kênh cũ đã bị xoá, chạy lại `bridgesetup`)'}\n"
                f"**Tổng số server trong mạng lưới:** {total}",
                discord.Color.green(),
            )
        await ctx.send(embed=embed)

    # -----------------------------------------------------------------
    # Relay tin nhắn — không cần gọi lệnh gì thêm sau khi đã setup
    # -----------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        if not message.content and not message.attachments:
            return

        bridge = get_bridge(message.guild.id)
        if not bridge or message.channel.id != bridge["channel_id"]:
            return

        content = message.content
        if message.attachments:
            urls = "\n".join(a.url for a in message.attachments)
            content = f"{content}\n{urls}" if content else urls
        content = content.strip()
        if not content:
            return
        content = content[:2000]

        violation = self._check_filter_violation(content)
        if violation:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
            notice = mod_embed(
                f"{e('error')} Tin nhắn không được relay",
                f"{message.author.mention}, tin nhắn của bạn {violation} nên không được gửi qua cầu nối chat.",
                discord.Color.red(),
            )
            try:
                sent = await message.channel.send(embed=notice)
                await sent.delete(delay=8)
            except discord.HTTPException:
                pass
            return

        session = await self._get_session()
        username = f"{message.author.display_name} • {message.guild.name}"[:80]

        for guild_id_str, info in list_bridges().items():
            if int(guild_id_str) == message.guild.id:
                continue
            try:
                webhook = discord.Webhook.from_url(info["webhook_url"], session=session)
                await webhook.send(
                    content=content,
                    username=username,
                    avatar_url=message.author.display_avatar.url,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.NotFound, discord.HTTPException):
                continue

    # -----------------------------------------------------------------
    # Quản lý bộ lọc chung cho toàn mạng lưới cầu nối (chỉ chủ bot)
    # -----------------------------------------------------------------
    @commands.group(name="bridgefilter", description="[Chủ bot] Quản lý bộ lọc nội dung cho cầu nối chat", invoke_without_command=True)
    @hard_owner_check()
    async def bridgefilter(self, ctx: commands.Context):
        cfg = get_filter_config()
        words = cfg.get("banned_words", [])
        embed = mod_embed(
            f"{e('bridge')} Bộ lọc cầu nối chat",
            f"**Chặn invite link:** {'BẬT' if cfg.get('block_invites', True) else 'TẮT'}\n"
            f"**Từ cấm ({len(words)}):** {', '.join(f'`{w}`' for w in words) if words else 'Chưa có'}",
            discord.Color.blurple(),
        )
        await ctx.send(embed=embed)

    @bridgefilter.command(name="addword", description="Thêm từ cấm vào bộ lọc cầu nối chat")
    @app_commands.describe(word="Từ cần cấm")
    @hard_owner_check()
    async def bridgefilter_addword(self, ctx: commands.Context, word: str):
        cfg = get_filter_config()
        words = set(cfg.get("banned_words", []))
        words.add(word.lower())
        set_filter_config(banned_words=list(words))
        embed = mod_embed(f"{e('success')} Đã thêm từ cấm", f"Đã thêm `{word}` vào bộ lọc cầu nối chat.", discord.Color.green())
        await ctx.send(embed=embed)

    @bridgefilter.command(name="removeword", description="Xoá từ cấm khỏi bộ lọc cầu nối chat")
    @app_commands.describe(word="Từ cần xoá khỏi danh sách cấm")
    @hard_owner_check()
    async def bridgefilter_removeword(self, ctx: commands.Context, word: str):
        cfg = get_filter_config()
        words = set(cfg.get("banned_words", []))
        words.discard(word.lower())
        set_filter_config(banned_words=list(words))
        embed = mod_embed(f"{e('success')} Đã xoá từ cấm", f"Đã xoá `{word}` khỏi bộ lọc cầu nối chat.", discord.Color.green())
        await ctx.send(embed=embed)

    @bridgefilter.command(name="invites", description="Bật/tắt tự động chặn invite link trong cầu nối chat")
    @app_commands.describe(state="on hoặc off")
    @app_commands.choices(state=[
        app_commands.Choice(name="Bật", value="on"),
        app_commands.Choice(name="Tắt", value="off"),
    ])
    @hard_owner_check()
    async def bridgefilter_invites(self, ctx: commands.Context, state: str):
        set_filter_config(block_invites=(state == "on"))
        embed = mod_embed(f"{e('success')} Đã cập nhật", f"Chặn invite link trong cầu nối chat: `{state.upper()}`", discord.Color.green())
        await ctx.send(embed=embed)

    # -----------------------------------------------------------------
    @bridgesetup.error
    @bridgeoff.error
    async def bridge_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            embed = mod_embed(f"{e('error')} Không đủ quyền", "Cần quyền Administrator để dùng lệnh này.", discord.Color.red())
        elif isinstance(error, commands.BotMissingPermissions):
            embed = mod_embed(f"{e('error')} Bot thiếu quyền", "Bot cần quyền `Manage Webhooks` để tạo cầu nối.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

    @bridgefilter_addword.error
    @bridgefilter_removeword.error
    @bridgefilter_invites.error
    async def bridgefilter_error_handler(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            embed = mod_embed(f"{e('error')} Không có quyền", "Chỉ chủ bot mới chỉnh được bộ lọc chung của cầu nối chat.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChatBridge(bot))
        
