"""🌿 Touch Grass: get the Mad Family out of the voice chat and into the sun.

- /touchgrass [place]  ➜ a short outing plan: best weather window before sunset, real
                          nearby parks/trails from OpenStreetMap, written by a local model
- /sethome <place>      ➜ where the group usually heads out from (admins)
- /touched              ➜ send or reply to an outdoor photo; the local vision model checks
                          it's really outside and counts a day on your streak
- /grassboard           ➜ the group's streaks
- After GRASS_NUDGE_HOURS of non-stop voice chat, the bot nudges everyone outside.

The model runs on Ollama on your own machine, so plans and photos never reach a third party.
"""
import asyncio
import html
import json
import logging
import time
from datetime import date, timedelta

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.types import CallbackQuery, Message
from pyrogram.types import InlineKeyboardButton as Btn
from pyrogram.types import InlineKeyboardMarkup

import config
from MusicBot.core import db, llm, outdoors, queue
from MusicBot.core.clients import bot
from MusicBot.utils.decorators import is_admin
from MusicBot.utils.filters import command
from MusicBot.utils.formatters import esc, mention

LOGGER = logging.getLogger("MusicBot.grass")

PLAN_SYSTEM = (
    "You are the outdoors buddy of a Telegram music group. Write a short, warm plan that gets "
    "people off their screens and outside. Use ONLY the places, times and weather in the facts; "
    "never invent a place. Plain text, no markdown, no hashtags, at most 90 words. Include: where "
    "to go (one spot, or two for a walk between them), when, one thing to bring, and one small "
    "outdoor mission (e.g. find three different leaves, spot a bird, watch the sunset). "
    "If the weather is bad, say so honestly and suggest the least-bad window."
)

PHOTO_PROMPT = (
    "Someone says they just went outside and sent this photo as proof. Look at it carefully. "
    "outdoors: true only if the photo was clearly taken outside (sky, plants, grass, trees, "
    "streets, water, trails). screenshot: true if it is a screenshot, a photo of a screen, a "
    "stock or AI-looking image, or a photo of a printed picture. nature: up to 4 short names "
    "of natural things you can see (e.g. 'oak leaves', 'pigeon', 'cumulus clouds'). comment: "
    "one friendly, specific sentence about what you see (max 25 words)."
)

PHOTO_SCHEMA = {
    "type": "object",
    "properties": {
        "outdoors": {"type": "boolean"},
        "screenshot": {"type": "boolean"},
        "nature": {"type": "array", "items": {"type": "string"}},
        "comment": {"type": "string"},
    },
    "required": ["outdoors", "screenshot", "nature", "comment"],
}

# message id -> {user_id: first name}  (RSVPs on a plan)
_rsvps: dict[tuple[int, int], dict[int, str]] = {}


# ---------------------------------------------------------------- helpers


def _location_of(message: Message | None):
    if not message:
        return None
    if message.venue:
        return message.venue.location
    return message.location


async def _resolve_place(message: Message) -> outdoors.Place | None:
    """Place from: reply to a location, the command argument, or the group's home."""
    loc = _location_of(message.reply_to_message) or _location_of(message)
    if loc:
        return outdoors.Place("your pin", loc.latitude, loc.longitude, "the shared location")
    if len(message.command) > 1:
        return await outdoors.geocode(" ".join(message.command[1:]))
    home = db.grass_home(message.chat.id)
    if home:
        return outdoors.Place(home["name"], home["lat"], home["lon"], home["name"])
    return None


def _fmt_dist(m: int) -> str:
    return f"{m} m" if m < 1000 else f"{m / 1000:.1f} km"


def _walk_min(m: int) -> int:
    return max(1, round(m / 80))  # ~4.8 km/h


def _facts(place: outdoors.Place, fc: outdoors.Forecast, window: list, spots: list) -> dict:
    return {
        "starting_point": place.label or place.name,
        "local_time_now": fc.now.strftime("%a %H:%M"),
        "plan_for": "tomorrow (it's dark now)" if fc.tomorrow else "today",
        "sunset": fc.sunset.strftime("%a %H:%M"),
        "daylight_left_minutes": int(fc.daylight_left().total_seconds() // 60),
        "best_window": [
            {"time": h.time.strftime("%a %H:%M"), "temp_c": round(h.temp), "rain_chance": h.rain_chance,
             "sky": h.sky, "wind_kmh": round(h.wind)}
            for h in window
        ],
        "nearby_spots": [
            {"name": s.name, "type": s.kind, "distance": _fmt_dist(s.distance), "walk_minutes": _walk_min(s.distance)}
            for s in spots
        ],
    }


def _fallback_plan(facts: dict) -> str:
    """Used when the local model is offline: still a useful plan, just less chatty."""
    w = facts["best_window"]
    spot = facts["nearby_spots"][0] if facts["nearby_spots"] else None
    when = f"around {w[0]['time']} ({w[0]['temp_c']}°C, {w[0]['sky']})" if w else "before sunset"
    where = f"{spot['name']} ({spot['walk_minutes']} min walk)" if spot else "the nearest green patch"
    return f"Head to {where} {when}. Bring water. Mission: find three different kinds of leaves. Sunset is {facts['sunset']}."


def _plan_markup(spots: list, count: int = 0) -> InlineKeyboardMarkup:
    rows = [[Btn(f"🙋 ɪ'ᴍ ɪɴ ({count})" if count else "🙋 ɪ'ᴍ ɪɴ", callback_data="grass:in")]]
    rows += [[Btn(f"🗺 {s.name[:28]}", url=s.map_url)] for s in spots[:2]]
    return InlineKeyboardMarkup(rows)


async def build_plan(place: outdoors.Place) -> tuple[str, list]:
    fc, spots = await asyncio.gather(
        outdoors.forecast(place.lat, place.lon),
        outdoors.nearby_spots(place.lat, place.lon),
        return_exceptions=True,
    )
    if isinstance(fc, Exception):
        raise fc
    if isinstance(spots, Exception):
        LOGGER.warning("Overpass lookup failed: %s", spots)
        spots = []
    window = outdoors.best_window(fc)
    facts = _facts(place, fc, window, spots)
    try:
        plan = await llm.chat("Facts (JSON):\n" + json.dumps(facts, ensure_ascii=False), system=PLAN_SYSTEM)
        source = f"🧠 <i>{esc(config.GRASS_MODEL, 30)} · local</i>"
    except llm.LLMError as e:
        LOGGER.warning("Plan model unavailable: %s", e)
        plan, source = _fallback_plan(facts), "📐 <i>offline plan (model unreachable)</i>"

    lines = [f"🌿 <b>ᴛᴏᴜᴄʜ ɢʀᴀss</b> ➜ <b>{esc(place.label or place.name, 50)}</b>", ""]
    if window:
        a, b = window[0], window[-1]
        lines.append(
            f"⏰ <b>Best window:</b> {a.time:%H:%M}–{(b.time + timedelta(hours=1)):%H:%M} · "
            f"{round(a.temp)}°C · {a.sky} · 🌧 {max(h.rain_chance for h in window)}%"
        )
    left = int(fc.daylight_left().total_seconds() // 60)
    if fc.tomorrow:
        lines.append(f"🌙 <b>It's dark now.</b> Plan for tomorrow · sunrise {fc.sunrise:%H:%M}, sunset {fc.sunset:%H:%M}")
    else:
        lines.append(f"🌇 <b>Sunset:</b> {fc.sunset:%H:%M} ({left // 60}h {left % 60}m of light left)")
    for s in spots[:4]:
        lines.append(f"📍 {esc(s.name, 40)} <i>({s.kind}, {_fmt_dist(s.distance)})</i>")
    lines += ["", f"<blockquote>{html.escape(plan)}</blockquote>", source]
    return "\n".join(lines), spots


# ---------------------------------------------------------------- commands


@Client.on_message(command("touchgrass", "outside", "grass"))
async def touchgrass_cmd(client: Client, message: Message):
    try:
        place = await _resolve_place(message)
    except outdoors.OutdoorsError as e:
        return await message.reply_text(f"❌ {esc(str(e), 200)}")
    if not place:
        return await message.reply_text(
            "🌿 <b>Where are you?</b>\n"
            "<code>/touchgrass Dhaka</code> • reply to a 📍 location with <code>/touchgrass</code>\n"
            "Admins can save the group's spot with <code>/sethome place</code>."
        )
    msg = await message.reply_text("🌱 <i>Checking the sky and the map…</i>")
    try:
        text, spots = await build_plan(place)
    except outdoors.OutdoorsError as e:
        return await msg.edit_text(f"❌ Couldn't get the weather: {esc(str(e), 200)}")
    await msg.edit_text(text, reply_markup=_plan_markup(spots), disable_web_page_preview=True)


@Client.on_message(command("sethome"))
async def sethome_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else None
    if message.chat.type != ChatType.PRIVATE and not await is_admin(message.chat.id, user_id):
        return await message.reply_text("🛡 Only admins can set the group's home spot.")
    try:
        loc = _location_of(message.reply_to_message)
        if loc:
            place = outdoors.Place("Group spot", loc.latitude, loc.longitude, "Group spot")
        elif len(message.command) > 1:
            place = await outdoors.geocode(" ".join(message.command[1:]))
        else:
            return await message.reply_text("<b>Usage:</b> <code>/sethome Dhaka</code> or reply to a 📍 location.")
    except outdoors.OutdoorsError as e:
        return await message.reply_text(f"❌ {esc(str(e), 200)}")
    db.set_grass_home(message.chat.id, place.label or place.name, place.lat, place.lon)
    await message.reply_text(
        f"🏡 <b>Home spot saved:</b> {esc(place.label or place.name, 60)}\n"
        "<code>/touchgrass</code> now plans from here, and nudges know when the sun sets."
    )


@Client.on_message(command("touched", "proof"))
async def touched_cmd(client: Client, message: Message):
    target = message if message.photo else message.reply_to_message
    if not target or not target.photo:
        return await message.reply_text(
            "📸 <b>Prove it!</b> Send a photo from outside with the caption <code>/touched</code>, "
            "or reply to your photo with <code>/touched</code>.\n"
            "<i>Checked by a model on our own server. Your photo isn't sent anywhere else.</i>"
        )
    user = target.from_user or message.from_user
    if not user or not message.from_user or user.id != message.from_user.id:
        return await message.reply_text("🙅 You can only log your own photos.")
    if target.forward_date:
        return await message.reply_text("🙅 Forwarded photos don't count. Take a fresh one outside!")
    msg = await message.reply_text("🔍 <i>Looking at your photo…</i>")
    try:
        photo = await target.download(in_memory=True)
        verdict = await llm.chat_json(PHOTO_PROMPT, PHOTO_SCHEMA, images=[bytes(photo.getbuffer())])
    except llm.LLMError as e:
        LOGGER.warning("Photo check failed: %s", e)
        return await msg.edit_text(
            "🤖 The local vision model isn't available right now, so I can't check photos.\n"
            f"<i>Ask the owner to run</i> <code>ollama pull {esc(config.GRASS_MODEL, 40)}</code>."
        )
    comment = esc(str(verdict.get("comment", "")), 200)
    if not verdict.get("outdoors") or verdict.get("screenshot"):
        return await msg.edit_text(f"🏠 <b>Not quite outside…</b>\n<i>{comment}</i>\n\nGo get some real sky! ☀️")
    today = date.today()
    rec, new = db.log_grass(
        message.chat.id, user.id, user.first_name or "User", today.isoformat(), (today - timedelta(days=1)).isoformat()
    )
    nature = ", ".join(esc(str(n), 30) for n in (verdict.get("nature") or [])[:4])
    head = "✅ <b>ɢʀᴀss ᴛᴏᴜᴄʜᴇᴅ!</b>" if new else "✅ <b>Already counted today</b>, but nice shot!"
    await msg.edit_text(
        f"{head} {mention(user)}\n"
        f"<i>{comment}</i>\n"
        + (f"🔎 Spotted: {nature}\n" if nature else "")
        + f"\n🔥 Streak: <b>{rec['streak']}</b> day{'s' * (rec['streak'] != 1)} · 🏆 best {rec['best']} · 🌿 {rec['total']} total"
    )


@Client.on_message(command("grassboard", "streaks"))
async def grassboard_cmd(client: Client, message: Message):
    board = db.grass_board(message.chat.id)
    if not board:
        return await message.reply_text("🌱 Nobody has touched grass yet. Be the first: <code>/touched</code> with a photo!")
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    rows = sorted(board.values(), key=lambda r: (r["last"] >= yesterday and r["streak"], r["total"]), reverse=True)
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🌿 <b>ɢʀᴀss ʙᴏᴀʀᴅ</b>\n"]
    for i, r in enumerate(rows[:10]):
        live = r["streak"] if r["last"] >= yesterday else 0
        lines.append(
            f"{medals[i] if i < 3 else f'{i + 1}.'} <b>{esc(r['name'], 25)}</b> ➜ 🔥 {live} · 🏆 {r['best']} · 🌿 {r['total']}"
        )
    await message.reply_text("\n".join(lines))


# ---------------------------------------------------------------- buttons


@Client.on_callback_query(filters.regex(r"^grass:in$"))
async def rsvp_cb(client: Client, query: CallbackQuery):
    key = (query.message.chat.id, query.message.id)
    people = _rsvps.setdefault(key, {})
    if people.pop(query.from_user.id, None):
        await query.answer("👋 You're out.")
    else:
        people[query.from_user.id] = query.from_user.first_name or "Someone"
        await query.answer("🌿 See you outside! " + ", ".join(people.values())[:150])
    markup = query.message.reply_markup
    if markup and markup.inline_keyboard:
        row = markup.inline_keyboard[0]
        row[0] = Btn(f"🙋 ɪ'ᴍ ɪɴ ({len(people)})" if people else "🙋 ɪ'ᴍ ɪɴ", callback_data="grass:in")
        try:
            await query.message.edit_reply_markup(markup)
        except Exception:
            pass


@Client.on_callback_query(filters.regex(r"^grass:plan$"))
async def plan_cb(client: Client, query: CallbackQuery):
    home = db.grass_home(query.message.chat.id)
    if not home:
        return await query.answer("Set a home spot first: /sethome <place>", show_alert=True)
    await query.answer("🌱 Planning…")
    try:
        text, spots = await build_plan(outdoors.Place(home["name"], home["lat"], home["lon"], home["name"]))
    except outdoors.OutdoorsError as e:
        return await query.message.reply_text(f"❌ Couldn't get the weather: {esc(str(e), 200)}")
    await query.message.reply_text(text, reply_markup=_plan_markup(spots), disable_web_page_preview=True)


# ---------------------------------------------------------------- nudges

_vc_since: dict[int, float] = {}
_nudged_on: dict[int, str] = {}


async def _nudge(chat_id: int, hours: float) -> None:
    text = f"☀️ <b>ʜᴇʏ ᴍᴀᴅ ғᴀᴍɪʟʏ!</b> The voice chat has been going for <b>{hours:.1f}h</b>.\n"
    home = db.grass_home(chat_id)
    markup = None
    if home:
        fc = await outdoors.forecast(home["lat"], home["lon"])
        left = int(fc.daylight_left().total_seconds() // 60)
        if fc.tomorrow or left < 45:
            return  # it's dark: no point nagging, try again tomorrow
        now = fc.hours[0] if fc.hours else None
        if now and outdoors.hour_score(now) < 30:
            return  # storm or downpour: let them keep listening
        text += f"There's <b>{left // 60}h {left % 60}m</b> of daylight left"
        text += f" ({round(now.temp)}°C, {now.sky}). " if now else ". "
        text += "Pause the music, go touch some grass 🌿"
        markup = InlineKeyboardMarkup([[Btn("🌿 ᴘʟᴀɴ ᴀ ᴡᴀʟᴋ", callback_data="grass:plan")]])
    else:
        text += "Pause the music and step outside for 20 minutes 🌿\n<i>Admins: /sethome place for weather-aware nudges.</i>"
    await bot.send_message(chat_id, text, reply_markup=markup)


async def _nudge_loop() -> None:
    while True:
        await asyncio.sleep(600)
        try:
            active = set(queue.active_chats())
            for cid in list(_vc_since):
                if cid not in active:
                    _vc_since.pop(cid)
            now = time.monotonic()
            today = date.today().isoformat()
            for cid in active:
                start = _vc_since.setdefault(cid, now)
                hours = (now - start) / 3600
                if hours >= config.GRASS_NUDGE_HOURS and _nudged_on.get(cid) != today:
                    _nudged_on[cid] = today
                    await _nudge(cid, hours)
        except Exception as e:
            LOGGER.warning("Touch-grass nudge failed: %s", e)


def start_nudger() -> None:
    if config.GRASS_NUDGE_HOURS > 0:
        asyncio.get_running_loop().create_task(_nudge_loop())
