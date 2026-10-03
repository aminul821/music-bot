import html


def fmt_time(seconds: int) -> str:
    if seconds <= 0:
        return "LIVE"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_time(text: str) -> int | None:
    """Parse '90', '1:30' or '1:02:30' into seconds."""
    try:
        parts = [int(p) for p in text.strip().split(":")]
    except ValueError:
        return None
    if not parts or len(parts) > 3 or any(p < 0 for p in parts):
        return None
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def progress_bar(elapsed: int, total: int, length: int = 14) -> str:
    if total <= 0:
        return "🔴 ━━━━━━━━ LIVE ━━━━━━━━"
    ratio = min(max(elapsed / total, 0), 1)
    pos = min(int(ratio * length), length - 1)
    return "━" * pos + "●" + "─" * (length - pos - 1)


def esc(text: str, limit: int = 60) -> str:
    text = text if len(text) <= limit else text[: limit - 1] + "…"
    return html.escape(text)


def mention(user) -> str:
    if user is None:
        return "Anonymous"
    name = esc(user.first_name or "User", 30)
    return f'<a href="tg://user?id={user.id}">{name}</a>'
