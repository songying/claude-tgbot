from __future__ import annotations

import shlex
from typing import Optional, Tuple

from claude_tgbot.auth import AuthManager
from claude_tgbot.config import ConfigManager


class AdminCommandError(ValueError):
    pass


def _parse_command(command: str) -> Tuple[str, list[str]]:
    parts = shlex.split(command)
    if not parts:
        raise AdminCommandError("命令不能为空")
    return parts[0], parts[1:]


def handle_admin_command(
    command: str,
    auth: AuthManager,
    config_manager: ConfigManager,
    now: Optional[float] = None,
) -> str:
    name, args = _parse_command(command)
    if name == "/revoke_key":
        if len(args) != 1:
            raise AdminCommandError("用法: /revoke_key <user_id>")
        user_id = args[0]
        if auth.revoke_user_key(user_id):
            config_manager.save()
            return f"已撤销用户 {user_id} 的 key"
        return f"用户 {user_id} 未配置 key"
    if name == "/update_key":
        if len(args) < 2:
            raise AdminCommandError("用法: /update_key <user_id> <new_key> [expires_at]")
        user_id = args[0]
        new_key = args[1]
        expires_at = float(args[2]) if len(args) > 2 else None
        auth.update_user_key(user_id, new_key, expires_at=expires_at)
        config_manager.save()
        return f"已更新用户 {user_id} 的 key"
    if name == "/rotate_token":
        if len(args) < 1:
            raise AdminCommandError("用法: /rotate_token <new_token>")
        new_token = args[0]
        auth.rotate_token(new_token, now=now)
        config_manager.save()
        return "已轮换 token"
    raise AdminCommandError(f"未知命令: {name}")
