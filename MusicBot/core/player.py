"""Voice chat playback engine: joins calls, streams tracks and advances the queue."""
import asyncio
import logging

from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import (
    ChatAdminRequired,
    InviteRequestSent,
    UserAlreadyParticipant,
    UserNotParticipant,
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
}.get(config.AUDIO_QUALITY, AudioQuality.STUDIO)

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


async def ensure_assistant(chat_id: int) -> None:
    """Make sure the assistant account is a member of the chat."""
    if chat_id in _joined:
        return
    me = assistant.me
    try:
        member = await bot.get_chat_member(chat_id, me.id)
        if member.status == ChatMemberStatus.BANNED:
            raise PlayerError(
                f"🚫 Assistant {me.mention} is banned here. Unban it and try again."
            )
        if member.status != ChatMemberStatus.LEFT:
            _joined.add(chat_id)
            return
    except UserNotParticipant:
        pass

    chat = await bot.get_chat(chat_id)
    try:
        if chat.username:
            await assistant.join_chat(chat.username)
        else:
            try:
                link = await bot.export_chat_invite_link(chat_id)
            except ChatAdminRequired:
                raise PlayerError(
                    "⚠️ I need to be an admin with <b>Invite Users</b> permission "
                    "to add my assistant to this chat."
                )
            await assistant.join_chat(link)
    except UserAlreadyParticipant:
        pass
    except InviteRequestSent:
        try:
            await bot.approve_chat_join_request(chat_id, me.id)
        except Exception:
            raise PlayerError(f"⏳ Approve the join request of {me.mention} and try again.")
    except PlayerError:
        raise
    except Exception as e:
        raise PlayerError(f"❌ Assistant couldn't join this chat: <code>{esc(str(e), 200)}</code>")

    await asyncio.sleep(1)
    try:
        await assistant.get_chat(chat_id)  # cache the peer for pytgcalls
    except Exception:
        pass
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


async def _play_current(chat_id: int, offset: int = 0, announce: bool = True) -> None:
    state = queue.get(chat_id)
    track = state.current
    path = await _prepare(track)
    await call.play(chat_id, _stream(path, track.video, offset))
    track.mark_started(offset)
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
                await _safe_send(
                    chat_id,
                    f"⚠️ Couldn't play <b>{esc(failed.title)}</b>, skipping.\n"
                    f"<code>{esc(str(e), 200)}</code>",
                )
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
