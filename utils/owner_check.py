"""
Check quyền owner dùng chung cho mọi lệnh cấp cao (global ban, global announce,
quản lý kênh hàng loạt, bộ lọc cầu nối chat, lockall...).

Khoá cứng theo 1 UID cụ thể lấy từ biến môi trường BOT_OWNER_ID (đặt qua .env hoặc
GitHub Secrets), KHÔNG dùng commands.is_owner() mặc định của discord.py.

Lý do: commands.is_owner() xác định owner dựa trên application đang chạy (ai sở hữu
bot token đó trong Developer Portal). Nếu ai đó clone repo này về và tự chạy bằng
token bot riêng của họ, họ sẽ tự động là "owner" theo cách đó. hard_owner_check()
luôn so khớp với đúng UID đã set trong BOT_OWNER_ID, nên dù ai clone repo và deploy
ở đâu (Termux, Codespaces, Windows...), các lệnh cấp cao này vẫn chỉ 1 người dùng
được, trừ khi họ tự đổi UID trong .env của họ.

CHỦ Ý: UID owner KHÔNG được gắn cứng trong code (không hardcode), chỉ đọc từ .env.
File .env nằm trong .gitignore -> không đi kèm khi push code lên GitHub/chia sẻ repo,
kể cả khi repo public hoặc file zip lỡ lọt ra ngoài. Mỗi máy host phải tự tạo .env
riêng và tự điền UID.

v2: Tự động dọn dấu ngoặc kép/đơn và khoảng trắng thừa quanh giá trị BOT_OWNER_ID.
Lỗi hay gặp nhất là copy-paste UID bị dính dấu ngoặc (VD: BOT_OWNER_ID="123...")
khiến int() parse lỗi -> khoá luôn cả owner thật. Bản này tự dọn sạch trước khi so sánh.
"""

import os
from discord.ext import commands


def _parse_owner_id() -> int | None:
    """Đọc BOT_OWNER_ID từ biến môi trường, tự dọn dấu ngoặc/khoảng trắng/ký tự ẩn thừa."""
    raw = os.getenv("BOT_OWNER_ID", "")
    if not raw:
        return None

    cleaned = raw.strip()

    # Dọn dấu ngoặc kép/đơn thừa nếu lỡ gõ "123..." hoặc '123...'
    if len(cleaned) >= 2 and cleaned[0] in "\"'" and cleaned[-1] in "\"'":
        cleaned = cleaned[1:-1].strip()

    # Discord snowflake chỉ nên là chuỗi số thuần. Không tự nhặt số từ chuỗi lẫn
    # chữ (VD: "abc123") vì dễ che giấu việc cấu hình sai UID.
    if not cleaned.isdigit():
        return None

    try:
        return int(cleaned)
    except ValueError:
        return None


def get_configured_owner_id() -> int | None:
    """Trả về UID owner đã cấu hình (đã dọn sạch), None nếu chưa set hoặc sai định dạng.
    Dùng để bot.py in ra log lúc khởi động, giúp tự kiểm tra BOT_OWNER_ID có đọc đúng không."""
    return _parse_owner_id()


def is_owner_configured() -> bool:
    """True nếu BOT_OWNER_ID đã set đúng định dạng. Dùng để quyết định có nạp các cog
    cấp owner hay không — nếu chưa cấu hình, KHÔNG nạp cog đó luôn (thay vì nạp rồi để
    lệnh tự chặn), tránh lộ ra là server có sẵn các lệnh nguy hiểm nhưng đang mở."""
    return get_configured_owner_id() is not None


def masked_owner_id() -> str:
    """Trả về UID owner đã che bớt để in ra log/console một cách an toàn hơn
    (VD: 12345678901234•••), tránh lộ nguyên UID trong log/terminal/screenshot."""
    owner_id = get_configured_owner_id()
    if owner_id is None:
        return "(chưa cấu hình)"
    raw = str(owner_id)
    if len(raw) <= 4:
        return "•" * len(raw)
    return raw[:-4] + "••••"


def hard_owner_check():
    """Check RIÊNG cho các lệnh cấp cao — khoá cứng theo đúng UID trong BOT_OWNER_ID."""
    async def predicate(ctx: commands.Context) -> bool:
        owner_id = _parse_owner_id()
        if owner_id is None:
            return False
        return ctx.author.id == owner_id
    return commands.check(predicate)
