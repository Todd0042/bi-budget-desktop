# run.py

import sys
import argparse
from PySide6.QtWidgets import QApplication

import bi_budget_desktop.app_flags as app_flags
from bi_budget_desktop.main import launch_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Enable debug overlay")
    args = parser.parse_args()

    # Set global debug flag BEFORE launching anything
    app_flags.DEBUG_MODE = args.debug
    print(">>> DEBUG_MODE =", app_flags.DEBUG_MODE)

    launch_app()


if __name__ == "__main__":
    main()
