import os
import discord
from discord.ext import commands

from utils.emojis import e

# Đặt link ảnh/gif giới thiệu bot vào đây (hoặc điền qua .env biến FEATURES_GIF_URL).
# Có thể dùng link ảnh gif upload lên Discord (gửi ảnh vào 1 kênh rồi copy link),
# hoặc link Imgur/bất kỳ CDN nào hỗ trợ .gif trực tiếp.
FEATURES_GIF_URL = os.getenv("FEATURES_GIF_URL", "")


class Info(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="features", aliases=["info", "gioithieu"], description="Xem toàn bộ chức năng của bot")
    async def features(self, ctx: commands.Context):
        embed = discord.Embed(
            title=f"{e('shield')} Mod Bot v2.0 — Bảng chức năng",
            description="Bot điều hành + phòng vệ server, dùng được cả lệnh `?` lẫn `/`.",
            color=discord.Color.blurple(),
        )

        embed.add_field(
            name=f"{e('kick')} Điều hành cơ bản",
            value=(
                "`kick` `ban` `unban` `mute` `unmute`\n"
                "`warn` `warnings` `clearwarn`\n"
                "`purge` `lock` `unlock` `slowmode`"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{e('raid')} Chống raid & bot giả dạng",
            value=(
                f"{e('fakebot')} Tự phát hiện bot có tên nhái theo bot mod nổi tiếng, không có tick verified\n"
                f"{e('raid')} Tự phát hiện join ồ ạt (raid) và khoá server (verification level `high`)\n"
                f"{e('shield')} `autodefense on/off` — bật/tắt chế độ tự phòng vệ **24/7**\n"
                f"{e('info')} `setmodlog #kênh` — chọn kênh nhận cảnh báo\n"
                f"{e('info')} `trustbot @bot` — thêm bot vào whitelist"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{e('shield')} Anti-Nuke (giám sát audit log real-time)",
            value=(
                "Tự phát hiện & trung hòa tài khoản được cấp quyền cao rồi phá server "
                "(xóa kênh/role, ban/kick hàng loạt)\n"
                "`antinukeunlock` `trust <user_id>` `status`"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{e('coin')} Economy (SQLite)",
            value=(
                "`balance` `daily` `work` `deposit` `withdraw`\n"
                "`pay` `rob` `shop` `buy` `inventory` `leaderboard`"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{e('info')} Khác",
            value=(
                "`rules <thấp|trung bình|cao> [#kênh]` — đăng nội quy có sẵn (data/rules_*.txt)\n"
                "`?emoji` — panel quản lý Application Emoji (thêm/đổi tên/xóa)\n"
                "Emoji phản hồi tự lấy từ Developer Portal nếu bạn đã upload, không thì dùng emoji mặc định."
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{e('info')} Category & kênh (tiền tố `?`)",
            value=(
                "`?autosetup` — tạo toàn bộ category + kênh theo `config.json`\n"
                "`?addcategory <tên>` `?addchannel <tên> [text|voice] [danh_mục]`\n"
                "`?renamechannel #kênh <tên_mới>` `?renamecategory TÊN CŨ | TÊN MỚI`"
            ),
            inline=False,
        )

        if FEATURES_GIF_URL:
            embed.set_image(url=FEATURES_GIF_URL)
        else:
            embed.set_footer(text="Mẹo: điền link ảnh gif vào FEATURES_GIF_URL trong .env để hiện ảnh minh hoạ ở đây")

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Info(bot))
      
