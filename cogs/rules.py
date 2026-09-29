"""
Lệnh !rules — đăng nội quy server có sẵn (KHÔNG dùng AI nữa).

Nội dung nội quy được soạn sẵn trong 3 file .txt theo mức độ, ở thư mục data/:
  - data/rules_thap.txt        (🟢 Nhẹ nhàng)
  - data/rules_trungbinh.txt   (🟡 Trung bình)
  - data/rules_cao.txt         (🔴 Nghiêm khắc)

Muốn đổi nội dung nội quy, chỉ cần sửa trực tiếp 3 file .txt này (không cần sửa code,
không cần GEMINI_API_KEY).
"""
import os

import discord
from discord.ext import commands

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

VALID_LEVELS = {
    "thấp": ("🟢", "Nhẹ nhàng", "rules_thap.txt"),
    "trung bình": ("🟡", "Trung bình", "rules_trungbinh.txt"),
    "cao": ("🔴", "Nghiêm khắc", "rules_cao.txt"),
}


def _read_rules_file(filename: str) -> str:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


class Rules(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="rules")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(embed_links=True, send_messages=True)
    async def rules(
        self,
        ctx: commands.Context,
        level: str,
        channel: discord.TextChannel = None,
        *,
        note: str = "",
    ):
        """Đăng nội quy server có sẵn theo 3 mức độ.

        Cú pháp: !rules <thấp|trung bình|cao> [#kênh]
        Ví dụ:
          !rules thấp #rules
          !rules cao #rules
        """
        level_key = level.lower().strip()
        if level_key not in VALID_LEVELS:
            await ctx.send(
                "⚠️ Mức độ không hợp lệ. Chọn một trong: `thấp`, `trung bình`, `cao`\n"
                "Ví dụ: `?rules trung bình #rules`"
            )
            return

        target_channel = channel or ctx.channel
        emoji, label, filename = VALID_LEVELS[level_key]

        try:
            content = _read_rules_file(filename)
        except FileNotFoundError:
            await ctx.send(
                f"❌ Không tìm thấy file `data/{filename}`. Hãy đảm bảo file tồn tại "
                f"(hoặc tạo lại theo mẫu trong repo)."
            )
            return

        embed = discord.Embed(
            title=f"{emoji} NỘI QUY SERVER — Mức độ: {label}",
            description=content[:4000],
            color=discord.Color.green() if level_key == "thấp"
            else discord.Color.gold() if level_key == "trung bình"
            else discord.Color.red(),
        )
        embed.set_footer(text=f"Đăng bởi {ctx.author.display_name}")

        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            await ctx.send(f"❌ Bot không có quyền gửi tin nhắn vào {target_channel.mention}.")
            return

        if target_channel.id != ctx.channel.id:
            await ctx.send(f"✅ Đã đăng nội quy mức **{label}** vào {target_channel.mention}.")
        else:
            await ctx.send(f"✅ Đã đăng nội quy mức **{label}**.")

    @rules.error
    async def rules_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("⚠️ Lệnh này cần quyền Administrator.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                "⚠️ Thiếu tham số. Dùng: `?rules <thấp|trung bình|cao> [#kênh]`"
            )
        else:
            await ctx.send(f"❌ Có lỗi xảy ra: `{error}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Rules(bot))
