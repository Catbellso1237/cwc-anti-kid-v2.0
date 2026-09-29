"""
Cog Quản Lý Application Emoji (liên kết trực tiếp Discord Developer Portal).

"Application Emoji" là loại emoji gắn liền với chính con bot (application),
xuất hiện trong Discord Developer Portal -> ứng dụng của bạn -> mục "Emojis".
Khác với emoji server thường, loại này:
- Không thuộc về 1 server cụ thể (guild_id = 0) mà thuộc về bot.
- Bot có thể dùng emoji này trong tin nhắn ở BẤT KỲ server nào nó có mặt,
  kể cả server không có sẵn emoji đó.
- Quản lý qua API create/edit/delete_application_emoji — đúng loại emoji
  quản lý trong Developer Portal.

Cách dùng — CHỈ dùng prefix "?" và panel (không có lệnh con dạng text):
    ?emoji

Gõ đúng `?emoji` sẽ mở ra một bảng điều khiển (panel) với các nút bấm:
    ➕ Thêm       - mở form (modal) nhập Tên + URL ảnh để tạo emoji mới
    ✏️ Đổi tên    - chọn 1 emoji từ danh sách (select menu) rồi đổi tên
    🗑️ Xóa        - chọn 1 emoji rồi xác nhận xóa
    🔄 Làm mới    - tải lại danh sách emoji mới nhất từ Developer Portal
    ✖️ Đóng       - đóng panel

Toàn bộ thao tác sau lệnh `?emoji` đều thực hiện bằng nút bấm / menu chọn /
form nhập liệu của Discord — không cần gõ thêm lệnh text nào khác.

Quyền sử dụng: chỉ những ID trong TRUSTED_IDS (.env) hoặc chủ sở hữu bot,
vì Application Emoji ảnh hưởng tới TOÀN BỘ bot (dùng chung ở mọi server),
không giới hạn trong 1 server như emoji thường.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Optional

import discord
from discord.ext import commands

from utils import antinuke_config as config
from utils.owner_check import get_configured_owner_id

logger = logging.getLogger("emoji_manager")

# Tiền tố lệnh riêng cho panel emoji — trùng với NORMAL_PREFIX của bot chính,
# nhưng đây là 1 message-listener độc lập (không đi qua discord.ext.commands).
EMOJI_PREFIX = "?"
TRIGGER_WORDS = {"emoji", "emojis"}  # gõ "?emoji" hoặc "?emojis"

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{2,32}$")
MAX_IMAGE_BYTES = 256 * 1024  # Giới hạn 256KB giống guild emoji
ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif"}
MAX_SELECT_OPTIONS = 25  # Giới hạn cứng của Discord select menu


def is_authorized(bot: commands.Bot, user_id: int) -> bool:
    """Chỉ TRUSTED_IDS, BOT_OWNER_ID (.env), hoặc chủ sở hữu application mới được quản lý
    Application Emoji."""
    configured_owner = get_configured_owner_id()
    return (
        user_id in config.TRUSTED_IDS
        or user_id == (getattr(bot, "owner_id", None) or 0)
        or (configured_owner is not None and user_id == configured_owner)
    )


def emoji_display(e: discord.Emoji) -> str:
    """Chuỗi hiển thị emoji thật (nếu bot render được) kèm tên/ID."""
    tag = f"<{'a' if e.animated else ''}:{e.name}:{e.id}>"
    return f"{tag} `:{e.name}:` — `{e.id}`"


def build_list_embed(emojis: list[discord.Emoji]) -> discord.Embed:
    embed = discord.Embed(
        title="🧩 Application Emoji Panel",
        description=(
            "Quản lý emoji gắn với **bot** (Discord Developer Portal → Emojis).\n"
            "Dùng các nút bên dưới để thao tác."
        ),
        color=discord.Color.blurple(),
    )
    if not emojis:
        embed.add_field(
            name="Danh sách emoji", value="*(chưa có emoji nào)*", inline=False
        )
    else:
        shown = emojis[:50]
        lines = [emoji_display(e) for e in shown]
        text = "\n".join(lines)
        if len(emojis) > 50:
            text += f"\n... và {len(emojis) - 50} emoji khác"
        # Đề phòng vượt giới hạn 1024 ký tự / field, embed field description dùng chung
        if len(text) > 4000:
            text = text[:4000] + "\n... (rút gọn)"
        embed.add_field(
            name=f"Danh sách emoji ({len(emojis)})", value=text, inline=False
        )
    embed.set_footer(text="Application Emoji — dùng chung cho mọi server có bot")
    return embed


class ConfirmDeleteView(discord.ui.View):
    """Xác nhận xóa 1 emoji trước khi thực hiện — tránh xóa nhầm."""

    def __init__(self, panel: "EmojiPanelView", emoji: discord.Emoji):
        super().__init__(timeout=60)
        self.panel = panel
        self.emoji = emoji

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.client, interaction.user.id):
            await interaction.response.send_message(
                "❌ Bạn không có quyền dùng panel này.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Xác nhận xóa", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await self.emoji.delete(reason=f"Xóa qua panel bởi {interaction.user}")
            await interaction.response.edit_message(
                content=f"✅ Đã xóa emoji `:{self.emoji.name}:`.", embed=None, view=None
            )
        except discord.HTTPException as e:
            await interaction.response.edit_message(
                content=f"❌ Không thể xóa emoji: {e}", embed=None, view=None
            )
        await self.panel.refresh()
        self.stop()

    @discord.ui.button(label="Hủy", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="Đã hủy thao tác xóa.", embed=None, view=None
        )
        self.stop()


class RenameModal(discord.ui.Modal, title="Đổi tên Emoji"):
    new_name = discord.ui.TextInput(
        label="Tên mới (2-32 ký tự, chữ/số/_)",
        placeholder="vi_du_ten_emoji",
        min_length=2,
        max_length=32,
        required=True,
    )

    def __init__(self, panel: "EmojiPanelView", emoji: discord.Emoji):
        super().__init__()
        self.panel = panel
        self.emoji = emoji

    async def on_submit(self, interaction: discord.Interaction):
        name = str(self.new_name.value).strip()
        if not NAME_PATTERN.match(name):
            await interaction.response.send_message(
                "❌ Tên không hợp lệ. Chỉ dùng chữ, số, dấu gạch dưới, dài 2-32 ký tự.",
                ephemeral=True,
            )
            return
        try:
            await self.emoji.edit(name=name)
            await interaction.response.send_message(
                f"✅ Đã đổi tên emoji thành `:{name}:`.", ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Không thể đổi tên: {e}", ephemeral=True
            )
            return
        await self.panel.refresh()


class AddEmojiModal(discord.ui.Modal, title="Thêm Emoji Mới"):
    name = discord.ui.TextInput(
        label="Tên emoji (2-32 ký tự, chữ/số/_)",
        placeholder="ten_emoji_moi",
        min_length=2,
        max_length=32,
        required=True,
    )
    image_url = discord.ui.TextInput(
        label="URL ảnh (PNG/JPG/GIF, tối đa 256KB)",
        placeholder="https://example.com/anh.png",
        required=True,
    )

    def __init__(self, panel: "EmojiPanelView"):
        super().__init__()
        self.panel = panel

    async def on_submit(self, interaction: discord.Interaction):
        name = str(self.name.value).strip()
        url = str(self.image_url.value).strip()

        if not NAME_PATTERN.match(name):
            await interaction.response.send_message(
                "❌ Tên không hợp lệ. Chỉ dùng chữ, số, dấu gạch dưới, dài 2-32 ký tự.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        session = getattr(interaction.client, "http_session", None)
        if session is None:
            await interaction.followup.send(
                "❌ Lỗi nội bộ: không có phiên HTTP để tải ảnh.", ephemeral=True
            )
            return

        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send(
                        f"❌ Không tải được ảnh (HTTP {resp.status}). Kiểm tra lại URL.",
                        ephemeral=True,
                    )
                    return
                content_type = (resp.content_type or "").lower()
                if content_type not in ALLOWED_CONTENT_TYPES:
                    await interaction.followup.send(
                        f"❌ Định dạng ảnh không hỗ trợ (`{content_type}`). "
                        f"Chỉ hỗ trợ PNG, JPG, GIF.",
                        ephemeral=True,
                    )
                    return
                data = await resp.read()
        except Exception as e:
            await interaction.followup.send(f"❌ Lỗi khi tải ảnh: {e}", ephemeral=True)
            return

        if len(data) > MAX_IMAGE_BYTES:
            await interaction.followup.send(
                f"❌ Ảnh quá lớn ({len(data) / 1024:.1f}KB). Giới hạn tối đa 256KB.",
                ephemeral=True,
            )
            return

        try:
            new_emoji = await interaction.client.create_application_emoji(
                name=name, image=data
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Không thể tạo emoji: {e}", ephemeral=True
            )
            return

        await interaction.followup.send(
            f"✅ Đã tạo emoji mới: {emoji_display(new_emoji)}", ephemeral=True
        )
        await self.panel.refresh()


class EmojiSelect(discord.ui.Select):
    """Select menu liệt kê emoji để chọn thao tác (đổi tên / xóa)."""

    def __init__(self, panel: "EmojiPanelView", emojis: list[discord.Emoji], action: str):
        self.panel = panel
        self.action = action  # "rename" | "delete"
        options = [
            discord.SelectOption(
                label=e.name[:100],
                value=str(e.id),
                description=f"ID: {e.id}",
                emoji=discord.PartialEmoji(name=e.name, id=e.id, animated=e.animated),
            )
            for e in emojis[:MAX_SELECT_OPTIONS]
        ]
        placeholder = (
            "Chọn emoji để đổi tên..."
            if action == "rename"
            else "Chọn emoji để xóa..."
        )
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        emoji_id = int(self.values[0])
        try:
            emoji = await interaction.client.fetch_application_emoji(emoji_id)
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Không lấy được thông tin emoji: {e}", ephemeral=True
            )
            return

        if self.action == "rename":
            await interaction.response.send_modal(RenameModal(self.panel, emoji))
        else:  # delete
            confirm_embed = discord.Embed(
                title="⚠️ Xác nhận xóa emoji",
                description=f"Bạn có chắc muốn xóa {emoji_display(emoji)} không?",
                color=discord.Color.red(),
            )
            await interaction.response.send_message(
                embed=confirm_embed,
                view=ConfirmDeleteView(self.panel, emoji),
                ephemeral=True,
            )


class EmojiSelectView(discord.ui.View):
    """View tạm chứa select menu — dùng riêng cho bước chọn emoji (rename/delete)."""

    def __init__(self, panel: "EmojiPanelView", emojis: list[discord.Emoji], action: str):
        super().__init__(timeout=60)
        self.add_item(EmojiSelect(panel, emojis, action))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(interaction.client, interaction.user.id):
            await interaction.response.send_message(
                "❌ Bạn không có quyền dùng panel này.", ephemeral=True
            )
            return False
        return True


class EmojiPanelView(discord.ui.View):
    """Panel chính — toàn bộ thao tác quản lý Application Emoji qua nút bấm."""

    def __init__(self, bot: commands.Bot, invoker_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.invoker_id = invoker_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not is_authorized(self.bot, interaction.user.id):
            await interaction.response.send_message(
                "❌ Bạn không có quyền dùng panel này.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass

    async def refresh(self):
        """Tải lại danh sách emoji mới nhất từ Developer Portal và cập nhật panel."""
        if not self.message:
            return
        try:
            emojis = await self.bot.fetch_application_emojis()
        except discord.HTTPException as e:
            logger.error(f"Không tải được danh sách application emoji: {e}")
            return
        embed = build_list_embed(emojis)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

    async def _get_emojis(self, interaction: discord.Interaction) -> list[discord.Emoji]:
        try:
            return await self.bot.fetch_application_emojis()
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Không tải được danh sách emoji: {e}", ephemeral=True
            )
            return []

    @discord.ui.button(label="Thêm", style=discord.ButtonStyle.success, emoji="➕")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AddEmojiModal(self))

    @discord.ui.button(label="Đổi tên", style=discord.ButtonStyle.primary, emoji="✏️")
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        emojis = await self._get_emojis(interaction)
        if not emojis:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Chưa có emoji nào để đổi tên.", ephemeral=True
                )
            return
        await interaction.response.send_message(
            "Chọn emoji cần đổi tên:",
            view=EmojiSelectView(self, emojis, "rename"),
            ephemeral=True,
        )

    @discord.ui.button(label="Xóa", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        emojis = await self._get_emojis(interaction)
        if not emojis:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "⚠️ Chưa có emoji nào để xóa.", ephemeral=True
                )
            return
        await interaction.response.send_message(
            "Chọn emoji cần xóa:",
            view=EmojiSelectView(self, emojis, "delete"),
            ephemeral=True,
        )

    @discord.ui.button(label="Làm mới", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        emojis = await self._get_emojis(interaction)
        embed = build_list_embed(emojis)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Đóng", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


class EmojiManager(commands.Cog):
    """Mở panel quản lý Application Emoji khi gõ đúng '?emoji' hoặc '?emojis'."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.content:
            return

        content = message.content.strip()
        if not content.startswith(EMOJI_PREFIX):
            return

        word = content[len(EMOJI_PREFIX):].strip().lower()
        if word not in TRIGGER_WORDS:
            return

        if not is_authorized(self.bot, message.author.id):
            await message.reply(
                "❌ Bạn không có quyền quản lý Application Emoji.", mention_author=False
            )
            return

        try:
            emojis = await self.bot.fetch_application_emojis()
        except discord.HTTPException as e:
            await message.reply(
                f"❌ Không tải được danh sách emoji từ Developer Portal: {e}",
                mention_author=False,
            )
            return

        embed = build_list_embed(emojis)
        view = EmojiPanelView(self.bot, message.author.id)
        sent = await message.reply(embed=embed, view=view, mention_author=False)
        view.message = sent


async def setup(bot: commands.Bot):
    await bot.add_cog(EmojiManager(bot))
