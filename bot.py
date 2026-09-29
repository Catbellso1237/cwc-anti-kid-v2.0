import asyncio
import os
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

from utils.emojis import e, load_application_emojis
from utils.owner_check import get_configured_owner_id, is_owner_configured, masked_owner_id

load_dotenv()

TOKEN = (os.getenv("DISCORD_TOKEN") or "").strip()
NORMAL_PREFIX = os.getenv("NORMAL_PREFIX", "?")   # Member & mod (kể cả tạo/sửa category & kênh) dùng tiền tố này
OWNER_PREFIX = os.getenv("OWNER_PREFIX", "!")     # Chỉ chủ bot dùng tiền tố này

# Nếu muốn slash command đồng bộ tức thì (chỉ cho 1 server) trong lúc test,
# điền GUILD_ID vào file .env. Để trống thì sync toàn cục (mất tới 1h để cập nhật).
GUILD_ID = os.getenv("GUILD_ID")

intents = discord.Intents.default()
intents.message_content = True   # Bắt buộc để đọc lệnh prefix (!)
intents.members = True           # Bắt buộc để kick/ban/mute/anti-raid hoạt động đúng
intents.moderation = True        # Bắt buộc để anti_nuke.py nghe audit log real-time

bot = commands.Bot(command_prefix=[NORMAL_PREFIX, OWNER_PREFIX], intents=intents, help_command=commands.DefaultHelpCommand())

from utils.prefix_gate import register_prefix_gate
register_prefix_gate(bot, NORMAL_PREFIX, OWNER_PREFIX)

COGS = [
    "cogs.moderation", "cogs.anti_raid", "cogs.anti_link", "cogs.anti_nuke",
    "cogs.setup", "cogs.category_setup", "cogs.economy", "cogs.rules", "cogs.emoji_manager",
    "cogs.ping", "cogs.chat_bridge", "cogs.info", "cogs.events",
]

# Cog chứa lệnh cấp owner (globalban, lockall...) — CHỈ nạp khi BOT_OWNER_ID hợp lệ.
# Nếu chưa cấu hình đúng, các cog này sẽ KHÔNG được nạp luôn (thay vì nạp rồi để hard_owner_check()
# tự chặn từng lệnh) — khoá chặt hơn 1 bước, tránh lộ ra là server có sẵn các lệnh nguy hiểm
# đang chờ mở khi ai đó tìm được đúng tiền tố + tên lệnh.
OWNER_ONLY_COGS = ["cogs.global_admin", "cogs.lockall"]

_synced_once = False
_emojis_loaded = False


async def load_cogs():
    for cog in COGS:
        await bot.load_extension(cog)
        print(f"{e('success')} Đã load extension: {cog}")

    if is_owner_configured():
        for cog in OWNER_ONLY_COGS:
            await bot.load_extension(cog)
            print(f"{e('success')} Đã load extension (owner-only): {cog}")
    else:
        print(f"{e('error')} BOT_OWNER_ID chưa cấu hình đúng — KHÔNG nạp các cog cấp owner ({', '.join(OWNER_ONLY_COGS)}).")


def _check_owner_id():
    """In ra trạng thái BOT_OWNER_ID lúc khởi động — KHÔNG in nguyên UID ra log/console
    để tránh lộ khi chụp màn hình/dán log công khai."""
    if is_owner_configured():
        print(f"{e('success')} BOT_OWNER_ID hợp lệ ({masked_owner_id()}) — lệnh owner-only chỉ UID này dùng được.")
    else:
        print(f"{e('error')} BOT_OWNER_ID chưa set hoặc sai định dạng trong .env — các lệnh cấp owner sẽ KHÔNG được nạp cho tới khi sửa đúng.")



@bot.listen("on_ready")
async def on_ready_setup():
    global _synced_once, _emojis_loaded

    # 0. Ghi lại thời điểm bot khởi động (dùng cho lệnh !ping hiện uptime)
    if not hasattr(bot, "start_time"):
        bot.start_time = discord.utils.utcnow()

    # 1. Tự động lấy emoji đã set trong Developer Portal (chỉ cần chạy 1 lần)
    if not _emojis_loaded:
        await load_application_emojis(bot)
        _emojis_loaded = True

    # 2. Đồng bộ slash command (chỉ cần chạy 1 lần dù on_ready gọi lại nhiều lần)
    if not _synced_once:
        try:
            if GUILD_ID:
                guild = discord.Object(id=int(GUILD_ID))
                bot.tree.copy_global_to(guild=guild)
                synced = await bot.tree.sync(guild=guild)
                print(f"{e('success')} Đã sync {len(synced)} slash command cho guild {GUILD_ID}")
            else:
                synced = await bot.tree.sync()
                print(f"{e('success')} Đã sync {len(synced)} slash command toàn cục (có thể mất tới 1h để hiện ra)")
            _synced_once = True
        except Exception as ex:
            print(f"{e('error')} Lỗi khi sync slash command: {ex}")


def _has_valid_token_format(token: str) -> bool:
    """Chặn trường hợp để nguyên placeholder/token rỗng trước khi gọi Discord API."""
    if not token:
        return False
    lowered = token.lower()
    return lowered not in {"your_bot_token_here", "token", "discord_token"}


async def main():
    if not _has_valid_token_format(TOKEN):
        print(f"{e('error')} DISCORD_TOKEN chưa set hoặc vẫn là placeholder. Hãy tạo file .env từ .env.example rồi điền token bot thật của riêng bạn.")
        return

    _check_owner_id()

    from utils.database import init_db
    await init_db()

    async with bot:
        bot.http_session = aiohttp.ClientSession()
        try:
            await load_cogs()
            await bot.start(TOKEN)
        finally:
            await bot.http_session.close()


if __name__ == "__main__":
    asyncio.run(main())
    
