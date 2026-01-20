from __future__ import annotations

from claude_tgbot.auth import AuthManager
from claude_tgbot.bot_service import BotService
from claude_tgbot.config import AppConfig, CommandPolicy
from claude_tgbot.dispatch import CommandDispatcher, DispatchLoggerConfig
from claude_tgbot.prompt_rules import PromptRuleEngine
from claude_tgbot.state_store import UserStateStore


class DummyConfigManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config


class StubRegistry:
    def list_records(self, user_id=None):  # type: ignore[no-untyped-def]
        return []

    def get_by_id(self, tag_id: str):  # type: ignore[no-untyped-def]
        return None


def _build_service(policy: CommandPolicy, tmp_path) -> BotService:
    config = AppConfig(command_policy=policy)
    auth = AuthManager(config)
    state_store = UserStateStore(path=tmp_path / "state.json")
    tag_registry = StubRegistry()
    prompt_engine = PromptRuleEngine({})
    dispatcher = CommandDispatcher(DispatchLoggerConfig(enabled=False))
    return BotService(
        config=config,
        auth=auth,
        state_store=state_store,
        tag_registry=tag_registry,
        prompt_engine=prompt_engine,
        dispatcher=dispatcher,
        config_manager=DummyConfigManager(config),
    )


def test_command_policy_blocks_pattern(tmp_path) -> None:
    policy = CommandPolicy(blocked_patterns=["rm -rf /"])
    service = _build_service(policy, tmp_path)
    assert service._validate_command("rm -rf /") == "命令被策略阻止。"


def test_command_policy_allowlist(tmp_path) -> None:
    policy = CommandPolicy(allowed_patterns=["^echo"], require_allowlist=True)
    service = _build_service(policy, tmp_path)
    assert service._validate_command("ls") == "命令不在允许列表中。"
    assert service._validate_command("echo ok") is None
