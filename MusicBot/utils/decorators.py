"""Permission levels:

- sudo:     OWNER_ID / SUDO_USERS — everything, everywhere
- admin:    chat admins with "Manage Video Chats" (or the owner) — settings & approvals
- approved: users approved with /approve — playback controls even in admin mode
- everyone: /play (unless play mode is "admins"), /queue, /np
"""
import time
from functools import wraps

from pyrogram.enums import ChatMembersFilter, ChatMemberStatus, ChatType
from pyrogram.types import CallbackQuery, Message

import config
from MusicBot.core import db
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


def is_sudo(user_id: int | None) -> bool:
    return user_id is not None and user_id in config.SUDO_USERS


async def is_admin(chat_id: int, user_id: int | None) -> bool:
    """Chat admin with Manage Video Chats, or sudo."""
    if user_id is None:
        return False
    return is_sudo(user_id) or user_id in await get_admins(chat_id)


async def can_control(chat_id: int, user_id: int | None) -> bool:
    """May pause/skip/stop/etc."""
    if user_id is None:
        return False
    if not db.get(chat_id, "admin_mode") or db.is_approved(chat_id, user_id):
        return True
    return await is_admin(chat_id, user_id)


async def can_play(chat_id: int, user_id: int | None) -> bool:
    """May add tracks with /play."""
    if db.get(chat_id, "play_mode") == "everyone":
        return True
    if user_id is not None and db.is_approved(chat_id, user_id):
        return True
    return await is_admin(chat_id, user_id)


def _is_anon_admin(message: Message) -> bool:
    return bool(message.sender_chat and message.sender_chat.id == message.chat.id)


def _in_group(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def group_only(func):
    @wraps(func)
    async def wrapper(client, message: Message):
        if not _in_group(message):
            return await message.reply_text("⚠️ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
        return await func(client, message)

    return wrapper


def _guard(check, denied: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(client, message: Message):
            if not _in_group(message):
                return await message.reply_text("⚠️ ᴛʜɪs ᴄᴏᴍᴍᴀɴᴅ ᴏɴʟʏ ᴡᴏʀᴋs ɪɴ ɢʀᴏᴜᴘs.")
            if _is_anon_admin(message):
                return await func(client, message)
            user_id = message.from_user.id if message.from_user else None
            if not await check(message.chat.id, user_id):
                return await message.reply_text(denied)
            return await func(client, message)

        return wrapper

    return decorator


# Playback controls: admins + approved users (or everyone when admin mode is off).
control_only = _guard(
    can_control,
    "🔒 <b>ᴀᴅᴍɪɴ ᴍᴏᴅᴇ ɪs ᴏɴ</b>\nOnly admins and approved users can control playback.\n"
    "<i>Ask an admin to</i> <code>/approve</code> <i>you.</i>",
)

# Chat management: real admins (Manage Video Chats) + sudo only.
admin_only = _guard(
    is_admin,
    "🛡 <b>ᴀᴅᴍɪɴs ᴏɴʟʏ</b>\nYou need the <b>Manage Video Chats</b> right to use this.",
)


async def callback_can_control(query: CallbackQuery) -> bool:
    if await can_control(query.message.chat.id, query.from_user.id):
        return True
    await query.answer("🔒 Only admins & approved users can use these buttons.", show_alert=True)
    return False


async def callback_is_admin(query: CallbackQuery) -> bool:
    if await is_admin(query.message.chat.id, query.from_user.id):
        return True
    await query.answer("🛡 Admins only.", show_alert=True)
    return False
