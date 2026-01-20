from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TelegramConfig:
    bot_token: str = ""
    use_webhook: bool = False
    webhook_url: Optional[str] = None
    listen_host: str = "0.0.0.0"
    listen_port: int = 8080


@dataclass
class TmuxConfig:
    width: int = 80
    height: int = 24
    capture_start: int = -2000


@dataclass
class PathsConfig:
    state_path: str = "data/state.json"
    tag_registry_path: str = "data/tag_sessions.json"
    prompt_rules_path: str = "config/prompt_rules.yaml"


@dataclass
class KeyConfig:
    value: str
    expires_at: Optional[float] = None

    def is_expired(self, now: float) -> bool:
        if self.expires_at is None:
            return False
        return now >= self.expires_at


@dataclass
class UserKeyConfig:
    key: str
    server_ip: Optional[str] = None
    expires_at: Optional[float] = None

    def is_expired(self, now: float) -> bool:
        if self.expires_at is None:
            return False
        return now >= self.expires_at


@dataclass
class AppConfig:
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    tmux: TmuxConfig = field(default_factory=TmuxConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)
    token_keys: List[KeyConfig] = field(default_factory=list)
    rotation_grace_seconds: int = 0
    max_failed_attempts: int = 5
    failure_window_seconds: int = 300
    lockout_seconds: int = 900
    whitelist_keys: Dict[str, UserKeyConfig] = field(default_factory=dict)
    admin_user_ids: List[int] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AppConfig":
        telegram = TelegramConfig(**payload.get("telegram", {}))
        tmux = TmuxConfig(**payload.get("tmux", {}))
        paths = PathsConfig(**payload.get("paths", {}))
        token_keys = [
            KeyConfig(value=item["value"], expires_at=item.get("expires_at"))
            for item in payload.get("token_keys", [])
        ]
        whitelist_keys: Dict[str, UserKeyConfig] = {}
        for user_id, entry in payload.get("whitelist_keys", {}).items():
            if isinstance(entry, dict):
                whitelist_keys[str(user_id)] = UserKeyConfig(
                    key=entry["key"],
                    server_ip=entry.get("server_ip"),
                    expires_at=entry.get("expires_at"),
                )
            else:
                whitelist_keys[str(user_id)] = UserKeyConfig(key=str(entry))
        return cls(
            telegram=telegram,
            tmux=tmux,
            paths=paths,
            token_keys=token_keys,
            rotation_grace_seconds=int(payload.get("rotation_grace_seconds", 0)),
            max_failed_attempts=int(payload.get("max_failed_attempts", 5)),
            failure_window_seconds=int(payload.get("failure_window_seconds", 300)),
            lockout_seconds=int(payload.get("lockout_seconds", 900)),
            whitelist_keys=whitelist_keys,
            admin_user_ids=[int(item) for item in payload.get("admin_user_ids", [])],
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "telegram": {
                "bot_token": self.telegram.bot_token,
                "use_webhook": self.telegram.use_webhook,
                "webhook_url": self.telegram.webhook_url,
                "listen_host": self.telegram.listen_host,
                "listen_port": self.telegram.listen_port,
            },
            "tmux": {
                "width": self.tmux.width,
                "height": self.tmux.height,
                "capture_start": self.tmux.capture_start,
            },
            "paths": {
                "state_path": self.paths.state_path,
                "tag_registry_path": self.paths.tag_registry_path,
                "prompt_rules_path": self.paths.prompt_rules_path,
            },
            "token_keys": [
                {"value": key.value, "expires_at": key.expires_at}
                for key in self.token_keys
            ],
            "rotation_grace_seconds": self.rotation_grace_seconds,
            "max_failed_attempts": self.max_failed_attempts,
            "failure_window_seconds": self.failure_window_seconds,
            "lockout_seconds": self.lockout_seconds,
            "whitelist_keys": {
                user_id: {
                    "key": entry.key,
                    "server_ip": entry.server_ip,
                    "expires_at": entry.expires_at,
                }
                for user_id, entry in self.whitelist_keys.items()
            },
            "admin_user_ids": self.admin_user_ids,
        }


class ConfigManager:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.config = AppConfig()

    def load(self) -> AppConfig:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.config = AppConfig.from_dict(payload)
        return self.config

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self.config.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
