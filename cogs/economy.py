import json
import os
import random
import time

import discord
from discord.ext import commands

from utils import database as db

SHOP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "shop.json")


def load_shop():
    with open(SHOP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["items"]


def fmt(amount: int) -> str:
    return f"{amount:,}".replace(",", ".")


def fmt_time(seconds: int) -> str:
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    parts = []
    if h:
        parts.append(f"{h} giờ")
    if m:
        parts.append(f"{m} phút")
    if not h and not m:
        parts.append(f"{s} giây")
    return " ".join(parts)


WORK_MESSAGES = [
    "làm shipper giao hàng",
    "code thuê cho khách",
    "livestream game",
    "dọn dẹp quán net",
    "phụ bán trà sữa",
    "làm freelancer thiết kế",
    "chạy grab",
]


class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        await db.init_db()

    # ---------------- Balance ----------------

    @commands.command(name="balance", aliases=["bal", "money"])
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        """Xem số dư ví + ngân hàng"""
        member = member or ctx.author
        wallet, bank = await db.get_balance(member.id, ctx.guild.id)

        embed = discord.Embed(
            title=f"💰 Số dư của {member.display_name}",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Ví", value=f"{fmt(wallet)} 🪙", inline=True)
        embed.add_field(name="Ngân hàng", value=f"{fmt(bank)} 🪙", inline=True)
        embed.add_field(name="Tổng", value=f"**{fmt(wallet + bank)}** 🪙", inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    # ---------------- Daily ----------------

    @commands.command(name="daily")
    async def daily(self, ctx: commands.Context):
        """Nhận thưởng hàng ngày"""
        last = await db.get_cooldown(ctx.author.id, ctx.guild.id, "last_daily")
        now = int(time.time())
        remaining = db.DAILY_COOLDOWN - (now - last)

        if remaining > 0:
            await ctx.send(f"⏳ Bạn đã nhận rồi. Quay lại sau **{fmt_time(remaining)}** nữa.")
            return

        claims_so_far = await db.get_daily_count(ctx.author.id, ctx.guild.id)
        is_first_time = claims_so_far == 0

        if is_first_time:
            amount = db.DAILY_FIRST_AMOUNT
        else:
            amount = random.randint(db.DAILY_MIN, db.DAILY_MAX)

        await db.update_wallet(ctx.author.id, ctx.guild.id, amount)
        await db.set_cooldown(ctx.author.id, ctx.guild.id, "last_daily")
        await db.increment_daily_count(ctx.author.id, ctx.guild.id)

        if is_first_time:
            await ctx.send(
                f"🎉 Chào mừng {ctx.author.mention}! Phần thưởng **!daily lần đầu** "
                f"của bạn là **{fmt(amount)} 🪙**!\n"
                f"Từ ngày mai, phần thưởng hàng ngày sẽ nhỏ hơn nhiều "
                f"(khoảng {fmt(db.DAILY_MIN)}–{fmt(db.DAILY_MAX)} 🪙)."
            )
        else:
            await ctx.send(
                f"🎁 {ctx.author.mention} đã nhận **{fmt(amount)} 🪙** thưởng hàng ngày!"
            )

    # ---------------- Work ----------------

    @commands.command(name="work")
    async def work(self, ctx: commands.Context):
        """Đi làm kiếm tiền"""
        last = await db.get_cooldown(ctx.author.id, ctx.guild.id, "last_work")
        now = int(time.time())
        remaining = db.WORK_COOLDOWN - (now - last)

        if remaining > 0:
            await ctx.send(f"⏳ Bạn vừa làm việc xong. Nghỉ ngơi thêm **{fmt_time(remaining)}** nữa.")
            return

        amount = random.randint(db.WORK_MIN, db.WORK_MAX)
        action = random.choice(WORK_MESSAGES)

        await db.update_wallet(ctx.author.id, ctx.guild.id, amount)
        await db.set_cooldown(ctx.author.id, ctx.guild.id, "last_work")
        await ctx.send(
            f"💼 {ctx.author.mention} đã đi **{action}** và kiếm được **{fmt(amount)} 🪙**!"
        )

    # ---------------- Deposit / Withdraw ----------------

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx: commands.Context, amount: str):
        """Gửi tiền vào ngân hàng. Dùng 'all' để gửi hết"""
        wallet, bank = await db.get_balance(ctx.author.id, ctx.guild.id)

        if amount.lower() == "all":
            value = wallet
        else:
            if not amount.isdigit():
                await ctx.send("⚠️ Số tiền không hợp lệ.")
                return
            value = int(amount)

        if value <= 0 or value > wallet:
            await ctx.send("⚠️ Số dư trong ví không đủ.")
            return

        await db.update_wallet(ctx.author.id, ctx.guild.id, -value)
        await db.update_bank(ctx.author.id, ctx.guild.id, value)
        await ctx.send(f"🏦 Đã gửi **{fmt(value)} 🪙** vào ngân hàng.")

    @commands.command(name="withdraw", aliases=["with"])
    async def withdraw(self, ctx: commands.Context, amount: str):
        """Rút tiền từ ngân hàng. Dùng 'all' để rút hết"""
        wallet, bank = await db.get_balance(ctx.author.id, ctx.guild.id)

        if amount.lower() == "all":
            value = bank
        else:
            if not amount.isdigit():
                await ctx.send("⚠️ Số tiền không hợp lệ.")
                return
            value = int(amount)

        if value <= 0 or value > bank:
            await ctx.send("⚠️ Số dư trong ngân hàng không đủ.")
            return

        await db.update_bank(ctx.author.id, ctx.guild.id, -value)
        await db.update_wallet(ctx.author.id, ctx.guild.id, value)
        await ctx.send(f"💵 Đã rút **{fmt(value)} 🪙** về ví.")

    # ---------------- Pay ----------------

    @commands.command(name="pay")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: int):
        """Chuyển tiền cho người khác"""
        if member.id == ctx.author.id:
            await ctx.send("⚠️ Không thể tự chuyển tiền cho chính mình.")
            return
        if member.bot:
            await ctx.send("⚠️ Không thể chuyển tiền cho bot.")
            return
        if amount <= 0:
            await ctx.send("⚠️ Số tiền phải lớn hơn 0.")
            return

        success = await db.transfer(ctx.author.id, member.id, ctx.guild.id, amount)
        if not success:
            await ctx.send("⚠️ Số dư trong ví không đủ.")
            return

        await ctx.send(f"✅ {ctx.author.mention} đã chuyển **{fmt(amount)} 🪙** cho {member.mention}")

    # ---------------- Rob ----------------

    @commands.command(name="rob")
    async def rob(self, ctx: commands.Context, member: discord.Member):
        """Cướp tiền trong ví người khác (rủi ro cao)"""
        if member.id == ctx.author.id:
            await ctx.send("⚠️ Không thể tự cướp chính mình.")
            return
        if member.bot:
            await ctx.send("⚠️ Không thể cướp bot.")
            return

        last = await db.get_cooldown(ctx.author.id, ctx.guild.id, "last_rob")
        now = int(time.time())
        remaining = db.ROB_COOLDOWN - (now - last)
        if remaining > 0:
            await ctx.send(f"⏳ Bạn vừa cướp xong. Thử lại sau **{fmt_time(remaining)}**.")
            return

        target_wallet, _ = await db.get_balance(member.id, ctx.guild.id)
        if target_wallet < 100:
            await ctx.send(f"⚠️ {member.display_name} không có đủ tiền trong ví để cướp.")
            return

        await db.set_cooldown(ctx.author.id, ctx.guild.id, "last_rob")

        success_chance = 0.4
        if random.random() < success_chance:
            stolen = random.randint(1, min(target_wallet, target_wallet // 2 + 1))
            await db.update_wallet(member.id, ctx.guild.id, -stolen)
            await db.update_wallet(ctx.author.id, ctx.guild.id, stolen)
            await ctx.send(
                f"🦹 {ctx.author.mention} đã cướp thành công **{fmt(stolen)} 🪙** từ {member.mention}!"
            )
        else:
            fine = random.randint(50, 300)
            actor_wallet, _ = await db.get_balance(ctx.author.id, ctx.guild.id)
            fine = min(fine, actor_wallet)
            await db.update_wallet(ctx.author.id, ctx.guild.id, -fine)
            await ctx.send(
                f"🚔 {ctx.author.mention} đã bị bắt khi cố cướp {member.mention} "
                f"và bị phạt **{fmt(fine)} 🪙**!"
            )

    # ---------------- Shop / Inventory ----------------

    @commands.command(name="shop")
    async def shop(self, ctx: commands.Context):
        """Xem cửa hàng vật phẩm"""
        items = load_shop()
        embed = discord.Embed(title="🛒 Cửa Hàng", color=discord.Color.blurple())
        for item in items:
            embed.add_field(
                name=f"{item['name']} — {fmt(item['price'])} 🪙",
                value=item["description"],
                inline=False,
            )
        embed.set_footer(text="Dùng !buy <tên vật phẩm> để mua")
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy(self, ctx: commands.Context, *, item_name: str):
        """Mua vật phẩm từ cửa hàng"""
        items = load_shop()
        match = next(
            (i for i in items if i["name"].lower().endswith(item_name.lower())
             or item_name.lower() in i["name"].lower()),
            None,
        )
        if not match:
            await ctx.send("⚠️ Không tìm thấy vật phẩm này trong cửa hàng. Dùng `?shop` để xem danh sách.")
            return

        wallet, _ = await db.get_balance(ctx.author.id, ctx.guild.id)
        if wallet < match["price"]:
            await ctx.send("⚠️ Số dư trong ví không đủ để mua vật phẩm này.")
            return

        await db.update_wallet(ctx.author.id, ctx.guild.id, -match["price"])
        await db.add_item(ctx.author.id, ctx.guild.id, match["name"], 1)
        await ctx.send(f"✅ Bạn đã mua **{match['name']}** với giá **{fmt(match['price'])} 🪙**")

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        """Xem túi đồ"""
        member = member or ctx.author
        items = await db.get_inventory(member.id, ctx.guild.id)

        embed = discord.Embed(
            title=f"🎒 Túi đồ của {member.display_name}",
            color=discord.Color.dark_teal(),
        )
        if not items:
            embed.description = "Trống trơn."
        else:
            for name, qty in items:
                embed.add_field(name=name, value=f"x{qty}", inline=True)
        await ctx.send(embed=embed)

    # ---------------- Leaderboard ----------------

    @commands.command(name="leaderboard", aliases=["lb", "top"])
    async def leaderboard(self, ctx: commands.Context):
        """Bảng xếp hạng người giàu nhất server"""
        rows = await db.get_leaderboard(ctx.guild.id, limit=10)
        if not rows:
            await ctx.send("Chưa có dữ liệu.")
            return

        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, (user_id, total) in enumerate(rows):
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"(rời server) {user_id}"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — {fmt(total)} 🪙")

        embed = discord.Embed(
            title=f"🏆 Bảng Xếp Hạng — {ctx.guild.name}",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )
        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))

