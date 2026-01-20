from __future__ import annotations

from pathlib import Path
from typing import Tuple

from claude_tgbot.auth import AuthManager
from claude_tgbot.config import ConfigManager


def startup(config_path: str | Path) -> Tuple[ConfigManager, AuthManager]:
    manager = ConfigManager(config_path)
    config = manager.load()
    auth = AuthManager(config)
    return manager, auth


def run(config_path: str | Path) -> None:
    from claude_tgbot.bot_app import run_bot

    run_bot(config_path)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("Usage: python -m claude_tgbot.main <config.json>")
    run(sys.argv[1])
