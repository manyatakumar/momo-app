"""Momo's pocket-sized sidekick: text or voice-note ideas from your phone, synced to the desktop database.

Run:  python -m telegram_bot.bot
(or set MOMO_TELEGRAM_AUTOSTART=1 in .env and the desktop app starts it for you)
"""
from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import sys
from datetime import date, datetime, timedelta

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from momo import config, db, scheduler, services

from . import transcribe

logging.basicConfig(format="%(asctime)s [momo-bot] %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)

ALLOWED_IDS = {int(x) for x in re.findall(r"-?\d+", os.environ.get("TELEGRAM_ALLOWED_USER_IDS", ""))}


def to_html(text: str) -> str:
    """Momo's **bold** markdown -> Telegram HTML."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html.escape(text))


async def _authorized(update: Update) -> bool:
    user = update.effective_user
    if user and user.id in ALLOWED_IDS:
        return True
    uid = user.id if user else "unknown"
    log.warning("Rejected message from user id %s", uid)
    if update.effective_message:
        await update.effective_message.reply_text(
            f"🐾 Hi! I only take ideas from my human.\n\nYour Telegram user id is {uid}. "
            f"If that's you, add TELEGRAM_ALLOWED_USER_IDS={uid} to Momo's .env and restart the bot.")
    return False


def _week_summary() -> str:
    start = scheduler.week_start(date.today())
    prog = scheduler.week_progress(start)
    lines = ["<b>This week's funnel</b>"]
    for f in config.FUNNELS:
        done, target = prog[f]
        lines.append(f"{'✅' if done >= target else '▫️'} {f}: {done}/{target}  <i>({config.FUNNEL_BLURB[f]})</i>")
    ideas = {(i.scheduled_date, i.funnel): i for i in db.ideas_in_range(start, start + timedelta(days=6))}
    lines.append("")
    for d, f in scheduler.week_slots(start):
        idea = ideas.get((d, f))
        mark = {"posted": "✓", "drafted": "✎", "idea": "💡"}[idea.status] if idea else "—"
        text = html.escape(idea.text[:50] + ("…" if len(idea.text) > 50 else "")) if idea else "<i>empty</i>"
        lines.append(f"<b>{d.strftime('%a')}</b> {f} {mark} {text}")
    return "\n".join(lines)


async def start(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    await update.effective_message.reply_text(
        "Mrrp! 🐾 Text me any idea (or send a voice note) and I'll file it into your LinkedIn funnel "
        "and sync it to Momo on your desktop.\n\n/week — this week's slots\n/backlog — unscheduled ideas")


async def week(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _authorized(update):
        await update.effective_message.reply_text(_week_summary(), parse_mode=ParseMode.HTML)


async def backlog(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    ideas = db.backlog()[:15]
    if not ideas:
        await update.effective_message.reply_text("Backlog is empty — every idea has a slot. 😽")
        return
    body = "\n".join(f"• <b>{i.funnel}</b> {html.escape(i.text[:80])}" for i in ideas)
    await update.effective_message.reply_text(f"<b>Backlog</b>\n{body}", parse_mode=ParseMode.HTML)


async def _ingest_and_reply(update: Update, text: str, prefix: str = "") -> None:
    result = await asyncio.to_thread(services.ingest_idea, text, "telegram")
    log.info("Synced idea #%s as %s (%s draft)", result.idea.id, result.draft.funnel, result.draft.engine)
    await update.effective_message.reply_text(prefix + to_html(result.message) + "\n\n<i>Synced to your desktop 🖥️</i>",
                                              parse_mode=ParseMode.HTML)
    # The draft goes in its own message so it's one long-press to copy.
    await update.effective_message.reply_text(result.draft.text)


async def on_text(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if await _authorized(update):
        await _ingest_and_reply(update, update.effective_message.text)


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _authorized(update):
        return
    msg = update.effective_message
    media = msg.voice or msg.audio
    config.VOICE_DIR.mkdir(parents=True, exist_ok=True)
    path = config.VOICE_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{media.file_unique_id}.ogg"
    tg_file = await ctx.bot.get_file(media.file_id)
    await tg_file.download_to_drive(path)

    if not transcribe.available():
        idea = await asyncio.to_thread(db.add_idea, f"🎙️ Voice note ({media.duration or '?'}s) — saved at "
                                       f"data/voice/{path.name}", "MoFU", "story", "telegram")
        await msg.reply_text("🎙️ Saved your voice note to the desktop backlog. Install faster-whisper "
                             "(pip install -r requirements-voice.txt) and I'll transcribe + categorize them too.")
        log.info("Saved untranscribed voice note as idea #%s", idea.id)
        return

    await msg.reply_text("🎧 Listening…")
    text = await asyncio.to_thread(transcribe.transcribe, path)
    if not text:
        await msg.reply_text("😿 Couldn't make that one out. The audio is saved — try again or type it?")
        return
    await _ingest_and_reply(update, text, prefix=f"🎙️ <i>“{html.escape(text)}”</i>\n\n")


def main() -> None:
    if not config.TELEGRAM_BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN is not set. Copy .env.example to .env and add your token from @BotFather.")
    if not ALLOWED_IDS:
        log.warning("TELEGRAM_ALLOWED_USER_IDS is empty — the bot will reply with your id and ignore ideas until set.")
    db.init()
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("week", week))
    app.add_handler(CommandHandler("backlog", backlog))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info("Momo bot is listening. Voice transcription: %s", "on" if transcribe.available() else "off")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
