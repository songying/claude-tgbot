"""tmux management helpers for consistent session sizing and pane capture."""

from __future__ import annotations

from dataclasses import dataclass
from subprocess import CompletedProcess, run
from typing import Iterable, Sequence


@dataclass(frozen=True)
class TmuxSessionConfig:
    """Configuration for managing tmux sessions."""

    width: int = 80
    height: int = 24
    capture_start: int = -2000


class TmuxManager:
    """Wrapper around tmux commands for sizing and capturing panes."""

    def __init__(self, tmux_cmd: str = "tmux") -> None:
        self._tmux_cmd = tmux_cmd

    def set_uniform_size(
        self,
        session: str,
        width: int,
        height: int,
    ) -> None:
        """Resize all windows and panes in a session to a fixed size."""
        self._resize_windows(session, width, height)
        self._resize_panes(session, width, height)

    def capture_pane(
        self,
        target: str,
        start: int,
    ) -> str:
        """Capture pane output using `capture-pane -p -S` to control range."""
        result = self._run_tmux(
            ["capture-pane", "-p", "-S", str(start), "-t", target]
        )
        return result.stdout

    def list_sessions(self) -> Sequence[str]:
        """Return a list of session names."""
        result = self._run_tmux(["list-sessions", "-F", "#{session_name}"])
        return [line for line in result.stdout.splitlines() if line.strip()]

    def _resize_windows(self, session: str, width: int, height: int) -> None:
        for window_id in self._list_windows(session):
            self._run_tmux(
                ["resize-window", "-t", window_id, "-x", str(width), "-y", str(height)]
            )

    def _resize_panes(self, session: str, width: int, height: int) -> None:
        for pane_id in self._list_panes(session):
            self._run_tmux(
                ["resize-pane", "-t", pane_id, "-x", str(width), "-y", str(height)]
            )

    def _list_windows(self, session: str) -> Iterable[str]:
        result = self._run_tmux(["list-windows", "-t", session, "-F", "#{window_id}"])
        return [line for line in result.stdout.splitlines() if line.strip()]

    def _list_panes(self, session: str) -> Iterable[str]:
        result = self._run_tmux(["list-panes", "-t", session, "-F", "#{pane_id}"])
        return [line for line in result.stdout.splitlines() if line.strip()]

    def _run_tmux(self, args: Sequence[str]) -> CompletedProcess[str]:
        result = run(
            [self._tmux_cmd, *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return result
