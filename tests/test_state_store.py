from __future__ import annotations

from pathlib import Path

from claude_tgbot.state_store import UserStateStore


def test_state_store_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    store = UserStateStore(path)
    state = store.get("100")
    state.active_tab_id = "tab-1"
    state.interval = "1m"
    state.mode = "claude"
    store.update(state)

    loaded = UserStateStore(path)
    restored = loaded.get("100")
    assert restored.active_tab_id == "tab-1"
    assert restored.interval == "1m"
    assert restored.mode == "claude"
