"""Per-chat playback queues and track state."""
import asyncio
import random
import time
from dataclasses import dataclass, field


@dataclass
class Track:
    title: str
    duration: int  # seconds, 0 for unknown/live
    source: str  # YouTube URL or local file path
    requested_by: str  # HTML mention of the requester
    video: bool = False
    vidid: str | None = None
    thumb: str | None = None
    link: str | None = None
    path: str | None = None  # local file once downloaded
    download: asyncio.Task | None = field(default=None, repr=False)
    # playback position bookkeeping
    started_at: float = 0.0
    paused_at: float = 0.0
    offset: int = 0  # seconds skipped via /seek

    def elapsed(self) -> int:
        if not self.started_at:
            return 0
        now = self.paused_at or time.monotonic()
        return int(now - self.started_at) + self.offset

    def mark_started(self, offset: int = 0) -> None:
        self.started_at = time.monotonic()
        self.paused_at = 0.0
        self.offset = offset

    def mark_paused(self) -> None:
        if not self.paused_at:
            self.paused_at = time.monotonic()

    def mark_resumed(self) -> None:
        if self.paused_at:
            self.started_at += time.monotonic() - self.paused_at
            self.paused_at = 0.0


@dataclass
class ChatState:
    tracks: list[Track] = field(default_factory=list)
    loop: int = 0  # remaining repeats of the current track
    volume: int = 100
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    @property
    def current(self) -> Track | None:
        return self.tracks[0] if self.tracks else None

    @property
    def paused(self) -> bool:
        return bool(self.current and self.current.paused_at)

    def shuffle(self) -> None:
        upcoming = self.tracks[1:]
        random.shuffle(upcoming)
        self.tracks[1:] = upcoming


_states: dict[int, ChatState] = {}


def get(chat_id: int) -> ChatState:
    state = _states.get(chat_id)
    if state is None:
        state = _states[chat_id] = ChatState()
    return state


def active_chats() -> list[int]:
    return [cid for cid, s in _states.items() if s.tracks]


def clear(chat_id: int) -> None:
    state = _states.pop(chat_id, None)
    if state:
        for track in state.tracks:
            if track.download and not track.download.done():
                track.download.cancel()
        state.tracks.clear()
        state.loop = 0
