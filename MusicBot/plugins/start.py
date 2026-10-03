from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

import config
from MusicBot.utils.decorators import callback_can_control
from MusicBot.utils.buttons import back_markup, help_markup, start_markup
from MusicBot.utils.filters import command

HELP_MAIN = (
    "╭─❰ 📖 <b>ʜᴇʟᴘ ᴍᴇɴᴜ</b> ❱\n"
    "│ Pick a category below ✨\n"
    "│\n"
    "│ Prefixes ➜ <code>/</code> <code>!</code> <code>.</code> <code>;</code>\n"
    "│ e.g. <code>;play</code>, <code>.skip</code>, <code>;approve</code>\n"
    f"╰─ 💞 <i>{config.BOT_NAME}</i>"
)

HELP_PAGES = {
    "play": (
        "╭─❰ 🎵 <b>ᴘʟᴀʏ</b> ❱\n"
        "│ <code>/play</code> <i>name | link | playlist</i>\n"
        "│    ➜ stream audio from YouTube\n"
        "│ <code>/play</code> <i>(reply to audio/voice)</i>\n"
        "│    ➜ play a Telegram file\n"
        "│ <code>/stream</code> <i>direct link / radio / m3u8</i>\n"
        "│    ➜ play any audio link\n"
        "│ <code>/playforce</code> <i>name</i> 🛡\n"
        "│    ➜ skip current & play now\n"
        "╰─ ⚡ <i>tracks pre-download for gapless playback</i>"
    ),
    "video": (
        "╭─❰ 📺 <b>ᴠɪᴅᴇᴏ</b> ❱\n"
        "│ <code>/vplay</code> <i>name | YouTube link</i>\n"
        "│    ➜ stream video in the voice chat\n"
        "│ <code>/vplay</code> <i>(reply to a video)</i>\n"
        "│    ➜ play a Telegram video file\n"
        "│ <code>/vstream</code> <i>direct link / m3u8 / live</i>\n"
        "│    ➜ stream any video link or live TV\n"
        "│ <code>/vplayforce</code> <i>name</i> 🛡\n"
        "│    ➜ skip current & play video now\n"
        "╰─ 💎 <i>up to 4K, set with VIDEO_QUALITY</i>"
    ),
    "controls": (
        "╭─❰ 🎛 <b>ᴄᴏɴᴛʀᴏʟs</b> ❱ <i>(admins & approved)</i>\n"
        "│ <code>/pause</code> • <code>/resume</code>\n"
        "│ <code>/skip</code> ➜ next track\n"
        "│ <code>/stop</code> ➜ clear queue & leave\n"
        "│ <code>/seek 1:30</code> • <code>/seek +30</code> • <code>/seek -10</code>\n"
        "│ <code>/volume 1-200</code>\n"
        "│ <code>/loop [1-10 | off]</code>\n"
        "╰─ 🎚 <i>or just use the buttons on the player</i>"
    ),
    "queue": (
        "╭─❰ 📜 <b>ǫᴜᴇᴜᴇ</b> ❱\n"
        "│ <code>/queue</code> ➜ show the queue\n"
        "│ <code>/np</code> ➜ now playing + progress\n"
        "│ <code>/shuffle</code> ➜ shuffle upcoming\n"
        "│ <code>/remove 2</code> ➜ remove a track\n"
        "╰─ <code>/clear</code> ➜ clear upcoming tracks"
    ),
    "admin": (
        "╭─❰ 🛡 <b>ᴀᴅᴍɪɴ ᴏɴʟʏ</b> ❱\n"
        "│ <code>/approve</code> <i>(reply | @user)</i>\n"
        "│    ➜ let a user control playback\n"
        "│ <code>/unapprove</code> • <code>/approved</code> • <code>/unapproveall</code>\n"
        "│ <code>/adminmode on|off</code>\n"
        "│    ➜ who can pause/skip/stop\n"
        "│ <code>/playmode everyone|admins</code>\n"
        "│    ➜ who can add songs\n"
        "│ <code>/settings</code> ➜ toggle panel\n"
        "│ <code>/userbotjoin</code> • <code>/userbotleave</code>\n"
        "╰─ <code>/reload</code> ➜ refresh admin list"
    ),
    "other": (
        "╭─❰ ⚙️ <b>ᴏᴛʜᴇʀ</b> ❱\n"
        "│ <code>/ping</code> ➜ latency & uptime\n"
        "│ <code>/stats</code> ➜ active chats (sudo)\n"
        "│ <code>/setcookies</code> ➜ fix YouTube blocks (sudo)\n"
        "│\n"
        "│ <code>/id</code> ➜ chat & user id\n"
        "│\n"
        "│ <b>sᴇᴛᴜᴘ:</b> make me admin with\n"
        "│ <i>Manage Video Chats, Invite Users,</i>\n"
        "│ <i>Delete Messages, Add New Admins</i>\n"
        "╰─ 🔒 private bot for the Mad Family group"
    ),
}


@Client.on_message(command("start") & filters.private)
async def start_private(client: Client, message: Message):
    me = client.me
    text = (
        f"<b>ʜᴇʏ {message.from_user.mention} 👋</b>\n\n"
        f"<blockquote>🎧 ɪ'ᴍ <b>{config.BOT_NAME}</b>\n"
        "ᴛʜᴇ ᴘʀɪᴠᴀᴛᴇ ᴍᴜsɪᴄ ᴘʟᴀʏᴇʀ ᴏғ ᴛʜᴇ <b>ᴍᴀᴅ ғᴀᴍɪʟʏ</b> ᴠᴏɪᴄᴇ ᴄʜᴀᴛ 💞</blockquote>\n\n"
        "╭─❰ ✨ <b>ғᴇᴀᴛᴜʀᴇs</b> ❱\n"
        "│ 🎵 YouTube songs, links & playlists\n"
        "│ 📺 Video streaming up to 4K\n"
        "│ 🔗 Direct links, radio & live streams\n"
        "│ ⚡ Pre-buffered, gapless playback\n"
        "│ 🎛 Live player with progress bar\n"
        "│ 🛡 Admin mode & approved users\n"
        "╰─ 📜 Queue • loop • shuffle • seek • volume\n\n"
        "<i>Come to the Mad Family voice chat and send</i> <code>/play song name</code> 🚀"
    )
    markup = start_markup(me.username)
    if config.START_IMG:
        try:
            return await message.reply_photo(config.START_IMG, caption=text, reply_markup=markup)
        except Exception:
            pass
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


@Client.on_message(command("start") & filters.group)
async def start_group(client: Client, message: Message):
    await message.reply_text(
        f"🎶 <b>{config.BOT_NAME}</b>\n<i>ɪ'ᴍ ᴀʟɪᴠᴇ & ʀᴇᴀᴅʏ ᴛᴏ ᴘʟᴀʏ!</i>\n\n"
        "<code>/play song name</code> ➜ audio\n"
        "<code>/vplay song name</code> ➜ video\n"
        "<code>/help</code> ➜ all commands"
    )


@Client.on_message(command("help"))
async def help_cmd(client: Client, message: Message):
    await message.reply_text(HELP_MAIN, reply_markup=help_markup())


@Client.on_callback_query(filters.regex(r"^help:"))
async def help_cb(client: Client, query: CallbackQuery):
    page = query.data.split(":", 1)[1]
    if page == "main":
        text, markup = HELP_MAIN, help_markup()
    else:
        text, markup = HELP_PAGES.get(page, HELP_MAIN), back_markup()
    try:
        if query.message.photo:
            await query.message.edit_caption(text, reply_markup=markup)
        else:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass
    await query.answer()


@Client.on_callback_query(filters.regex(r"^close$"))
async def close_cb(client: Client, query: CallbackQuery):
    if query.message.chat.type != ChatType.PRIVATE:
        if not await callback_can_control(query):
            return
    try:
        await query.message.delete()
    except Exception:
        await query.answer("Can't delete this message.")
