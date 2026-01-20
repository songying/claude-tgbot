"""Command dispatch layer with structured logging."""

from __future__ import annotations

from dataclasses import dataclass
from logging import Formatter, Logger, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Callable, Optional


@dataclass(frozen=True)
class DispatchLoggerConfig:
    """Configuration for dispatch logging."""

    enabled: bool = True
    log_path: Path = Path("logs/dispatch.log")
    max_bytes: int = 5 * 1024 * 1024
    backup_count: int = 3
    truncate_length: int = 200


@dataclass(frozen=True)
class DispatchResult:
    """Result of a command execution."""

    status: str
    output: str


class CommandDispatcher:
    """Dispatches commands and logs results with rotation support."""

    def __init__(self, logger_config: DispatchLoggerConfig) -> None:
        self._logger_config = logger_config
        self._logger = self._build_logger(logger_config)

    def dispatch(
        self,
        *,
        user_id: str,
        tag_id: str,
        command: str,
        executor: Callable[[], DispatchResult],
    ) -> DispatchResult:
        """Execute a command via executor and log the dispatch result."""

        result = executor()
        self._log_dispatch(
            user_id=user_id,
            tag_id=tag_id,
            command=command,
            status=result.status,
            output=result.output,
        )
        return result

    def _build_logger(self, config: DispatchLoggerConfig) -> Logger:
        logger = getLogger("dispatch")
        if logger.handlers:
            return logger

        logger.setLevel("INFO")
        logger.propagate = False
        if not config.enabled:
            logger.disabled = True
            return logger

        log_path = config.log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            log_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        handler.setFormatter(
            Formatter(
                "%(asctime)s | user=%(user_id)s | tag=%(tag_id)s | command=%(command)s | "
                "status=%(status)s | output=%(output_summary)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        logger.addHandler(handler)
        return logger

    def _log_dispatch(
        self,
        *,
        user_id: str,
        tag_id: str,
        command: str,
        status: str,
        output: str,
    ) -> None:
        if not self._logger_config.enabled:
            return

        output_summary = self._truncate_output(output)
        extra = {
            "user_id": user_id,
            "tag_id": tag_id,
            "command": command,
            "status": status,
            "output_summary": output_summary,
        }
        self._logger.info("dispatch", extra=extra)

    def _truncate_output(self, output: str) -> str:
        if len(output) <= self._logger_config.truncate_length:
            return output
        return output[: self._logger_config.truncate_length] + "..."
