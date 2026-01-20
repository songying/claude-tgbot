from __future__ import annotations

from pathlib import Path

from claude_tgbot.session_registry import TagSessionRegistry


class FakeTmux:
    def __init__(self) -> None:
        self.sessions = set()

    def list_sessions(self):
        return set(self.sessions)

    def has_session(self, name: str) -> bool:
        return name in self.sessions

    def new_session(self, name: str) -> None:
        self.sessions.add(name)

    def kill_session(self, name: str) -> None:
        self.sessions.discard(name)


def test_registry_reconcile_creates_missing(tmp_path: Path) -> None:
    tmux = FakeTmux()
    path = tmp_path / "registry.json"
    registry = TagSessionRegistry(path, tmux_client=tmux)
    record = registry.create_tag("100", "tab-1")
    tmux.sessions.discard(record.session_name)

    updated = registry.reconcile_sessions(create_missing=True)

    assert record.session_name in tmux.sessions
    assert updated
