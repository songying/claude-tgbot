from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Optional


@dataclass
class EditSession:
    edit_id: str
    path: str
    tab_id: str
    started_at: float


@dataclass
class UserState:
    user_id: str
    active_tab_id: Optional[str] = None
    interval: str = "5m"
    mode: str = "normal"
    edit_session: Optional[EditSession] = None
    authorized: bool = False
    server_ip: Optional[str] = None
    chat_id: Optional[int] = None
    rename_tab_id: Optional[str] = None


class UserStateStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._states: Dict[str, UserState] = {}
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            self._states = {}
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        states: Dict[str, UserState] = {}
        for item in data.get("users", []):
            edit = item.get("edit_session")
            edit_session = None
            if edit:
                edit_session = EditSession(
                    edit_id=edit["edit_id"],
                    path=edit["path"],
                    tab_id=edit["tab_id"],
                    started_at=float(edit.get("started_at", time.time())),
                )
            state = UserState(
                user_id=str(item["user_id"]),
                active_tab_id=item.get("active_tab_id"),
                interval=item.get("interval", "5m"),
                mode=item.get("mode", "normal"),
                edit_session=edit_session,
                authorized=bool(item.get("authorized", False)),
                server_ip=item.get("server_ip"),
                chat_id=item.get("chat_id"),
                rename_tab_id=item.get("rename_tab_id"),
            )
            states[state.user_id] = state
        self._states = states

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "users": [self._serialize_state(state) for state in self._states.values()],
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get(self, user_id: str) -> UserState:
        if user_id not in self._states:
            self._states[user_id] = UserState(user_id=user_id)
        return self._states[user_id]

    def update(self, state: UserState) -> None:
        self._states[state.user_id] = state
        self.save()

    @staticmethod
    def _serialize_state(state: UserState) -> dict:
        payload = asdict(state)
        if state.edit_session is None:
            payload["edit_session"] = None
        return payload
