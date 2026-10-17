#!/bin/bash
# Double-click me to start Momo. The first run sets everything up (about a minute).
cd "$(dirname "$0")" || exit 1

PY=""
for v in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$v" >/dev/null 2>&1 && "$v" -c 'import sys; sys.exit(sys.version_info < (3, 9))' 2>/dev/null; then
    PY="$(command -v "$v")"; break
  fi
done
if [ -z "$PY" ]; then
  osascript -e 'display alert "Momo needs Python 3.10 or newer" message "Install it from python.org (the big yellow Download button), then double-click Start Momo again."' >/dev/null 2>&1
  open "https://www.python.org/downloads/"
  exit 1
fi

MARKER=".venv/.momo-ready-2"
if [ ! -f "$MARKER" ]; then
  echo "🐾 First run: setting up Momo (about a minute)…"
  rm -rf .venv
  "$PY" -m venv .venv && \
  .venv/bin/python -m pip install --quiet --upgrade pip && \
  .venv/bin/python -m pip install --quiet -r requirements.txt && \
  touch "$MARKER" || { echo; echo "😿 Setup failed. Scroll up for the error, or send a screenshot."; read -r -p "Press Enter to close…"; exit 1; }
fi

nohup .venv/bin/python run.py >/dev/null 2>&1 &
echo "🐾 Momo is on your screen (bottom-right corner). You can close this window."
