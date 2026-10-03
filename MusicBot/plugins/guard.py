"""Keep the bot private to the groups listed in ALLOWED_CHATS."""
from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

import config

GUARD_GROUP = -100  # runs before every other handler


def _blocked(chat) -> bool:
    return (
        bool(config.ALLOWED_CHATS)
        and chat is not None
        and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL)
        and chat.id not in config.ALLOWED_CHATS
    )


@Client.on_message(filters.all, group=GUARD_GROUP)
async def guard_messages(client: Client, message: Message):
    if not _blocked(message.chat):
        return
    try:
        await message.reply_text(
            f"🔒 <b>{config.BOT_NAME}</b> is a private bot, only for the <b>Mad Family</b> group.\n"
            "👋 Leaving this chat…"
        )
    except Exception:
        pass
    try:
        await client.leave_chat(message.chat.id)
    except Exception:
        pass
    message.stop_propagation()


@Client.on_callback_query(group=GUARD_GROUP)
async def guard_callbacks(client: Client, query: CallbackQuery):
    if query.message and _blocked(query.message.chat):
        await query.answer("🔒 Private bot.", show_alert=True)
        query.stop_propagation()
