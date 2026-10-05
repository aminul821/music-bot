---
title: Our Telegram music bot now tells us to go outside (local Gemma 3 + OpenStreetMap)
published: false
tags: devchallenge, hf26challenge
---

*This is a submission for the [Hacktoberfest Open-Source AI Challenge Week 1: Touch Grass](https://dev.to/challenges/hacktoberfest-week1-2026-10-05)*

## What I Built

**Mad Family Music Bot** is the private music bot of our Telegram group. It plays songs in
the group voice chat, and it's very good at keeping us there for hours. So I gave it a
conscience: **Touch Grass mode**.

- 🌿 **`/touchgrass`** finds the best 2-hour weather window before sunset and real nearby
  parks, gardens, trails and viewpoints, then writes a short plan with one small mission
  ("find three different leaves", "watch the sunset from the viewpoint"). Friends tap
  **🙋 I'm in**.
- 📸 **`/touched`**: send a photo from outside. A local vision model checks it was really
  taken outdoors (screenshots and photos of a screen are rejected), says what it spotted
  ("banyan tree, crow"), and grows your streak. **`/grassboard`** turns it into a group
  competition.
- ☀️ **Nudges**: after 3 hours of non-stop voice chat, the bot says *"6h 25m of daylight
  left, 22°C and clear. Pause the music, go touch some grass"*, with a button that plans
  the walk. It stays quiet after dark and during storms.

It's for groups of friends who hang out online and forget the outside exists. The screen
part is one message. The rest happens outside.

## Demo

<!-- TODO: add a short screen recording: /touchgrass → plan → 🙋 I'm in → /touched photo → streak -->

## Code

{% github aminul821/music-bot %}

The feature lives in three files:

- `MusicBot/core/llm.py`: a tiny client for a local Ollama server (text, images, JSON-schema output)
- `MusicBot/core/outdoors.py`: Open-Meteo forecast and sunset, OpenStreetMap (Overpass) green spots, and the weather-window scoring
- `MusicBot/plugins/grass.py`: the commands, streaks and nudges

## How I Built It

**Open-weight model:** [Gemma 3 4B](https://ollama.com/library/gemma3) served by
**[Ollama](https://ollama.com)** on the same box as the bot. One model handles both jobs:
writing plans (text) and checking `/touched` photos (vision). It runs on a laptop CPU.

**Open data, no API keys:** [Open-Meteo](https://open-meteo.com) for the hourly forecast
and sunrise/sunset, and [OpenStreetMap](https://www.openstreetmap.org) via the Overpass
API for parks, gardens, woods, beaches, peaks, viewpoints and hiking routes.

**Facts first, model second.** I didn't want an LLM inventing a park that doesn't exist,
so the pipeline is:

1. Code picks the best window: each daylight hour is scored on rain chance, storm codes,
   temperature comfort and wind, and the best 2 consecutive hours win.
2. Code gets real spots from OSM, removes duplicates and sorts them by distance.
3. The model gets only that JSON and is told to use only those places. It writes the
   friendly part: which spot, what to bring, a mini mission.
4. If Ollama is down, a plain template plan is posted instead. The feature never breaks.

**Photo checks use structured output.** Ollama's `format` field takes a JSON schema, so the
vision model must answer `{outdoors, screenshot, nature[], comment}`. The bot reads
booleans, not free text. A day only counts if `outdoors && !screenshot`, and forwarded
photos are rejected before the model sees them.

## Why Does Open Innovation Matter?

- **Photos stay at home.** People send pictures of where they are right now. Those
  pictures go to a model on our own server, not to a company's API. For a friends' group
  that's the difference between "fun" and "no thanks".
- **It costs nothing to run.** The bot already runs 24/7 on a small server. An open model
  on that box, plus key-free open weather and map data, means no per-request bill. A
  nudge every afternoon costs nothing.
- **Swap the model with one setting.** `GRASS_MODEL=gemma3:4b` on a laptop,
  `gemma3:12b` or `qwen2.5vl` on a bigger machine. Same code, no vendor lock-in, and no
  deprecation emails.
- **Open maps make it honest.** The plan can only use real places from OpenStreetMap, the
  same map the local hiking community edits.

<!-- TODO: where did the open approach beat a closed one for you? e.g. latency on the box, privacy reactions from the group -->

## Taking it outside

<!-- TODO (bonus points): the group actually used it. Which spot did /touchgrass pick? Who's leading /grassboard? Did the vision check catch anyone faking it? -->

## My Agent Session

<!-- Optional: save the session with DevRelay and embed it here with the agent_session tag. -->

## Prize Categories

<!-- List the partner categories you're entering, or remove this section. -->
