from pathlib import Path
import sys

def app_root():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent
