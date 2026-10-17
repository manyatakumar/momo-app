"""Launch Momo:  python run.py   (the packaged Momo.exe runs this same file)

  --telegram-bot   run the Telegram sync bot instead of the desktop pet
  --selftest       boot, write one draft, exit 0/1 (used by the build)
"""
import sys

if __name__ == "__main__":
    if "--telegram-bot" in sys.argv:
        from telegram_bot.bot import main as bot_main
        bot_main()
    else:
        from momo.app import main
        main(selftest="--selftest" in sys.argv)
