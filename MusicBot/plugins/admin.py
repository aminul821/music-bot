from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message
from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup

from MusicBot.core import db, player
from MusicBot.core.clients import assistant
from MusicBot.utils.decorators import admin_only, callback_is_admin, get_admins
from MusicBot.utils.filters import command
from MusicBot.utils.formatters import esc, mention


async def _target_user(client: Client, message: Message):
    """User from a reply, or from an @username / id argument."""
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    if len(message.command) > 1:
        arg = message.command[1]
        try:
            return await client.get_users(int(arg) if arg.lstrip("-").isdigit() else arg)
        except Exception:
            await message.reply_text("❌ ᴜsᴇʀ ɴᴏᴛ ғᴏᴜɴᴅ. Reply to their message or use their @username.")
            return None
    await message.reply_text(
        f"<b>ᴜsᴀɢᴇ:</b> reply to a user with <code>{message.command[0]}</code>\n"
        f"or <code>/{message.command[0]} @username</code>"
    )
    return None


@Client.on_message(command("approve", "auth"))
@admin_only
async def approve_cmd(client: Client, message: Message):
    user = await _target_user(client, message)
    if not user:
        return
    if user.is_bot:
        return await message.reply_text("🤖 Bots can't be approved.")
    new = db.approve(message.chat.id, user.id, user.first_name or str(user.id))
    if not new:
        return await message.reply_text(f"ℹ️ {mention(user)} is already approved.")
    await message.reply_text(
        "╭─❰ ✅ <b>ᴜsᴇʀ ᴀᴘᴘʀᴏᴠᴇᴅ</b> ❱\n"
        f"│ 👤 {mention(user)}\n"
        "│ 🎛 Can now use playback controls\n"
        f"╰─ ʙʏ {mention(message.from_user) if message.from_user else 'Admin'}"
    )


@Client.on_message(command("unapprove", "unauth", "disapprove"))
@admin_only
async def unapprove_cmd(client: Client, message: Message):
    user = await _target_user(client, message)
    if not user:
        return
    if db.unapprove(message.chat.id, user.id):
        await message.reply_text(f"🚫 {mention(user)} is <b>no longer approved</b>.")
    else:
        await message.reply_text(f"ℹ️ {mention(user)} wasn't approved.")


@Client.on_message(command("approved", "authlist", "approvedlist"))
@admin_only
async def approved_cmd(client: Client, message: Message):
    users = db.approved(message.chat.id)
    if not users:
        return await message.reply_text("📭 ɴᴏ ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs ʏᴇᴛ.\nUse <code>/approve</code> on someone.")
    lines = ["╭─❰ 📋 <b>ᴀᴘᴘʀᴏᴠᴇᴅ ᴜsᴇʀs</b> ❱"]
    for i, (uid, name) in enumerate(users.items(), 1):
        lines.append(f'│ {i}. <a href="tg://user?id={uid}">{esc(name, 30)}</a> • <code>{uid}</code>')
    lines.append(f"╰─ ᴛᴏᴛᴀʟ: <b>{len(users)}</b>")
    await message.reply_text("\n".join(lines))


@Client.on_message(command("unapproveall", "clearapproved"))
@admin_only
async def unapprove_all_cmd(client: Client, message: Message):
    n = db.clear_approved(message.chat.id)
    await message.reply_text(f"🧹 Removed <b>{n}</b> approved user(s).")


def _on_off(arg: str) -> bool | None:
    arg = arg.lower()
    if arg in ("on", "yes", "true", "enable", "1"):
        return True
    if arg in ("off", "no", "false", "disable", "0"):
        return False
    return None


@Client.on_message(command("adminmode", "adminonly"))
@admin_only
async def adminmode_cmd(client: Client, message: Message):
    value = _on_off(message.command[1]) if len(message.command) > 1 else None
    if value is None:
        cur = db.get(message.chat.id, "admin_mode")
        return await message.reply_text(
            f"🛡 ᴀᴅᴍɪɴ ᴍᴏᴅᴇ: <b>{'ON' if cur else 'OFF'}</b>\n<b>ᴜsᴀɢᴇ:</b> <code>/adminmode on|off</code>"
        )
    db.set(message.chat.id, "admin_mode", value)
    await message.reply_text(
        "🛡 <b>ᴀᴅᴍɪɴ ᴍᴏᴅᴇ ᴏɴ</b> — only admins & approved users can control playback."
        if value
        else "🔓 <b>ᴀᴅᴍɪɴ ᴍᴏᴅᴇ ᴏғғ</b> — everyone can control playback."
    )


@Client.on_message(command("playmode"))
@admin_only
async def playmode_cmd(client: Client, message: Message):
    arg = message.command[1].lower() if len(message.command) > 1 else ""
    if arg not in ("everyone", "admins", "all", "admin"):
        cur = db.get(message.chat.id, "play_mode")
        return await message.reply_text(
            f"🎵 ᴘʟᴀʏ ᴍᴏᴅᴇ: <b>{cur}</b>\n<b>ᴜsᴀɢᴇ:</b> <code>/playmode everyone|admins</code>"
        )
    mode = "everyone" if arg in ("everyone", "all") else "admins"
    db.set(message.chat.id, "play_mode", mode)
    await message.reply_text(
        "🎵 <b>ᴘʟᴀʏ ᴍᴏᴅᴇ: ᴇᴠᴇʀʏᴏɴᴇ</b> — anyone can add songs."
        if mode == "everyone"
        else "🎵 <b>ᴘʟᴀʏ ᴍᴏᴅᴇ: ᴀᴅᴍɪɴs</b> — only admins & approved users can add songs."
    )


# ---------------------------------------------------------------- settings panel


def _settings_text(chat_id: int, title: str) -> str:
    admin_mode = db.get(chat_id, "admin_mode")
    play_mode = db.get(chat_id, "play_mode")
    return (
        "╭─❰ ⚙️ <b>sᴇᴛᴛɪɴɢs</b> ❱\n"
        f"│ 💬 {esc(title, 40)}\n"
        "│\n"
        f"│ 🛡 ᴀᴅᴍɪɴ ᴍᴏᴅᴇ  ➜ <b>{'ON' if admin_mode else 'OFF'}</b>\n"
        f"│    <i>{'admins & approved control playback' if admin_mode else 'everyone controls playback'}</i>\n"
        f"│ 🎵 ᴘʟᴀʏ ᴍᴏᴅᴇ   ➜ <b>{play_mode.upper()}</b>\n"
        f"│    <i>{'anyone can add songs' if play_mode == 'everyone' else 'admins & approved add songs'}</i>\n"
        f"│ ✅ ᴀᴘᴘʀᴏᴠᴇᴅ    ➜ <b>{len(db.approved(chat_id))}</b> user(s)\n"
        "╰─ <i>tap a button to toggle</i>"
    )


def _settings_markup(chat_id: int) -> InlineKeyboardMarkup:
    admin_mode = db.get(chat_id, "admin_mode")
    play_mode = db.get(chat_id, "play_mode")
    return InlineKeyboardMarkup(
        [
            [Btn(f"🛡 Admin mode: {'ON ✅' if admin_mode else 'OFF ❌'}", callback_data="set:admin_mode")],
            [Btn(f"🎵 Play mode: {play_mode.title()}", callback_data="set:play_mode")],
            [Btn("📋 Approved users", callback_data="set:approved"), Btn("🗑 Close", callback_data="close")],
        ]
    )


@Client.on_message(command("settings", "config"))
@admin_only
async def settings_cmd(client: Client, message: Message):
    await message.reply_text(
        _settings_text(message.chat.id, message.chat.title or ""), reply_markup=_settings_markup(message.chat.id)
    )


@Client.on_callback_query(filters.regex(r"^set:"))
async def settings_cb(client: Client, query: CallbackQuery):
    if not await callback_is_admin(query):
        return
    chat_id = query.message.chat.id
    key = query.data.split(":", 1)[1]
    if key == "admin_mode":
        db.set(chat_id, "admin_mode", not db.get(chat_id, "admin_mode"))
    elif key == "play_mode":
        db.set(chat_id, "play_mode", "admins" if db.get(chat_id, "play_mode") == "everyone" else "everyone")
    elif key == "approved":
        users = db.approved(chat_id)
        names = ", ".join(users.values()) if users else "none yet"
        return await query.answer(f"Approved: {names}"[:200], show_alert=True)
    await query.answer("✅ Updated")
    try:
        await query.message.edit_text(
            _settings_text(chat_id, query.message.chat.title or ""), reply_markup=_settings_markup(chat_id)
        )
    except Exception:
        pass


# ---------------------------------------------------------------- assistant & cache


@Client.on_message(command("userbotjoin", "assistantjoin"))
@admin_only
async def userbot_join_cmd(client: Client, message: Message):
    msg = await message.reply_text("🔄 ᴀᴅᴅɪɴɢ ᴀssɪsᴛᴀɴᴛ…")
    try:
        await player.ensure_assistant(message.chat.id)
    except player.PlayerError as e:
        return await msg.edit_text(str(e))
    await msg.edit_text(f"✅ ᴀssɪsᴛᴀɴᴛ {assistant.me.mention} ɪs ʜᴇʀᴇ.")


@Client.on_message(command("userbotleave", "assistantleave"))
@admin_only
async def userbot_leave_cmd(client: Client, message: Message):
    await player.stop(message.chat.id)
    player.forget_chat(message.chat.id)
    try:
        await assistant.leave_chat(message.chat.id)
    except Exception as e:
        return await message.reply_text(f"❌ <code>{esc(str(e), 150)}</code>")
    await message.reply_text("👋 ᴀssɪsᴛᴀɴᴛ ʟᴇғᴛ ᴛʜᴇ ᴄʜᴀᴛ.")


@Client.on_message(command("reload", "admincache"))
@admin_only
async def reload_cmd(client: Client, message: Message):
    admins = await get_admins(message.chat.id, refresh=True)
    await message.reply_text(f"🔄 <b>ᴀᴅᴍɪɴ ʟɪsᴛ ʀᴇғʀᴇsʜᴇᴅ</b> — {len(admins)} admin(s) with voice chat rights.")
