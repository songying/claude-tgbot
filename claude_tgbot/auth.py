from __future__ import annotations

from dataclasses import dataclass, field
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
        if self.is_ip_locked(server_ip, now):
            return False
        if user_id and user_id in self.config.whitelist_keys:
            user_key = self.config.whitelist_keys[user_id]
            if user_key.server_ip and user_key.server_ip != server_ip:
                self.record_failure(server_ip, now)
                return False
            if user_key.is_expired(now):
                self.record_failure(server_ip, now)
                return False
            if provided_token == user_key.key:
                return True
            self.record_failure(server_ip, now)
            return False
        if self._is_valid_token(provided_token, now):
            return True
        self.record_failure(server_ip, now)
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
