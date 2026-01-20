from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable


@dataclass(frozen=True)
class ButtonAction:
    label: str
    action: str


@dataclass(frozen=True)
class MatchResult:
    rule_id: str
    incremental_output: bool
    buttons: tuple[ButtonAction, ...]


class PromptRuleEngine:
    def __init__(self, config: dict[str, Any]) -> None:
        self._config = config
        self._rules = config.get("rules", {})
        self._user_overrides = config.get("user_overrides", {})

    def evaluate(
        self, message: str, *, user_id: str | None = None
    ) -> MatchResult | None:
        if not self._rules.get("enabled", True):
            return None
        if self._is_user_disabled(user_id):
            return None

        for matcher in self._rules.get("matchers", []):
            if self._matches(matcher, message):
                incremental = self._resolve_incremental(matcher, user_id)
                buttons = self._build_buttons(matcher)
                return MatchResult(
                    rule_id=matcher.get("id", "unknown"),
                    incremental_output=incremental,
                    buttons=buttons,
                )

        if self._rules.get("default_silence", True):
            return None

        return MatchResult(rule_id="default", incremental_output=False, buttons=())

    def _is_user_disabled(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        user_config = self._user_overrides.get("users", {}).get(user_id, {})
        return user_config.get("enabled") is False

    def _resolve_incremental(self, matcher: dict[str, Any], user_id: str | None) -> bool:
        if user_id:
            user_config = self._user_overrides.get("users", {}).get(user_id, {})
            if user_config.get("force_incremental") is True:
                return True
            if user_config.get("force_incremental") is False:
                return False
        return bool(matcher.get("incremental_output", False))

    def _matches(self, matcher: dict[str, Any], message: str) -> bool:
        match_type = matcher.get("type", "keyword")
        if match_type == "regex":
            pattern = matcher.get("pattern", "")
            flags = 0
            if not matcher.get("case_sensitive", True):
                flags |= re.IGNORECASE
            return re.search(pattern, message, flags) is not None

        keywords = matcher.get("keywords", [])
        return self._keyword_match(keywords, message, matcher.get("case_sensitive", True))

    @staticmethod
    def _keyword_match(
        keywords: Iterable[str], message: str, case_sensitive: bool
    ) -> bool:
        haystack = message if case_sensitive else message.lower()
        for keyword in keywords:
            needle = keyword if case_sensitive else keyword.lower()
            if needle in haystack:
                return True
        return False

    @staticmethod
    def _build_buttons(matcher: dict[str, Any]) -> tuple[ButtonAction, ...]:
        buttons = []
        for item in matcher.get("buttons", []):
            buttons.append(ButtonAction(label=item["label"], action=item["action"]))
        return tuple(buttons)
