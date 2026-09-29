import time
import aiosqlite

DB_PATH = "data/economy.db"

DEFAULT_WALLET = 500
DAILY_FIRST_AMOUNT = 10_000_000         # Lần đầu tiên dùng !daily
DAILY_MIN = 10_000                      # Từ lần thứ 2 trở đi
DAILY_MAX = 20_000
DAILY_COOLDOWN = 24 * 60 * 60          # 24 giờ
WORK_COOLDOWN = 60 * 60                 # 1 giờ
WORK_MIN, WORK_MAX = 50, 250
ROB_COOLDOWN = 3 * 60 * 60               # 3 giờ


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                guild_id INTEGER NOT NULL,
                wallet INTEGER NOT NULL DEFAULT 500,
                bank INTEGER NOT NULL DEFAULT 0,
                last_daily INTEGER NOT NULL DEFAULT 0,
                last_work INTEGER NOT NULL DEFAULT 0,
                last_rob INTEGER NOT NULL DEFAULT 0,
                daily_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Migration an toàn cho DB đã tạo trước khi có cột daily_count
        cur = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cur.fetchall()]
        if "daily_count" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0"
            )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, guild_id, item_name)
            )
            """
        )
        await db.commit()


async def _ensure_user(db, user_id: int, guild_id: int):
    await db.execute(
        "INSERT OR IGNORE INTO users (user_id, guild_id, wallet, bank) VALUES (?, ?, ?, 0)",
        (user_id, guild_id, DEFAULT_WALLET),
    )


async def get_balance(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        cur = await db.execute(
            "SELECT wallet, bank FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cur.fetchone()
        return row[0], row[1]


async def update_wallet(user_id: int, guild_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE users SET wallet = wallet + ? WHERE user_id = ? AND guild_id = ?",
            (delta, user_id, guild_id),
        )
        await db.commit()


async def update_bank(user_id: int, guild_id: int, delta: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE users SET bank = bank + ? WHERE user_id = ? AND guild_id = ?",
            (delta, user_id, guild_id),
        )
        await db.commit()


async def set_balance(user_id: int, guild_id: int, wallet: int = None, bank: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        if wallet is not None:
            await db.execute(
                "UPDATE users SET wallet = ? WHERE user_id = ? AND guild_id = ?",
                (wallet, user_id, guild_id),
            )
        if bank is not None:
            await db.execute(
                "UPDATE users SET bank = ? WHERE user_id = ? AND guild_id = ?",
                (bank, user_id, guild_id),
            )
        await db.commit()


async def transfer(sender_id: int, receiver_id: int, guild_id: int, amount: int):
    """Chuyển tiền từ wallet người gửi sang wallet người nhận."""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, sender_id, guild_id)
        await _ensure_user(db, receiver_id, guild_id)
        await db.commit()

        cur = await db.execute(
            "SELECT wallet FROM users WHERE user_id = ? AND guild_id = ?",
            (sender_id, guild_id),
        )
        row = await cur.fetchone()
        if row is None or row[0] < amount:
            return False

        await db.execute(
            "UPDATE users SET wallet = wallet - ? WHERE user_id = ? AND guild_id = ?",
            (amount, sender_id, guild_id),
        )
        await db.execute(
            "UPDATE users SET wallet = wallet + ? WHERE user_id = ? AND guild_id = ?",
            (amount, receiver_id, guild_id),
        )
        await db.commit()
        return True


async def get_cooldown(user_id: int, guild_id: int, field: str):
    """field: last_daily / last_work / last_rob"""
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        cur = await db.execute(
            f"SELECT {field} FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def set_cooldown(user_id: int, guild_id: int, field: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            f"UPDATE users SET {field} = ? WHERE user_id = ? AND guild_id = ?",
            (int(time.time()), user_id, guild_id),
        )
        await db.commit()


async def get_daily_count(user_id: int, guild_id: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.commit()
        cur = await db.execute(
            "SELECT daily_count FROM users WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        row = await cur.fetchone()
        return row[0] if row else 0


async def increment_daily_count(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await _ensure_user(db, user_id, guild_id)
        await db.execute(
            "UPDATE users SET daily_count = daily_count + 1 WHERE user_id = ? AND guild_id = ?",
            (user_id, guild_id),
        )
        await db.commit()


async def get_leaderboard(guild_id: int, limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT user_id, wallet + bank AS total
            FROM users
            WHERE guild_id = ?
            ORDER BY total DESC
            LIMIT ?
            """,
            (guild_id, limit),
        )
        return await cur.fetchall()


# ---------------- Inventory ----------------

async def add_item(user_id: int, guild_id: int, item_name: str, qty: int = 1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO inventory (user_id, guild_id, item_name, quantity)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, guild_id, item_name)
            DO UPDATE SET quantity = quantity + excluded.quantity
            """,
            (user_id, guild_id, item_name, qty),
        )
        await db.commit()


async def get_inventory(user_id: int, guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT item_name, quantity FROM inventory WHERE user_id = ? AND guild_id = ? AND quantity > 0",
            (user_id, guild_id),
        )
        return await cur.fetchall()
  
