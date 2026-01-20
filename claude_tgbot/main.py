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
