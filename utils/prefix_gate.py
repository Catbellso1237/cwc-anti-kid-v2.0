"""
Tách biệt tiền tố lệnh: TOÀN BỘ lệnh (mod, member, tạo/sửa category & kênh...)
dùng '?', RIÊNG lệnh cấp chủ bot (owner) dùng '!'.

Không ảnh hưởng tới slash command (/) — slash luôn hoạt động bình thường ở mọi
trường hợp; phần phân quyền owner cho slash vẫn do hard_owner_check() lo
(xem utils/owner_check.py), không liên quan gì tới file này.

Nếu sau này thêm lệnh owner mới, nhớ thêm TÊN GỐC (root command) của lệnh đó
vào OWNER_COMMAND_ROOTS bên dưới, nếu không lệnh đó sẽ bị coi là lệnh thường
và chỉ nhận tiền tố '?' thay vì '!'.
"""

from discord.ext import commands

OWNER_COMMAND_ROOTS = {
    "globalban", "globalunban", "globalbanlist",
    "createchannels", "deletechannel", "deletechannels", "renameserver",
    "globalannounce", "bridgefilter", "lockall",
}


class WrongPrefixUsage(commands.CheckFailure):
    """Raise khi gọi lệnh bằng sai loại tiền tố (VD: gõ '?' cho lệnh owner, hoặc '!' cho lệnh thường)."""

    def __init__(self, expected_prefix: str):
        self.expected_prefix = expected_prefix
        super().__init__(f"Lệnh này chỉ dùng được với tiền tố `{expected_prefix}` (gõ lại đúng tiền tố).")


def register_prefix_gate(bot: commands.Bot, normal_prefix: str, owner_prefix: str):
    """Gắn 1 check toàn cục vào bot, chặn lệnh nếu gọi sai loại tiền tố."""

    @bot.check
    async def prefix_gate(ctx: commands.Context) -> bool:
        # Slash command không có khái niệm tiền tố -> luôn cho qua
        if ctx.interaction is not None or ctx.command is None:
            return True

        root_name = ctx.command.root_parent.name if ctx.command.root_parent else ctx.command.name
        is_owner_cmd = root_name in OWNER_COMMAND_ROOTS
        expected = owner_prefix if is_owner_cmd else normal_prefix

        if ctx.prefix != expected:
            raise WrongPrefixUsage(expected)
        return True

    return prefix_gate
