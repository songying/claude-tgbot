"""Thin tmux client helpers."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Iterable, Set


@dataclass(frozen=True)
class TmuxCommandResult:
    output: str


class TmuxClient:
    """Wrapper for tmux session management."""

    def list_sessions(self) -> Set[str]:
        result = self._run(["tmux", "list-sessions", "-F", "#S"], check=False)
        output = result.output.strip()
        if not output:
            return set()
        return {line.strip() for line in output.splitlines() if line.strip()}

    def has_session(self, session_name: str) -> bool:
        completed = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            check=False,
            capture_output=True,
            text=True,
        )
        return completed.returncode == 0

    def new_session(self, session_name: str) -> None:
        self._run(["tmux", "new-session", "-d", "-s", session_name])

    def kill_session(self, session_name: str) -> None:
        self._run(["tmux", "kill-session", "-t", session_name])

    def _run(self, command: Iterable[str], check: bool = True) -> TmuxCommandResult:
        completed = subprocess.run(
            list(command),
            check=check,
            capture_output=True,
            text=True,
        )
        return TmuxCommandResult(output=completed.stdout)
