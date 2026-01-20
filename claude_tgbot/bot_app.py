from __future__ import annotations

from pathlib import Path

import yaml

from claude_tgbot.auth import AuthManager
from claude_tgbot.bot_service import BotService
from claude_tgbot.config import ConfigManager
from claude_tgbot.dispatch import CommandDispatcher, DispatchLoggerConfig
from claude_tgbot.prompt_rules import PromptRuleEngine
from claude_tgbot.session_registry import TagSessionRegistry
from claude_tgbot.state_store import UserStateStore


def load_prompt_rules(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_bot(config_path: str | Path) -> None:
    config_manager = ConfigManager(config_path)
    config = config_manager.load()
    auth = AuthManager(config)

    state_store = UserStateStore(Path(config.paths.state_path))
    tag_registry = TagSessionRegistry(Path(config.paths.tag_registry_path))
    tag_registry.reconcile_sessions(create_missing=True)

    prompt_rules = load_prompt_rules(Path(config.paths.prompt_rules_path))
    prompt_engine = PromptRuleEngine(prompt_rules)

    dispatcher = CommandDispatcher(DispatchLoggerConfig())

    service = BotService(
        config=config,
        auth=auth,
        state_store=state_store,
        tag_registry=tag_registry,
        prompt_engine=prompt_engine,
        dispatcher=dispatcher,
        config_manager=config_manager,
    )

    application = service.build_application()

    if config.telegram.use_webhook:
        if not config.telegram.webhook_url:
            raise ValueError("use_webhook=true requires webhook_url")
        application.run_webhook(
            listen=config.telegram.listen_host,
            port=config.telegram.listen_port,
            url_path="",
            webhook_url=config.telegram.webhook_url,
        )
    else:
        application.run_polling()
