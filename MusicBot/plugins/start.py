from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message

import config
from MusicBot.utils.decorators import callback_is_admin
from MusicBot.utils.buttons import back_markup, help_markup, start_markup
from MusicBot.utils.filters import command

HELP_MAIN = (
    "<b>📖 Help Menu</b>\n\n"
    "Pick a category below to see its commands.\n"
    "Commands work with <code>/</code>, <code>!</code> or <code>.</code> prefixes."
)

HELP_PAGES = {
    "play": (
        "<b>🎵 Play Commands</b>\n\n"
        "• <code>/play</code> <i>song name | YouTube link | playlist</i> — stream audio\n"
        "• <code>/vplay</code> <i>song name | YouTube link</i> — stream video\n"
        "• Reply <code>/play</code> to an audio/voice file — play it\n"
        "• Reply <code>/vplay</code> to a video file — play it\n"
        "• <code>/playforce</code> <i>query</i> — skip current & play now (admins)\n\n"
        "<i>Audio is streamed in studio quality (up to 96 kHz stereo); "
        "tracks are pre-downloaded for gapless, lag-free playback.</i>"
    ),
    "controls": (
        "<b>🎛 Playback Controls</b> <i>(admins)</i>\n\n"
        "• <code>/pause</code> — pause playback\n"
        "• <code>/resume</code> — resume playback\n"
        "• <code>/skip</code> — next track\n"
        "• <code>/stop</code> or <code>/end</code> — clear queue & leave\n"
        "• <code>/seek</code> <i>1:30</i> — jump to a position\n"
        "• <code>/volume</code> <i>1-200</i> — set volume\n"
        "• <code>/loop</code> <i>[1-10 | off]</i> — repeat current track"
    ),
    "queue": (
        "<b>📜 Queue</b>\n\n"
        "• <code>/queue</code> — show the queue\n"
        "• <code>/np</code> — now playing with progress\n"
        "• <code>/shuffle</code> — shuffle upcoming tracks (admins)\n"
        "• <code>/remove</code> <i>position</i> — remove a track (admins)\n"
        "• <code>/clear</code> — clear upcoming tracks (admins)"
    ),
    "other": (
        "<b>⚙️ Other</b>\n\n"
        "• <code>/ping</code> — bot latency & status\n"
        "• <code>/reload</code> — refresh admin list\n"
        "• <code>/stats</code> — active voice chats (sudo)\n\n"
        "<b>Setup:</b> add me as admin with <i>Manage Video Chats</i>, "
        "<i>Invite Users</i> and <i>Delete Messages</i>. "
        "My assistant joins automatically."
    ),
}


@Client.on_message(command("start") & filters.private)
async def start_private(client: Client, message: Message):
    me = client.me
    text = (
        f"<b>👋 Hey {message.from_user.mention}!</b>\n\n"
        f"I'm <b>{me.first_name}</b> — a fast, high-quality music player for "
        "Telegram voice chats.\n\n"
        "✨ <b>Features</b>\n"
        "├ 🎧 Studio-grade audio (96 kHz stereo)\n"
        "├ 📺 Up to 4K video streaming\n"
        "├ ⚡ Pre-downloaded, gapless playback\n"
        "├ 📜 Queue, loop, shuffle, seek & volume\n"
        "└ 🎛 Inline control panel\n\n"
        "Add me to a group and send <code>/play song name</code> to begin!"
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
        "🎶 <b>I'm alive and ready to play!</b>\nUse <code>/play song name</code> or /help."
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
        if not await callback_is_admin(query):
            return
    try:
        await query.message.delete()
    except Exception:
        await query.answer("Can't delete this message.")
