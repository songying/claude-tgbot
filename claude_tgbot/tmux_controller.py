from __future__ import annotations

from dataclasses import dataclass
from subprocess import CompletedProcess, run
from typing import List

from claude_tgbot.tmux_manager import TmuxManager, TmuxSessionConfig


@dataclass(frozen=True)
class TmuxJob:
    job_id: str
    command: str


class TmuxController:
    def __init__(
        self,
        tmux_cmd: str = "tmux",
        session_config: TmuxSessionConfig | None = None,
    ) -> None:
        self._tmux_cmd = tmux_cmd
        self._session_config = session_config or TmuxSessionConfig()
        self._manager = TmuxManager(tmux_cmd=tmux_cmd)

    def ensure_session(self, session_name: str) -> None:
        if self.has_session(session_name):
            self._manager.set_uniform_size(
                session_name,
                width=self._session_config.width,
                height=self._session_config.height,
            )
            return
        self._run(["new-session", "-d", "-s", session_name])
        self._manager.set_uniform_size(
            session_name,
            width=self._session_config.width,
            height=self._session_config.height,
        )

    def has_session(self, session_name: str) -> bool:
        result = run(
            [self._tmux_cmd, "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def kill_session(self, session_name: str) -> None:
        self._run(["kill-session", "-t", session_name])

    def send_command(self, session_name: str, command: str) -> None:
        self._run(["send-keys", "-t", session_name, command, "Enter"])

    def send_ctrlz(self, session_name: str) -> None:
        self._run(["send-keys", "-t", session_name, "C-z"])

    def send_bg(self, session_name: str, job_id: str) -> None:
        self.send_command(session_name, f"bg %{job_id}")

    def send_fg(self, session_name: str, job_id: str) -> None:
        self.send_command(session_name, f"fg %{job_id}")

    def capture(self, session_name: str) -> str:
        return self._manager.capture_pane(
            session_name,
            start=self._session_config.capture_start,
        )

    def list_jobs(self, session_name: str) -> List[TmuxJob]:
        self.send_command(session_name, "jobs -l")
        output = self.capture(session_name)
        return self._parse_jobs(output)

    def get_cwd(self, session_name: str) -> str:
        result = self._run(
            [
                "display-message",
                "-p",
                "-t",
                session_name,
                "#{pane_current_path}",
            ]
        )
        return result.stdout.strip()

    @staticmethod
    def _parse_jobs(output: str) -> List[TmuxJob]:
        jobs: List[TmuxJob] = []
        for line in output.splitlines():
            if not line.strip().startswith("["):
                continue
            parts = line.strip().split(" ", 2)
            if not parts:
                continue
            job_id = parts[0].strip("[]")
            command = parts[-1] if len(parts) > 1 else ""
            if job_id.isdigit():
                jobs.append(TmuxJob(job_id=job_id, command=command))
        return jobs

    def _run(self, args: List[str]) -> CompletedProcess[str]:
        return run(
            [self._tmux_cmd, *args],
            capture_output=True,
            text=True,
            check=True,
        )
