"""
Bộ lệnh tự động tạo category + kênh cho server, dùng chung tiền tố "?" như mọi
lệnh thường khác (đổi được qua NORMAL_PREFIX trong .env).

Lệnh:
  ?autosetup              Tạo toàn bộ category + kênh theo template trong config.json
  ?addcategory <tên>      Tạo 1 category mới
  ?addchannel <tên> [text|voice] [danh_mục]   Tạo 1 kênh mới
  ?renamechannel #kênh <tên_mới>              Đổi tên kênh
  ?renamecategory <TÊN CŨ> | <TÊN MỚI>        Đổi tên category

Tất cả lệnh trên yêu cầu quyền Administrator.
"""
import json
import os

import discord
from discord.ext import commands

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")


def _load_template() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class CategorySetup(commands.Cog):
    """Tạo/sửa category & kênh hàng loạt theo template config.json."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _find_category(self, guild: discord.Guild, name: str) -> discord.CategoryChannel | None:
        name_lower = name.lower().strip()
        for cat in guild.categories:
            if cat.name.lower() == name_lower:
                return cat
        return None

    # -----------------------------------------------------------------
    # ?autosetup — tạo toàn bộ category + kênh theo config.json
    # -----------------------------------------------------------------
    @commands.command(name="autosetup", aliases=["setupcategories"])
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def autosetup(self, ctx: commands.Context):
        """Tạo toàn bộ category + kênh theo template trong config.json.
        Category/kênh đã tồn tại (trùng tên) sẽ được bỏ qua, không tạo trùng."""
        try:
            template = _load_template()
        except FileNotFoundError:
            return await ctx.send(f"❌ Không tìm thấy `config.json`. Hãy tạo file theo mẫu trong repo.")
        except json.JSONDecodeError as ex:
            return await ctx.send(f"❌ `config.json` bị lỗi định dạng JSON: `{ex}`")

        guild = ctx.guild
        created_categories = 0
        created_channels = 0
        skipped = 0

        thinking = await ctx.send("⏳ Đang tạo category + kênh theo template...")

        for cat_def in template.get("categories", []):
            cat_name = cat_def.get("name", "").strip()
            if not cat_name:
                continue

            category = self._find_category(guild, cat_name)
            if category is None:
                try:
                    category = await guild.create_category(cat_name, reason=f"Auto-setup bởi {ctx.author}")
                    created_categories += 1
                except discord.HTTPException as ex:
                    await ctx.send(f"⚠️ Không tạo được category `{cat_name}`: `{ex}`")
                    continue
            else:
                skipped += 1

            existing_names = {ch.name.lower() for ch in category.channels}

            for ch_def in cat_def.get("channels", []):
                ch_name = ch_def.get("name", "").strip()
                ch_type = ch_def.get("type", "text").lower()
                if not ch_name:
                    continue
                if ch_name.lower() in existing_names:
                    skipped += 1
                    continue
                try:
                    if ch_type == "voice":
                        await guild.create_voice_channel(ch_name, category=category, reason=f"Auto-setup bởi {ctx.author}")
                    else:
                        await guild.create_text_channel(ch_name, category=category, reason=f"Auto-setup bởi {ctx.author}")
                    created_channels += 1
                except discord.HTTPException as ex:
                    await ctx.send(f"⚠️ Không tạo được kênh `{ch_name}`: `{ex}`")

        embed = mod_embed(
            "✅ Đã hoàn tất Auto-Setup",
            f"**Category mới:** {created_categories}\n"
            f"**Kênh mới:** {created_channels}\n"
            f"**Bỏ qua (đã tồn tại):** {skipped}",
            discord.Color.green(),
        )
        await thinking.edit(content=None, embed=embed)

    # -----------------------------------------------------------------
    # ?addcategory <tên>
    # -----------------------------------------------------------------
    @commands.command(name="addcategory")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def addcategory(self, ctx: commands.Context, *, name: str):
        """Tạo 1 category mới. Cú pháp: ?addcategory <tên>"""
        if self._find_category(ctx.guild, name):
            return await ctx.send(f"⚠️ Category `{name}` đã tồn tại.")
        try:
            await ctx.guild.create_category(name, reason=f"Tạo bởi {ctx.author}")
        except discord.HTTPException as ex:
            return await ctx.send(f"❌ Không tạo được category: `{ex}`")
        await ctx.send(f"✅ Đã tạo category `{name}`.")

    # -----------------------------------------------------------------
    # ?addchannel <tên> [text|voice] [danh_mục]
    # -----------------------------------------------------------------
    @commands.command(name="addchannel")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def addchannel(self, ctx: commands.Context, name: str, channel_type: str = "text", *, category_name: str = None):
        """Tạo 1 kênh mới. Cú pháp: ?addchannel <tên> [text|voice] [danh_mục]"""
        channel_type = channel_type.lower().strip()
        if channel_type not in {"text", "voice"}:
            return await ctx.send("⚠️ Loại kênh không hợp lệ. Chọn `text` hoặc `voice`.")

        category = None
        if category_name:
            category = self._find_category(ctx.guild, category_name)
            if category is None:
                return await ctx.send(f"⚠️ Không tìm thấy category `{category_name}`. Dùng `?addcategory` để tạo trước.")

        try:
            if channel_type == "voice":
                await ctx.guild.create_voice_channel(name, category=category, reason=f"Tạo bởi {ctx.author}")
            else:
                await ctx.guild.create_text_channel(name, category=category, reason=f"Tạo bởi {ctx.author}")
        except discord.HTTPException as ex:
            return await ctx.send(f"❌ Không tạo được kênh: `{ex}`")

        loc = f" trong `{category_name}`" if category_name else ""
        await ctx.send(f"✅ Đã tạo kênh `{name}` ({channel_type}){loc}.")

    # -----------------------------------------------------------------
    # ?renamechannel #kênh <tên_mới>
    # -----------------------------------------------------------------
    @commands.command(name="renamechannel")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def renamechannel(self, ctx: commands.Context, channel: discord.abc.GuildChannel, *, new_name: str):
        """Đổi tên kênh. Cú pháp: ?renamechannel #kênh <tên_mới>"""
        old_name = channel.name
        try:
            await channel.edit(name=new_name, reason=f"Đổi tên bởi {ctx.author}")
        except discord.HTTPException as ex:
            return await ctx.send(f"❌ Không đổi được tên kênh: `{ex}`")
        await ctx.send(f"✅ Đã đổi tên kênh `{old_name}` → `{new_name}`.")

    # -----------------------------------------------------------------
    # ?renamecategory TÊN CŨ | TÊN MỚI
    # -----------------------------------------------------------------
    @commands.command(name="renamecategory")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def renamecategory(self, ctx: commands.Context, *, names: str):
        """Đổi tên category. Cú pháp: ?renamecategory TÊN CŨ | TÊN MỚI"""
        if "|" not in names:
            return await ctx.send("⚠️ Sai cú pháp. Dùng: `?renamecategory TÊN CŨ | TÊN MỚI`")
        old_name, _, new_name = names.partition("|")
        old_name, new_name = old_name.strip(), new_name.strip()

        category = self._find_category(ctx.guild, old_name)
        if category is None:
            return await ctx.send(f"⚠️ Không tìm thấy category `{old_name}`.")

        try:
            await category.edit(name=new_name, reason=f"Đổi tên bởi {ctx.author}")
        except discord.HTTPException as ex:
            return await ctx.send(f"❌ Không đổi được tên category: `{ex}`")
        await ctx.send(f"✅ Đã đổi tên category `{old_name}` → `{new_name}`.")

    @autosetup.error
    @addcategory.error
    @addchannel.error
    @renamechannel.error
    @renamecategory.error
    async def category_setup_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⚠️ Lệnh này cần quyền Administrator.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"⚠️ Thiếu tham số. Dùng `?help {ctx.command}` để xem cách dùng.")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"⚠️ Tham số không hợp lệ: `{error}`")
        else:
            await ctx.send(f"❌ Có lỗi xảy ra: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(CategorySetup(bot))
