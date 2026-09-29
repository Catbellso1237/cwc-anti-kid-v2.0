import discord
from discord import app_commands
from discord.ext import commands

from utils.emojis import e
from utils.owner_check import hard_owner_check


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class LockAll(commands.Cog):
    """
    Lệnh cấp cao NGUY HIỂM: xoá TOÀN BỘ kênh trong server, kèm tuỳ chọn đổi tên server
    ngay sau đó. Chỉ đúng UID trong BOT_OWNER_ID mới gọi được (xem utils/owner_check.py).

    Bắt buộc gõ lại CHÍNH XÁC tên server hiện tại làm tham số xác nhận — nếu gõ sai
    (kể cả sai 1 ký tự), lệnh tự huỷ và KHÔNG xoá gì cả. Đây là lớp an toàn bắt buộc,
    không phải tuỳ chọn, vì hành động này không thể hoàn tác.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(
        name="lockall",
        description="[Chủ bot - NGUY HIỂM] Xoá TOÀN BỘ kênh trong server, có thể kèm đổi tên server",
    )
    @app_commands.describe(
        confirm_server_name="Gõ CHÍNH XÁC tên server hiện tại để xác nhận (bắt buộc, chống gọi nhầm)",
        new_name="Tuỳ chọn: đổi tên server ngay sau khi xoá xong",
    )
    @hard_owner_check()
    @commands.bot_has_permissions(manage_channels=True)
    async def lockall(self, ctx: commands.Context, confirm_server_name: str, new_name: str = None):
        guild = ctx.guild

        # Lớp xác nhận bắt buộc — gõ sai tên server thì huỷ ngay, không đụng gì cả
        if confirm_server_name != guild.name:
            embed = mod_embed(
                f"{e('error')} Xác nhận không khớp — đã huỷ lệnh",
                f"Tên bạn gõ không khớp chính xác với tên server hiện tại (`{guild.name}`). "
                f"Không có kênh nào bị xoá. Gõ lại đúng tên server nếu thực sự muốn tiếp tục.",
                discord.Color.red(),
            )
            return await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)

        if ctx.interaction:
            await ctx.defer()

        channels = list(guild.channels)
        deleted = 0
        for ch in channels:
            try:
                await ch.delete(reason=f"lockall bởi {ctx.author}")
                deleted += 1
            except discord.HTTPException:
                continue

        renamed_text = ""
        if new_name:
            try:
                await guild.edit(name=new_name, reason=f"lockall bởi {ctx.author}")
                renamed_text = f"\n**Đã đổi tên server thành:** {new_name}"
            except discord.HTTPException:
                renamed_text = "\n(Không đổi được tên server — có thể do rate limit đổi tên của Discord)"

        # Kênh gọi lệnh gần như chắc chắn đã bị xoá trong lúc này -> báo kết quả qua DM
        report = mod_embed(
            f"{e('success')} Đã hoàn tất lockall",
            f"**Server:** {guild.name} (`{guild.id}`)\n"
            f"**Số kênh đã xoá:** {deleted}/{len(channels)}{renamed_text}",
            discord.Color.orange(),
        )
        try:
            await ctx.author.send(embed=report)
        except discord.Forbidden:
            pass

    @lockall.error
    async def lockall_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingRequiredArgument):
            embed = mod_embed(
                f"{e('error')} Thiếu tham số xác nhận",
                "Bạn PHẢI gõ chính xác tên server làm tham số `confirm_server_name` để xác nhận, tránh gọi nhầm lệnh nguy hiểm này.",
                discord.Color.red(),
            )
        elif isinstance(error, commands.BotMissingPermissions):
            embed = mod_embed(f"{e('error')} Bot thiếu quyền", "Bot cần quyền `Manage Channels`.", discord.Color.red())
        elif isinstance(error, commands.CheckFailure):
            embed = mod_embed(f"{e('error')} Không có quyền", "Lệnh này chỉ dành riêng cho đúng UID đã cấu hình trong `BOT_OWNER_ID`.", discord.Color.red())
        else:
            embed = mod_embed(f"{e('error')} Lỗi", f"```{error}```", discord.Color.red())
        try:
            await ctx.send(embed=embed, ephemeral=True if ctx.interaction else False)
        except discord.HTTPException:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(LockAll(bot))
                
