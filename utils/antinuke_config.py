"""
Cấu hình riêng cho hệ thống Anti-Nuke (cogs/anti_nuke.py) và Emoji Manager
(cogs/emoji_manager.py). Đọc từ biến môi trường (.env) — không hard-code.

Đây KHÔNG phải là nơi check quyền chủ bot cấp cao (globalban, lockall...).
Cho việc đó, xem utils/owner_check.py (BOT_OWNER_ID). TRUSTED_IDS ở đây là
một whitelist RIÊNG, có thể gồm nhiều người (chủ bot + admin thật sự tin
tưởng), dùng để loại trừ khỏi hệ thống phát hiện nuke/raid tự động.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _parse_id_list(raw: str) -> set[int]:
    ids = set()
    if not raw:
        return ids
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0") or 0)
ALERT_WEBHOOK_URL = os.getenv("ALERT_WEBHOOK_URL", "").strip()

TRUSTED_IDS = _parse_id_list(os.getenv("TRUSTED_IDS", ""))

ACTION_THRESHOLD = int(os.getenv("ACTION_THRESHOLD", "3"))
ACTION_WINDOW_SECONDS = int(os.getenv("ACTION_WINDOW_SECONDS", "10"))
