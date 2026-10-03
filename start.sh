#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
pip install -U -r requirements.txt
python -m MusicBot
