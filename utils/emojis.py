"""
Bảng emoji dùng chung cho bot.

v2.0: Bot sẽ TỰ ĐỘNG lấy toàn bộ emoji bạn đã set trong Discord Developer Portal
(tab "Emoji" của app) khi khởi động, không cần copy tay ID nữa.

Cách hoạt động:
  1. Bạn upload emoji gif vào Developer Portal -> tab Emoji, đặt TÊN emoji trùng với
     các key bên dưới (success, warn, error, kick, ban, unban, mute, unmute, purge,
     lock, unlock, slowmode, info, loading, raid, shield, fakebot, coin, daily, work,
     pay, leaderboard, ping, pong, link).
  2. Khi bot chạy, hàm load_application_emojis() trong bot.py sẽ gọi Discord API lấy
     toàn bộ emoji của app, tự map theo tên vào _runtime_emojis.
  3. Hàm e(key) sẽ ưu tiên: emoji tự fetch được (Developer Portal) -> emoji khai báo tay
     trong EMOJI_ANIMATED -> emoji Unicode tĩnh EMOJI_STATIC. Không tìm thấy cái nào thì
     rơi về Unicode để không bao giờ bị lỗi hiển thị.

Không cần sửa gì thêm ở đây nếu chỉ muốn dùng emoji đã set trong Developer Portal —
chỉ cần đặt đúng TÊN emoji khi upload là bot tự nhận.
"""

import os

USE_ANIMATED = os.getenv("USE_ANIMATED_EMOJI", "true").lower() == "true"

# Cache runtime, được đổ dữ liệu bởi load_application_emojis() lúc bot khởi động
_runtime_emojis: dict[str, str] = {}


EMOJI_STATIC = {
    "success": "✅",
    "warn": "⚠️",
    "error": "❌",
    "kick": "👢",
    "ban": "🔨",
    "unban": "🕊️",
    "mute": "🔇",
    "unmute": "🔊",
    "purge": "🧹",
    "lock": "🔒",
    "unlock": "🔓",
    "slowmode": "🐢",
    "info": "ℹ️",
    "loading": "⏳",
    "raid": "🚨",       # phát hiện raid / vào ồ ạt
    "shield": "🛡️",     # auto-defense đang bật
    "fakebot": "🎭",    # phát hiện bot giả dạng
    "coin": "🪙",        # đơn vị tiền tệ economy
    "daily": "🎁",       # nhận thưởng hàng ngày
    "work": "💼",        # đi làm kiếm xu
    "pay": "💸",         # chuyển xu cho người khác
    "leaderboard": "🏆", # bảng xếp hạng giàu nhất
    "ping": "📡",        # lệnh kiểm tra độ trễ bot
    "pong": "🏓",        # phản hồi ping
    "link": "🔗",        # anti-link
    "bridge": "🌉",      # cầu nối chat xuyên server
}

# Điền tay nếu muốn (fallback khi chưa fetch được từ Developer Portal), có thể để trống.
EMOJI_ANIMATED = {
    "success": "", "warn": "", "error": "", "kick": "", "ban": "", "unban": "",
    "mute": "", "unmute": "", "purge": "", "lock": "", "unlock": "", "slowmode": "",
    "info": "", "loading": "", "raid": "", "shield": "", "fakebot": "",
    "coin": "", "daily": "", "work": "", "pay": "", "leaderboard": "",
    "ping": "", "pong": "", "link": "", "bridge": "",
}


async def load_application_emojis(bot) -> int:
    """
    Gọi API Discord để lấy toàn bộ emoji đã set trong Developer Portal (tab Emoji)
    của chính con bot này, rồi map vào cache runtime theo tên.
    Trả về số lượng emoji đã map được. Gọi 1 lần lúc bot on_ready.
    """
    global _runtime_emojis
    try:
        app_emojis = await bot.fetch_application_emojis()
    except Exception as ex:
        print(f"{EMOJI_STATIC['error']} Không thể fetch application emoji: {ex}")
        return 0

    matched = 0
    known_keys = set(EMOJI_STATIC.keys())
    for emj in app_emojis:
        name_key = emj.name.lower()
        _runtime_emojis[name_key] = str(emj)
        if name_key in known_keys:
            matched += 1

    print(f"{EMOJI_STATIC['success']} Đã fetch {len(app_emojis)} emoji từ Developer Portal, khớp {matched} key đang dùng trong bot.")
    return matched


def e(key: str, animated: bool | None = None) -> str:
    """
    Lấy emoji theo tên (key), theo thứ tự ưu tiên:
    1. Emoji tự fetch từ Developer Portal (_runtime_emojis) - nếu USE_ANIMATED đang bật.
    2. Emoji khai báo tay trong EMOJI_ANIMATED - nếu USE_ANIMATED đang bật.
    3. Emoji Unicode tĩnh trong EMOJI_STATIC.

    animated=True/False có thể ép riêng cho 1 lần gọi, bỏ qua cấu hình USE_ANIMATED chung.
    """
    use_gif = USE_ANIMATED if animated is None else animated

    if use_gif:
        runtime = _runtime_emojis.get(key)
        if runtime:
            return runtime
        manual = EMOJI_ANIMATED.get(key, "")
        if manual:
            return manual

    return EMOJI_STATIC.get(key, EMOJI_STATIC["info"])

