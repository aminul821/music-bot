"""Keep the bot private: it works in ALLOWED_CHATS and in groups the owner/sudo added it to.

If anyone else adds the bot to a group, it says it's only for Mad Family and leaves.
"""
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

import config
from MusicBot.core import db
from MusicBot.utils.decorators import is_sudo
from MusicBot.utils.filters import command

GUARD_GROUP = -100  # runs before every other handler


def _locked() -> bool:
    return bool(config.ALLOWED_CHATS)


def is_allowed(chat_id: int) -> bool:
    return not _locked() or chat_id in config.ALLOWED_CHATS or chat_id in db.allowed_chats()


def _is_group(chat) -> bool:
    return chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)


def _added_me(client: Client, message: Message) -> bool:
    return any(u.id == client.me.id for u in (message.new_chat_members or []))


async def _reject(client: Client, message: Message) -> None:
    try:
        await message.reply_text(
            f"🔒 <b>{config.BOT_NAME}</b>\n\n"
            "❌ <b>ᴛʜɪs ʙᴏᴛ ɪs ᴏɴʟʏ ᴍᴀᴅᴇ ғᴏʀ ᴍᴀᴅ ғᴀᴍɪʟʏ</b> 💞\n"
            "👋 <i>Leaving this group…</i>"
        )
    except Exception:
        pass
    try:
        await client.leave_chat(message.chat.id)
    except Exception:
        pass


@Client.on_message(filters.all, group=GUARD_GROUP)
async def guard_messages(client: Client, message: Message):
    chat = message.chat
    if not _is_group(chat) or is_allowed(chat.id):
        return
    user_id = message.from_user.id if message.from_user else None
    if is_sudo(user_id):
        # The owner added the bot here (or is using it here): allow this group from now on.
        db.allow_chat(chat.id)
        if _added_me(client, message):
            await message.reply_text(
                f"💞 <b>{config.BOT_NAME}</b>\n\n"
                "✅ <b>ᴀᴅᴅᴇᴅ ʙʏ ᴛʜᴇ ᴏᴡɴᴇʀ</b> — this group is unlocked!\n"
                "<i>Make me admin and send</i> <code>/play song name</code> 🎶"
            )
            message.stop_propagation()
        return
    await _reject(client, message)
    message.stop_propagation()


@Client.on_callback_query(group=GUARD_GROUP)
async def guard_callbacks(client: Client, query: CallbackQuery):
    if query.message and _is_group(query.message.chat) and not is_allowed(query.message.chat.id):
        await query.answer("🔒 This bot is only made for Mad Family.", show_alert=True)
        query.stop_propagation()


@Client.on_message(command("allowchat", "allowgroup"))
async def allow_cmd(client: Client, message: Message):
    if not (message.from_user and is_sudo(message.from_user.id)) or not _is_group(message.chat):
        return
    db.allow_chat(message.chat.id)
    await message.reply_text("✅ <b>ɢʀᴏᴜᴘ ᴀʟʟᴏᴡᴇᴅ</b> — I'll work here.")


@Client.on_message(command("disallowchat", "disallowgroup"))
async def disallow_cmd(client: Client, message: Message):
    if not (message.from_user and is_sudo(message.from_user.id)) or not _is_group(message.chat):
        return
    db.disallow_chat(message.chat.id)
    if message.chat.id in config.ALLOWED_CHATS:
        return await message.reply_text("ℹ️ This group is in <code>ALLOWED_CHATS</code> (.env), remove it there.")
    await message.reply_text("👋 <b>ɢʀᴏᴜᴘ ʀᴇᴍᴏᴠᴇᴅ</b> — leaving.")
    await client.leave_chat(message.chat.id)
