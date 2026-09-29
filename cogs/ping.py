import time
import discord
from discord.ext import commands

from utils.emojis import e


def mod_embed(title: str, description: str, color: discord.Color = discord.Color.blurple()):
    return discord.Embed(title=title, description=description, color=color)


class Ping(commands.Cog):
    """Lệnh kiểm tra độ trễ (ping) và thời gian hoạt động của bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Kiểm tra độ trễ (ping) của bot")
    async def ping(self, ctx: commands.Context):
        ws_latency = round(self.bot.latency * 1000)  # độ trễ websocket (heartbeat)

        start = time.perf_counter()
        if ctx.interaction:
            await ctx.defer()
        message = await ctx.send(embed=mod_embed(f"{e('ping')} Đang đo...", "Đang gửi tin nhắn để đo API latency..."))
        api_latency = round((time.perf_counter() - start) * 1000)

        uptime_text = "Không rõ"
        if hasattr(self.bot, "start_time"):
            delta = discord.utils.utcnow() - self.bot.start_time
            days, rem = divmod(int(delta.total_seconds()), 86400)
            hours, rem = divmod(rem, 3600)
            minutes, _ = divmod(rem, 60)
            uptime_text = f"{days}d {hours}h {minutes}p"

        # Đánh giá chất lượng kết nối bằng emoji cho trực quan
        if ws_latency < 150:
            quality = f"{e('success')} Tốt"
        elif ws_latency < 300:
            quality = f"{e('warn')} Bình thường"
        else:
            quality = f"{e('error')} Chậm"

        embed = mod_embed(
            f"{e('pong')} Pong!",
            f"**Websocket:** {ws_latency}ms\n"
            f"**API (round-trip):** {api_latency}ms\n"
            f"**Chất lượng:** {quality}\n"
            f"**Uptime:** {uptime_text}",
            discord.Color.green(),
        )
        await message.edit(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Ping(bot))
          
