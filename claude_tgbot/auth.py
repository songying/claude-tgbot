from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from logging import Formatter, Logger, getLogger
from logging.handlers import RotatingFileHandler
from pathlib import Path
import time
from typing import Dict, List, Optional, Tuple

from claude_tgbot.config import AppConfig, KeyConfig, UserKeyConfig


@dataclass
class FailureRecord:
    attempts: List[float] = field(default_factory=list)
    locked_until: Optional[float] = None


class AuthManager:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.failures: Dict[str, FailureRecord] = {}
        self._logger = self._build_logger()

    def _build_logger(self) -> Logger:
        logger = getLogger("auth")
        if logger.handlers:
            return logger
        logger.setLevel("INFO")
        logger.propagate = False
        log_path = Path("logs/auth.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_path,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            Formatter(
                "%(asctime)s | user=%(user_id)s | ip=%(server_ip)s | status=%(status)s | "
                "reason=%(reason)s | token_fp=%(token_fp)s | token_len=%(token_len)s | "
                "failures=%(failure_count)s | locked_until=%(locked_until)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        logger.addHandler(handler)
        return logger

    def _token_fingerprint(self, token: str) -> str:
        if not token:
            return "empty"
        return hashlib.sha256(token.encode("utf-8")).hexdigest()[:12]

    def _failure_snapshot(self, ip: str, now: float) -> Tuple[int, Optional[float]]:
        record = self.failures.get(ip)
        if not record:
            return 0, None
        self._prune_failures(ip, now)
        return len(record.attempts), record.locked_until

    def _log_auth(
        self,
        *,
        user_id: Optional[str],
        server_ip: str,
        status: str,
        reason: str,
        token_fp: str,
        token_len: int,
        now: float,
    ) -> None:
        failure_count, locked_until = self._failure_snapshot(server_ip, now)
        self._logger.info(
            "auth",
            extra={
                "user_id": user_id or "unknown",
                "server_ip": server_ip,
                "status": status,
                "reason": reason,
                "token_fp": token_fp,
                "token_len": token_len,
                "failure_count": failure_count,
                "locked_until": locked_until,
            },
        )

    def _prune_failures(self, ip: str, now: float) -> None:
        record = self.failures.get(ip)
        if not record:
            return
        window_start = now - self.config.failure_window_seconds
        record.attempts = [ts for ts in record.attempts if ts >= window_start]
        if record.locked_until and record.locked_until <= now:
            record.locked_until = None

    def record_failure(self, ip: str, now: Optional[float] = None) -> FailureRecord:
        if now is None:
            now = time.time()
        record = self.failures.setdefault(ip, FailureRecord())
        record.attempts.append(now)
        self._prune_failures(ip, now)
        if len(record.attempts) >= self.config.max_failed_attempts:
            record.locked_until = now + self.config.lockout_seconds
        return record

    def is_ip_locked(self, ip: str, now: Optional[float] = None) -> bool:
        if now is None:
            now = time.time()
        record = self.failures.get(ip)
        if not record:
            return False
        self._prune_failures(ip, now)
        return bool(record.locked_until and record.locked_until > now)

    def validate_token(
        self,
        provided_token: str,
        user_id: Optional[str],
        server_ip: str,
        now: Optional[float] = None,
    ) -> bool:
        if now is None:
            now = time.time()
        token_fp = self._token_fingerprint(provided_token)
        token_len = len(provided_token)
        if self.is_ip_locked(server_ip, now):
            self._log_auth(
                user_id=user_id,
                server_ip=server_ip,
                status="denied",
                reason="ip_locked",
                token_fp=token_fp,
                token_len=token_len,
                now=now,
            )
            return False
        if user_id and user_id in self.config.whitelist_keys:
            user_key = self.config.whitelist_keys[user_id]
            if user_key.server_ip and user_key.server_ip != server_ip:
                self.record_failure(server_ip, now)
                self._log_auth(
                    user_id=user_id,
                    server_ip=server_ip,
                    status="denied",
                    reason="whitelist_ip_mismatch",
                    token_fp=token_fp,
                    token_len=token_len,
                    now=now,
                )
                return False
            if user_key.is_expired(now):
                self.record_failure(server_ip, now)
                self._log_auth(
                    user_id=user_id,
                    server_ip=server_ip,
                    status="denied",
                    reason="whitelist_key_expired",
                    token_fp=token_fp,
                    token_len=token_len,
                    now=now,
                )
                return False
            if provided_token == user_key.key:
                self._log_auth(
                    user_id=user_id,
                    server_ip=server_ip,
                    status="allowed",
                    reason="whitelist_key_match",
                    token_fp=token_fp,
                    token_len=token_len,
                    now=now,
                )
                return True
            self.record_failure(server_ip, now)
            self._log_auth(
                user_id=user_id,
                server_ip=server_ip,
                status="denied",
                reason="whitelist_key_mismatch",
                token_fp=token_fp,
                token_len=token_len,
                now=now,
            )
            return False
        if self._is_valid_token(provided_token, now):
            self._log_auth(
                user_id=user_id,
                server_ip=server_ip,
                status="allowed",
                reason="shared_key_match",
                token_fp=token_fp,
                token_len=token_len,
                now=now,
            )
            return True
        self.record_failure(server_ip, now)
        self._log_auth(
            user_id=user_id,
            server_ip=server_ip,
            status="denied",
            reason="shared_key_mismatch",
            token_fp=token_fp,
            token_len=token_len,
            now=now,
        )
        return False

    def _is_valid_token(self, provided_token: str, now: float) -> bool:
        for key in self.config.token_keys:
            if key.value == provided_token and not key.is_expired(now):
                return True
        return False

    def rotate_token(self, new_value: str, now: Optional[float] = None) -> Tuple[KeyConfig, List[KeyConfig]]:
        if now is None:
            now = time.time()
        expired_at = now + self.config.rotation_grace_seconds
        rotated_keys: List[KeyConfig] = []
        for key in self.config.token_keys:
            if key.expires_at is None or key.expires_at > expired_at:
                key.expires_at = expired_at
                rotated_keys.append(key)
        new_key = KeyConfig(value=new_value)
        self.config.token_keys.insert(0, new_key)
        return new_key, rotated_keys

    def revoke_user_key(self, user_id: str) -> bool:
        if user_id in self.config.whitelist_keys:
            del self.config.whitelist_keys[user_id]
            return True
        return False

    def update_user_key(self, user_id: str, key: str, expires_at: Optional[float] = None) -> None:
        self.config.whitelist_keys[user_id] = UserKeyConfig(key=key, expires_at=expires_at)
