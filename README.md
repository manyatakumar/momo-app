# momo 🐾 your pixel-cat content companion

A small black pixel cat sits in the corner of your screen. Dump a messy idea into it and Momo:

1. **files it into your funnel**: ToFU (memes, pop culture, work-life humor · 3×/week), MoFU (vulnerable stories, career
   lessons, identity · 3×/week) or BoFU (results, client wins, metrics · 1×/week)
2. **hypes you with your own receipts**, e.g. *"your AI-police irony post hit 25.8k impressions, so let's frame this one the same way!"*
3. **writes a ready-to-post LinkedIn draft in your voice** (lowercase, short punchy lines, → arrows), built on the
   best-fitting hook: Gaurav Sharma's 10 MoFU storytelling hooks, or the meme formats from your viral hits
4. **drops it into your weekly calendar**, then nags you about empty slots and stares at you during focus sessions

---

## ▶ How to start Momo

### Windows (easiest): the Momo app
1. Open this repo's **Releases** page (right side of the GitHub repo page) → latest release → click **`Momo.exe`**.
2. Double-click `Momo.exe` (move it to your Desktop first if you like).
   - "Windows protected your PC"? Click **More info → Run anyway**. You only need to do this once. It appears
     because Momo is a new app without a paid code-signing certificate.
3. The first launch takes about 5 seconds, then Momo appears in the bottom-right corner.
4. Right-click Momo → **🚀 Start Momo with Windows** to have it there every time you log in.

The app needs no Python or setup. Your data lives in `%APPDATA%\Momo` (right-click Momo → **📂 Open my Momo folder**).
Every push to `main` rebuilds and tests `Momo.exe` automatically (see the Actions tab).

### Running from source (Mac, or developers)
> Don't double-click `run.py`: on many computers `.py` files open in another app.

- **Mac:** double-click **`Start Momo (Mac).command`** (first time: right-click → Open → Open).
- **Windows:** double-click **`Start Momo (Windows).bat`**.

The first run sets itself up in about a minute; needs [Python 3.10+](https://www.python.org/downloads/).

---

## Using Momo

| Do this | What happens |
|---|---|
| **Click Momo** | Opens the drawer: pixel-cat header, funnel progress bars, Brain dump · Week · Insights · ⏱ |
| **Drag Momo** | Moves it; the spot is remembered |
| **Right-click Momo** | Menu: Brain dump, This week, Insights, Focus mode, Check my slots, LinkedIn setup, Snap to corner, Hide, Quit |
| **Brain dump** | Type a messy idea and press Enter. You get the hype line, the hook it picked and why, the funnel, the calendar slot, and a **ready-to-post draft** with a **Copy draft** button. Wrong funnel? Click ToFU/MoFU/BoFU and the draft is rewritten in that funnel's style. |
| **Week** | One post a day, 3 ToFU / 3 MoFU / 1 BoFU: Mon MoFU story · Tue ToFU short text · Wed BoFU carousel · Thu MoFU story · Fri ToFU meme · Sat MoFU text/video · Sun ToFU one-liner. Click a filled slot to copy its draft or mark it drafted/posted. Click an empty one to fill it from your backlog. |
| **Insights** | Your numbers, which post types beat your average, your hall of fame |
| **⏱ Focus mode** | Momo goes deadpan (— —) with a countdown: *"55 minutes left, stop looking at me and finish this draft!"* Hover over it and it scolds you. |
| **Pester mode** | Every 45 minutes (not 10pm–8am, never during focus): *"Meow meow! 🐾 You're missing a middle‑funnel post for Wednesday."* |

## Who writes the drafts: offline, Gemini, Claude, or any AI

| Option | Cost | How |
|---|---|---|
| **Offline** (default) | free | Momo picks the hook and writes the draft in your style, leaving `[fill: …]` spots for details only you know. |
| **Copy prompt → any AI** | free | Click **📋 Prompt** next to Send, or **Copy prompt for any AI** under a draft. Paste it into Gemini, ChatGPT or Claude.ai. The prompt includes your instructions, voice, hits and all 10 hooks. |
| **Gemini** | free tier for light use | Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → right-click Momo → **LinkedIn setup → Voice & AI** → paste it under Gemini → Save. Momo picks the newest Gemini Flash model your key can use. |
| **Claude** | pay-as-you-go (~1–2¢ a draft) | Key from [console.anthropic.com](https://console.anthropic.com) → same place, Claude field. |

The **AI** dropdown in Voice & AI chooses between them. **Auto** uses Gemini if its key is set, then Claude, then
offline. If an AI call fails (no internet, rate limit, bad key), Momo quietly writes an offline draft instead and
tells you why. A Gemini or Claude *chat* subscription is separate from API keys: the key is what Momo needs.

Every draft comes with the funnel, hook and format, two alternative first lines, a first-comment suggestion, and a
one-line reason tied to your data. Hooks rotate automatically: never the same one twice in a row, at most twice a week.
The hype numbers always come from your own data, never from the AI.

## Your data: `my_linkedin_data/`

This folder comes preloaded with your profile and viral hits. You can edit it in the app (**LinkedIn setup**) or directly:

| File | What it is |
|---|---|
| `about.md` | Headline + background |
| `posts.md` | Past posts separated by `---`, each with optional `label:`, `archetype:`, `impressions:`, `comments:`, `date:` lines |
| `viral_hooks.md` | One hook per line |
| `voice.md` | Your writing rules. Every draft follows these. |
| `momo_instructions.md` | Momo's operating instructions (funnels, hook library, hard rules). They're sent with every AI draft and copied prompt. |
| `baselines.md` | Account-wide stats (47 posts, avg 4,757, median 2,056…). Update them when your numbers change. |
| `*.csv` | Optional LinkedIn analytics export (**Import CSV…** in setup) |

Add new winners to `posts.md` as they happen, and Momo's hype gets sharper.

## 📱 Telegram (optional): text or voice-note ideas from your phone

1. In Telegram, message **@BotFather** → `/newbot` → copy the token.
2. Open `.env` in this folder (copy `.env.example` to `.env` if it doesn't exist). Set `TELEGRAM_BOT_TOKEN=...` and `MOMO_TELEGRAM_AUTOSTART=1`.
3. Restart Momo and send `/start` to your bot. It replies with your user id.
4. Put that id in `TELEGRAM_ALLOWED_USER_IDS=` in `.env` and restart Momo.

Now every idea you text gets the same hype, funnel and slot, and the bot replies with the full draft. On your
desktop Momo pops up *"📱 New idea from your phone"*. For voice notes, run
`.venv/bin/pip install -r requirements-voice.txt` (Windows: `.venv\Scripts\pip install -r requirements-voice.txt`).
Your computer needs to be on for the bot to work.

## Settings (`.env`)

| Variable | Default | |
|---|---|---|
| `MOMO_AI_PROVIDER` | `auto` | `auto`, `gemini`, `claude` or `offline` |
| `GEMINI_API_KEY` | (empty) | Turns on Gemini drafts |
| `GEMINI_MODEL` | (auto) | Force a specific Gemini model |
| `ANTHROPIC_API_KEY` | (empty) | Turns on Claude drafts |
| `MOMO_CLAUDE_MODEL` | `claude-opus-5-5` | Model used for drafts |
| `MOMO_SCALE` | `4` | Size of the cat (4 → about 130 px) |
| `MOMO_CAT_GLOW` | `1` | Faint outline so the black cat stays visible on dark wallpapers |
| `MOMO_PESTER_INTERVAL_MIN` | `45` | How often Momo checks for empty slots |
| `MOMO_QUIET_START` / `MOMO_QUIET_END` | `22` / `8` | No nagging between these hours |

---

## For developers

```
momo/
├── .github/workflows/build.yml   # builds + self-tests Momo.exe, publishes it to Releases
├── build_app.py                  # PyInstaller packaging
├── assets/momo.ico, momo.png     # app icon
├── Start Momo (Mac).command      # source launchers: create .venv, install, run
├── Start Momo (Windows).bat
├── run.py
├── requirements.txt / requirements-voice.txt / .env.example
├── my_linkedin_data/             # profile, viral hits, voice rules
├── momo/
│   ├── app.py                    # wiring: pet, bubble, drawer, tray, phone sync, bot autostart
│   ├── hooks.py                  # hook library (Gaurav's 10 MoFU + ToFU/BoFU formats) + offline writer
│   ├── writer.py                 # Claude draft writer with offline fallback
│   ├── content.py                # funnel + archetype classifier
│   ├── analyzer.py               # parses my_linkedin_data/
│   ├── hype.py                   # hype lines from real numbers
│   ├── scheduler.py · db.py · services.py · controllers.py · config.py
│   └── ui/                       # sprites (pixel Momo), pet window, bubble, drawer, pages, worker thread
├── telegram_bot/                 # bot.py + optional faster-whisper transcription
└── tests/test_core.py            # python -m pytest -q
```

Manual run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python run.py`.
