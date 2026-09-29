# CWC Anti Kid — Bản Gộp (Moderation + Anti-Nuke + Economy + Bridge Chat)

Bot Discord tổng hợp từ 3 repo: **Cwc-Anti-Kid**, **Anti-raid-System-Nuke-Bot-Controller-**,
và **Bot-Setup-Auto-Economy-**. Hỗ trợ cả prefix lẫn slash command (`/`) cùng lúc, kèm phản
hồi bằng emoji cho từng hành động.

> **Tiền tố lệnh:** toàn bộ lệnh trong bảng bên dưới (không ghi rõ tiền tố) đều dùng `?`
> (VD: `?ban`, `?autosetup`, `?rules`...), đổi được qua `NORMAL_PREFIX` trong `.env`.
> Một số lệnh quản trị cấp cao được khoá riêng cho đúng 1 người (`BOT_OWNER_ID`) và
> **không liệt kê công khai trong README này** — xem trực tiếp trong code nếu bạn là
> người vận hành bot.

## ⚠️ Lưu ý khi gộp

Bản gốc `cogs/setup.py` của repo **Bot-Setup-Auto-Economy-** (tạo category/kênh theo
`config.json`) bị thiếu trong file zip ban đầu. Tính năng này đã được **viết lại từ đầu**
thành `cogs/category_setup.py` (xem mục "Tạo category & kênh hàng loạt" bên dưới) và dùng
chung tiền tố `?` với mọi lệnh thường khác — có thể không giống 100% bản gốc nhưng tương
đương về chức năng.

Lệnh `?rules` cũng đã được đổi từ gọi Gemini AI sang đọc nội dung có sẵn trong 3 file `.txt`
(xem mục "Rules" bên dưới) — không cần `GEMINI_API_KEY` nữa.

## ✨ Tính năng

### 🛡️ Điều hành cơ bản (`cogs/moderation.py`)
| Lệnh | Mô tả |
|---|---|
| `kick <member> [reason]` | Kick thành viên |
| `ban <member> [reason]` | Ban thành viên |
| `unban <user_id> [reason]` | Gỡ ban |
| `mute <member> [minutes]` | Timeout thành viên |
| `unmute <member>` | Gỡ timeout |
| `warn` / `warnings` / `clearwarn` | Hệ thống cảnh báo |
| `purge <số lượng>` | Xóa hàng loạt tin nhắn |
| `lock` / `unlock` | Khóa/mở khóa 1 kênh |
| `slowmode <giây>` | Bật/tắt slowmode |

### 🚨 Chống raid & bot giả dạng (`cogs/anti_raid.py`, `cogs/anti_link.py`)
- Tự phát hiện bot có tên nhái theo bot mod nổi tiếng, không tick verified
- Tự phát hiện join ồ ạt (raid) và khóa server tạm thời
- `autodefense on/off` — bật/tắt tự phòng vệ 24/7
- `setmodlog #kênh`, `trustbot @bot`
- `antilink on/off`, `antilinkwhitelist`, `antilinkchannel` — chống spam link

### 🔒 Anti-Nuke — giám sát audit log real-time (`cogs/anti_nuke.py`)
Khác với anti-raid (chống join ồ ạt), Anti-Nuke bảo vệ server khỏi **tài khoản/bot đã có quyền
cao rồi âm thầm phá hoại**:
1. Nghe `on_audit_log_entry_create` real-time — không cần polling
2. Đếm hành động nguy hiểm (xóa kênh/role, ban/kick, tạo webhook...) theo cửa sổ thời gian
   (mặc định 3 hành động / 10 giây) — vượt ngưỡng thì coi là tấn công
3. Giám sát riêng việc cấp quyền Administrator — phát hiện là xử lý ngay, không cần chờ đủ ngưỡng
4. Phản ứng tự động: tước toàn bộ role nguy hiểm, ban khỏi server, khóa tạm `@everyone`, gửi
   cảnh báo tới kênh log + webhook ngoài (nếu cấu hình)

| Lệnh | Mô tả |
|---|---|
| `antinukeunlock` | Mở khóa server sau khi Anti-Nuke tự động lockdown |
| `trust <user_id>` | Thêm ID vào whitelist tin tưởng (tạm thời, nhớ cập nhật `.env`) |
| `status` | Xem trạng thái bảo vệ hiện tại |

> Whitelist (`TRUSTED_IDS`) tách biệt hoàn toàn với `BOT_OWNER_ID` — có thể gồm nhiều admin
> thật sự tin tưởng, không giới hạn 1 người.

### 😀 Quản lý Application Emoji (`cogs/emoji_manager.py`)
Gõ `?emoji` để mở panel quản lý emoji gắn liền với bot (dùng được ở mọi server bot có mặt):
➕ Thêm — ✏️ Đổi tên — 🗑️ Xóa — 🔄 Làm mới — ✖️ Đóng. Toàn bộ thao tác bằng nút bấm/form, không
cần gõ lệnh text. Chỉ `TRUSTED_IDS`, `BOT_OWNER_ID`, hoặc chủ sở hữu application mới dùng được.

### 💰 Economy — SQLite (`cogs/economy.py`)
Dữ liệu lưu ở `data/economy.db`, không mất khi restart bot.

| Lệnh | Mô tả |
|---|---|
| `balance` (`bal`) | Xem ví + ngân hàng |
| `daily` | Nhận thưởng hàng ngày (lần đầu thưởng lớn) |
| `work` | Đi làm kiếm xu (cooldown 1 tiếng) |
| `deposit` (`dep`) / `withdraw` (`with`) | Gửi/rút tiền vào ngân hàng |
| `pay <member> <amount>` | Chuyển xu |
| `rob <member>` | Trộm xu (cooldown 3 tiếng) |
| `shop` / `buy <item>` / `inventory` (`inv`) | Cửa hàng vật phẩm |
| `leaderboard` (`lb`, `top`) | Bảng xếp hạng giàu nhất |

### 📜 Rules — nội dung có sẵn, không cần AI (`cogs/rules.py`)
```
?rules <thấp|trung bình|cao> [#kênh]
?rules cao #rules
```
Nội dung lấy trực tiếp từ 3 file `.txt` trong `data/`, không gọi API ngoài:
- `data/rules_thap.txt` (🟢 Nhẹ nhàng)
- `data/rules_trungbinh.txt` (🟡 Trung bình)
- `data/rules_cao.txt` (🔴 Nghiêm khắc)

Muốn đổi nội dung nội quy: sửa thẳng 3 file `.txt` này, không cần sửa code hay xin API key.

### 🗂️ Tạo category & kênh hàng loạt (`cogs/category_setup.py`)
Bù lại phần `cogs/setup.py` gốc của Bot-Setup-Auto-Economy- bị thiếu trong lần gộp trước,
đây là bộ lệnh tạo/sửa category + kênh, dùng chung tiền tố `?` như mọi lệnh thường khác.

| Lệnh | Mô tả |
|---|---|
| `?autosetup` | Tạo toàn bộ category + kênh theo template trong `config.json` (bỏ qua cái đã tồn tại) |
| `?addcategory <tên>` | Tạo 1 category mới |
| `?addchannel <tên> [text\|voice] [danh_mục]` | Tạo 1 kênh mới |
| `?renamechannel #kênh <tên_mới>` | Đổi tên kênh |
| `?renamecategory TÊN CŨ \| TÊN MỚI` | Đổi tên category |

Tất cả lệnh trên yêu cầu quyền **Administrator**. Sửa `config.json` ở thư mục gốc để tùy
chỉnh template category/kênh mặc định của `?autosetup`.

### 🌉 Cầu nối chat xuyên server (`cogs/chat_bridge.py`)
`bridgesetup`, `bridgeoff`, `bridgestatus` — webhook forwarding giữ tên/avatar người gửi thật.

### 👑 Lệnh cấp chủ bot
Có 1 nhóm cog riêng cho các thao tác nguy hiểm/cấp toàn cục (ban trên nhiều server, khoá toàn
bộ server, quản lý kênh hàng loạt...), khoá cứng theo đúng 1 UID owner. Nhóm cog này **chỉ được
nạp khi UID owner đã cấu hình hợp lệ** — nếu chưa cấu hình, các lệnh đó không tồn tại trên bot
luôn (không phải bị chặn quyền, mà là chưa từng được nạp). Tên lệnh cụ thể, tiền tố, và cách
hoạt động **không liệt kê ở đây** — xem `cogs/global_admin.py`, `cogs/lockall.py`, và
`utils/owner_check.py` nếu bạn là người vận hành bot.

UID owner được set qua `.env` (`BOT_OWNER_ID`) — file `.env` không nằm trong Git/zip khi chia
sẻ repo, nên UID này không đi kèm code, mỗi máy host phải tự tạo `.env` riêng và điền UID.

> ⚠️ **Nếu bạn fork repo này về CHỈ ĐỂ ĐỌC/HỌC CODE** (cách tổ chức cog, logic anti-nuke,
> economy, bridge chat...) — cứ tự nhiên, không cần đổi gì cả.
>
> **Nếu bạn fork về để TỰ CHẠY bot cho server của mình**, bạn bắt buộc phải tự tạo `.env` và
> điền `BOT_OWNER_ID` bằng UID Discord của chính bạn — bot sẽ không có ai điều khiển được lệnh
> cấp cao cho tới khi bạn làm việc này. Không set `BOT_OWNER_ID` không có nghĩa "an toàn hơn" —
> nó chỉ khiến nhóm lệnh cấp cao không được nạp, dùng bình thường thì vẫn cần điền đúng UID
> của chính bạn.

## 🛠️ Cài đặt

1. Cài thư viện:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy `.env.example` thành `.env`, điền:
   - `DISCORD_TOKEN` (bắt buộc)
   - `BOT_OWNER_ID` (bắt buộc cho lệnh cấp cao)
   - `TRUSTED_IDS` (khuyến nghị — whitelist cho Anti-Nuke)
3. (Tùy chọn) Sửa `config.json` để tùy chỉnh template category/kênh mặc định của `?autosetup`
4. Chạy:
   ```bash
   python bot.py
   ```

## 📁 Cấu trúc thư mục

```
cogs/
  moderation.py      anti_raid.py       anti_link.py
  anti_nuke.py        emoji_manager.py   setup.py
  category_setup.py   economy.py         rules.py
  chat_bridge.py       global_admin.py    lockall.py
  info.py              ping.py            events.py
utils/
  antinuke_config.py  database.py        owner_check.py
  prefix_gate.py       guild_config.py    bridge_data.py
  global_data.py       storage.py         emojis.py
config.json   (template category/kênh cho ?autosetup)
data/
  shop.json                economy.db (tự sinh khi chạy)
  rules_thap.txt           rules_trungbinh.txt      rules_cao.txt
```

Toàn bộ ngưỡng phát hiện, danh sách whitelist, tên lệnh cấp owner, và cách hoạt động chi tiết
**không** được liệt kê trong README này — xem trực tiếp trong code (`cogs/anti_nuke.py`,
`utils/owner_check.py`, `cogs/global_admin.py`, `cogs/lockall.py`) nếu bạn là người vận hành
bot và cần điều chỉnh.
