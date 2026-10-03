"""Voice chat playback engine: joins calls, streams tracks and advances the queue."""
import asyncio
import logging

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChannelPrivate,
    ChatAdminRequired,
    InviteHashExpired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserBannedInChannel,
)
from pyrogram.types import Message
from pytgcalls import filters as fl
from pytgcalls.exceptions import NotInCallError
from pytgcalls.types import AudioQuality, ChatUpdate, MediaStream, StreamEnded, VideoQuality

import config
from MusicBot.core import queue, youtube
from MusicBot.core.clients import assistant, bot, call
from MusicBot.core.queue import Track
from MusicBot.utils.buttons import player_markup
from MusicBot.utils.formatters import esc, fmt_time

LOGGER = logging.getLogger("MusicBot.player")

AUDIO_QUALITY = {
    "studio": AudioQuality.STUDIO,
    "high": AudioQuality.HIGH,
    "medium": AudioQuality.MEDIUM,
    "low": AudioQuality.LOW,
}.get(config.AUDIO_QUALITY, AudioQuality.HIGH)

VIDEO_QUALITY = {
    "4k": VideoQuality.UHD_4K,
    "2k": VideoQuality.QHD_2K,
    "1080": VideoQuality.FHD_1080p,
    "720": VideoQuality.HD_720p,
    "480": VideoQuality.SD_480p,
    "360": VideoQuality.SD_360p,
}.get(config.VIDEO_QUALITY, VideoQuality.FHD_1080p)

QUALITY_LABEL = f"{AUDIO_QUALITY.value[0] // 1000} kHz {'Stereo' if AUDIO_QUALITY.value[1] == 2 else 'Mono'}"

# Last "now playing" card per chat, deleted when the next one is sent.
_np_messages: dict[int, Message] = {}
# Chats where the assistant is known to be a member.
_joined: set[int] = set()


class PlayerError(Exception):
    pass


# ---------------------------------------------------------------- assistant


async def _assistant_knows(chat_id: int) -> bool:
    """True if the assistant has the chat cached and is a member of it."""
    try:
        member = await assistant.get_chat_member(chat_id, "me")
    except Exception:  # UserNotParticipant, PeerIdInvalid, ChannelInvalid...
        return False
    return member.status not in (ChatMemberStatus.BANNED, ChatMemberStatus.LEFT)


async def _invite_link(chat_id: int) -> str:
    chat = await bot.get_chat(chat_id)
    if chat.username:
        return chat.username
    if chat.invite_link:
        return chat.invite_link
    try:
        # A separate link, so the group's primary invite link is never revoked.
        link = await bot.create_chat_invite_link(chat_id, name="Music assistant")
        return link.invite_link
    except ChatAdminRequired:
        raise PlayerError(
            "⚠️ I need to be an admin with <b>Invite Users</b> permission "
            "to add my assistant to this chat."
        )


async def _unban_assistant(chat_id: int) -> bool:
    me = assistant.me
    try:
        # Bots can only reach the assistant by username (they've never "met" it by id).
        await bot.unban_chat_member(chat_id, me.username or me.id)
        return True
    except Exception:
        return False


async def ensure_assistant(chat_id: int) -> None:
    """Make sure the assistant account is in the chat and knows its peer."""
    if chat_id in _joined:
        return
    if await _assistant_knows(chat_id):
        _joined.add(chat_id)
        return

    me = assistant.me
    target = await _invite_link(chat_id)
    for attempt in range(2):
        try:
            await assistant.join_chat(target)
            break
        except UserAlreadyParticipant:
            break
        except InviteRequestSent:
            try:
                await bot.approve_chat_join_request(chat_id, me.username or me.id)
            except Exception:
                raise PlayerError(f"⏳ Approve the join request of {me.mention} and try again.")
            break
        except (UserBannedInChannel, ChannelPrivate, InviteHashExpired) as e:
            if attempt == 0 and await _unban_assistant(chat_id):
                continue
            raise PlayerError(
                f"🚫 Assistant {me.mention} can't join (it may be banned). "
                f"Unban it and try again.\n<code>{type(e).__name__}</code>"
            )
        except Exception as e:
            raise PlayerError(f"❌ Assistant couldn't join this chat: <code>{esc(str(e), 200)}</code>")

    # Resolving through the link/username stores the chat's access hash for the assistant.
    try:
        await assistant.get_chat(target)
    except Exception:
        pass
    if not await _assistant_knows(chat_id):
        await asyncio.sleep(2)
        async for _ in assistant.get_dialogs(limit=100):
            pass
        if not await _assistant_knows(chat_id):
            raise PlayerError(
                f"❌ Assistant {me.mention} couldn't access this chat. "
                "Try again in a few seconds, or add it to the group manually."
            )
    _joined.add(chat_id)


# ---------------------------------------------------------------- streams


def _prefetch(track: Track) -> None:
    """Start downloading a YouTube track in the background so it's ready instantly."""
    if track.path or track.download or not track.vidid or track.duration == 0:
        return
    track.download = asyncio.create_task(youtube.download(track.source, track.vidid, track.video))


async def _prepare(track: Track) -> str:
    if track.path:
        return track.path
    if track.vidid and track.duration == 0:  # live stream: resolve a fresh URL
        return await youtube.download(track.source, track.vidid, track.video, live=True)
    _prefetch(track)
    track.path = await track.download
    return track.path


def _stream(path: str, video: bool, offset: int = 0) -> MediaStream:
    return MediaStream(
        path,
        audio_parameters=AUDIO_QUALITY,
        video_parameters=VIDEO_QUALITY,
        video_flags=MediaStream.Flags.AUTO_DETECT if video else MediaStream.Flags.IGNORE,
        ffmpeg_parameters=f"-ss {offset}" if offset else None,
    )


async def _check_can_speak(chat_id: int) -> None:
    """Warn the chat if the assistant is in the call but muted by an admin."""
    await asyncio.sleep(4)
    try:
        participants = await call.get_participants(chat_id) or []
    except Exception:
        return
    me = assistant.me
    for p in participants:
        if p.user_id == me.id and p.muted_by_admin:
            await _safe_send(
                chat_id,
                f"🔇 <b>My assistant {me.mention} is muted in the voice chat</b>, so nobody can hear the music.\n"
                "Unmute it in the voice chat (tap its name → <i>Allow to speak</i>), "
                "or make it an admin with <b>Manage Video Chats</b>.",
            )
            return


async def _play_current(chat_id: int, offset: int = 0, announce: bool = True) -> None:
    state = queue.get(chat_id)
    track = state.current
    path = await _prepare(track)
    LOGGER.info("Playing %r in %s from %s", track.title, chat_id, path)
    await call.play(chat_id, _stream(path, track.video, offset))
    track.mark_started(offset)
    try:
        await call.unmute(chat_id)
    except Exception:
        pass
    asyncio.create_task(_check_can_speak(chat_id))
    if state.volume != 100:
        try:
            await call.change_volume_call(chat_id, state.volume)
        except Exception:
            pass
    if announce:
        await send_now_playing(chat_id)
    if len(state.tracks) > 1:
        _prefetch(state.tracks[1])


async def _advance(chat_id: int, error_chat_notice: bool = True) -> None:
    """Play the current queue head, skipping tracks that fail. Leaves the call when empty."""
    state = queue.get(chat_id)
    while state.tracks:
        try:
            await _play_current(chat_id)
            return
        except Exception as e:
            failed = state.tracks.pop(0)
            state.loop = 0
            LOGGER.warning("Failed to play %s in %s: %s", failed.title, chat_id, e)
            if error_chat_notice:
                detail = str(e) if str(e) == youtube.BOT_CHECK_HELP else f"<code>{esc(str(e), 200)}</code>"
                await _safe_send(chat_id, f"⚠️ Couldn't play <b>{esc(failed.title)}</b>, skipping.\n{detail}")
    await stop(chat_id, notify=True)


# ---------------------------------------------------------------- public API


async def enqueue(chat_id: int, track: Track) -> int:
    """Add a track. Returns 0 if it started playing now, else its queue position."""
    state = queue.get(chat_id)
    async with state.lock:
        if len(state.tracks) > config.QUEUE_LIMIT:
            raise PlayerError(f"📛 Queue is full ({config.QUEUE_LIMIT} tracks).")
        state.tracks.append(track)
        position = len(state.tracks) - 1
        if position == 0:
            try:
                await _play_current(chat_id)
            except Exception:
                queue.clear(chat_id)
                raise
        elif position == 1:
            _prefetch(track)
        return position


async def skip(chat_id: int) -> Track | None:
    """Skip the current track. Returns the new current track (None if queue ended)."""
    state = queue.get(chat_id)
    async with state.lock:
        if not state.tracks:
            return None
        state.loop = 0
        state.tracks.pop(0)
        await _advance(chat_id)
        return state.current


async def on_stream_end(chat_id: int) -> None:
    state = queue.get(chat_id)
    async with state.lock:
        if not state.tracks:
            return
        cur = state.current
        played = cur.elapsed() - cur.offset
        LOGGER.info("Stream ended in %s after %ss: %r", chat_id, played, cur.title)
        if played < 5 and cur.duration > 15:
            # ffmpeg exited right away: the file couldn't be read/decoded.
            LOGGER.warning("Playback of %s ended immediately (path=%s)", cur.title, cur.path)
            await _safe_send(
                chat_id,
                f"⚠️ <b>{esc(cur.title)}</b> stopped right after starting — the audio file couldn't be "
                "decoded. Check that <code>ffmpeg</code> is installed on the server.",
            )
            state.loop = 0
        if state.loop > 0:
            state.loop -= 1
        else:
            state.tracks.pop(0)
        await _advance(chat_id)


async def stop(chat_id: int, notify: bool = False) -> None:
    queue.clear(chat_id)
    old = _np_messages.pop(chat_id, None)
    if old:
        await _safe_delete(old)
    try:
        await call.leave_call(chat_id)
    except (NotInCallError, Exception):
        pass
    if notify:
        await _safe_send(chat_id, "✅ Queue finished. Left the voice chat.")


async def pause(chat_id: int) -> bool:
    state = queue.get(chat_id)
    if not state.current or state.paused:
        return False
    await call.pause(chat_id)
    state.current.mark_paused()
    return True


async def resume(chat_id: int) -> bool:
    state = queue.get(chat_id)
    if not state.current or not state.paused:
        return False
    await call.resume(chat_id)
    state.current.mark_resumed()
    return True


async def seek(chat_id: int, position: int) -> None:
    state = queue.get(chat_id)
    async with state.lock:
        track = state.current
        if not track:
            raise PlayerError("❌ Nothing is playing.")
        if track.duration == 0:
            raise PlayerError("❌ Can't seek in a live stream.")
        position = max(0, min(position, track.duration - 5))
        await _play_current(chat_id, offset=position, announce=False)


async def set_volume(chat_id: int, volume: int) -> int:
    volume = max(1, min(volume, 200))
    await call.change_volume_call(chat_id, volume)
    queue.get(chat_id).volume = volume
    return volume


# ---------------------------------------------------------------- UI


async def send_now_playing(chat_id: int) -> None:
    state = queue.get(chat_id)
    track = state.current
    if not track:
        return
    upcoming = state.tracks[1] if len(state.tracks) > 1 else None
    kind = "📺 Video" if track.video else "🎧 Audio"
    title = f'<a href="{track.link}">{esc(track.title)}</a>' if track.link else f"<b>{esc(track.title)}</b>"
    caption = (
        f"<b>▶️ Now Streaming</b>  •  {kind}\n\n"
        f"🎵 {title}\n"
        f"⏱ <b>Duration:</b> <code>{fmt_time(track.duration)}</code>\n"
        f"💎 <b>Quality:</b> <code>{QUALITY_LABEL}"
        f"{' • ' + VIDEO_QUALITY.name.split('_')[-1] if track.video else ''}</code>\n"
        f"👤 <b>Requested by:</b> {track.requested_by}"
    )
    if upcoming:
        caption += f"\n⏭ <b>Up next:</b> {esc(upcoming.title, 45)}"

    old = _np_messages.pop(chat_id, None)
    if old:
        await _safe_delete(old)

    markup = player_markup(paused=False, loop=state.loop > 0)
    msg = None
    if track.thumb:
        try:
            msg = await bot.send_photo(chat_id, track.thumb, caption=caption, reply_markup=markup)
        except Exception:
            msg = None
    if msg is None:
        msg = await _safe_send(chat_id, caption, reply_markup=markup)
    if msg:
        _np_messages[chat_id] = msg


async def _safe_send(chat_id: int, text: str, **kwargs) -> Message | None:
    try:
        return await bot.send_message(chat_id, text, disable_web_page_preview=True, **kwargs)
    except Exception as e:
        LOGGER.debug("send_message failed in %s: %s", chat_id, e)
        return None


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


# ---------------------------------------------------------------- pytgcalls updates


@call.on_update(fl.stream_end(StreamEnded.Type.AUDIO))
async def _stream_end_handler(_, update: StreamEnded):
    await on_stream_end(update.chat_id)


@call.on_update(fl.chat_update(ChatUpdate.Status.LEFT_CALL))
async def _left_call_handler(_, update: ChatUpdate):
    if update.status & (ChatUpdate.Status.KICKED | ChatUpdate.Status.LEFT_GROUP):
        _joined.discard(update.chat_id)
    queue.clear(update.chat_id)
    old = _np_messages.pop(update.chat_id, None)
    if old:
        await _safe_delete(old)
