import discord
from discord.ext import commands
from utils.emojis import e
from utils.prefix_gate import WrongPrefixUsage


class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"{e('success')} Đã đăng nhập với tên {self.bot.user} (ID: {self.bot.user.id})")
        print(f"{e('info')} Đang hoạt động ở {len(self.bot.guilds)} server.")
        await self.bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name="server | ?help hoặc /help")
        )

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        # Lỗi riêng của từng lệnh mod đã được xử lý trong cog gốc của lệnh đó
        # Đây chỉ là fallback cho các lỗi chung / lệnh không tồn tại
        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, WrongPrefixUsage):
            # Nếu cog gốc của lệnh đã có sẵn error handler riêng thì để nó tự xử lý,
            # tránh hiện thông báo 2 lần
            if ctx.command and ctx.command.has_error_handler():
                return
            try:
                cmd_name = ctx.command.qualified_name if ctx.command else "?"
                await ctx.send(f"{e('error')} Lệnh `{cmd_name}` dùng tiền tố `{error.expected_prefix}`, không phải `{ctx.prefix}`.")
            except discord.HTTPException:
                pass
            return

        if isinstance(error, commands.CheckFailure):
            return  # đã được cog con xử lý
        print(f"[LỖI] {ctx.command}: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))

