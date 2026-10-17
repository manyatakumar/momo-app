"""Package Momo into a single double-clickable app with PyInstaller.

    pip install -r requirements.txt pyinstaller
    python build_app.py            ->  dist/Momo.exe (Windows) · dist/Momo.app (macOS) · dist/Momo (Linux)
"""
import os
import sys

import PyInstaller.__main__

sep = os.pathsep  # PyInstaller wants ";" on Windows, ":" elsewhere for --add-data
args = [
    "run.py",
    "--name=Momo",
    "--windowed",                      # no black console window
    "--noconfirm",
    "--clean",
    f"--add-data=my_linkedin_data{sep}my_linkedin_data",
    "--collect-submodules=telegram_bot",
    "--exclude-module=tkinter",
    "--exclude-module=pytest",
]
if sys.platform == "darwin":
    args += ["--icon=assets/momo.png", "--osx-bundle-identifier=com.momo.desktoppet"]
else:
    args += ["--onefile", "--icon=assets/momo.ico"]
PyInstaller.__main__.run(args)
