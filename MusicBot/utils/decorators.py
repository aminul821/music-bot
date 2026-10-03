import time
from functools import wraps

from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
from pyrogram.types import CallbackQuery, Message

import config
from MusicBot.core.clients import bot

_ADMIN_TTL = 300
_admin_cache: dict[int, tuple[float, set[int]]] = {}


async def get_admins(chat_id: int, refresh: bool = False) -> set[int]:
    cached = _admin_cache.get(chat_id)
    if cached and not refresh and time.monotonic() - cached[0] < _ADMIN_TTL:
        return cached[1]
    admins: set[int] = set()
    async for member in bot.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
        if member.status == ChatMemberStatus.OWNER or (
            member.privileges and member.privileges.can_manage_video_chats
        ):
            admins.add(member.user.id)
    _admin_cache[chat_id] = (time.monotonic(), admins)
    return admins


async def is_admin(chat_id: int, user_id: int | None) -> bool:
    if user_id is None:
        return False
    if user_id in config.SUDO_USERS or not config.ADMIN_ONLY:
        return True
    return user_id in await get_admins(chat_id)


def group_only(func):
    @wraps(func)
    async def wrapper(client, message: Message):
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply_text("⚠️ This command only works in groups.")
        return await func(client, message)

    return wrapper


def admin_only(func):
    """Restrict a group command to admins with 'manage video chats' (or sudo users)."""

    @wraps(func)
    async def wrapper(client, message: Message):
        if message.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply_text("⚠️ This command only works in groups.")
        if message.sender_chat and message.sender_chat.id == message.chat.id:
            # Anonymous admin
            return await func(client, message)
        user_id = message.from_user.id if message.from_user else None
        if not await is_admin(message.chat.id, user_id):
            return await message.reply_text("🔒 Only admins with <b>Manage Video Chats</b> can do that.")
        return await func(client, message)

    return wrapper


async def callback_is_admin(query: CallbackQuery) -> bool:
    if await is_admin(query.message.chat.id, query.from_user.id):
        return True
    await query.answer("🔒 Only admins can use these buttons.", show_alert=True)
    return False
