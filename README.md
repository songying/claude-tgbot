# claude-tgbot

Telegram bot for remote control server and Claude code.

## Prompt matching rules

See `docs/prompt_rules.md` for the configurable rule design and `config/prompt_rules.yaml` for the default configuration.

## Setup

See `docs/setup.md` for configuration and launch steps (Telegram Bot API token, polling/webhook settings).

## Security

See `docs/security.md` for whitelist/login policy, command restrictions, and audit logging.


Telegram bot utilities for remote control servers and Claude code.

## New utilities

- `TmuxManager` standardizes tmux window/pane sizing per session and captures pane output
  using `capture-pane -p -S` for precise range control.
- Telegram text formatting helpers normalize encoding and line wrapping to avoid truncation
  or garbled messages.
Telegram bot for remote control server and Claude code.

## Session registry

This repository includes a small registry for maintaining stable tag identifiers and
persisting tag name <-> tmux session mappings. The registry stores JSON data on disk
and can reconcile sessions at startup.

```python
from pathlib import Path

from claude_tgbot.session_registry import TagSessionRegistry

registry = TagSessionRegistry(Path("data/tag_sessions.json"))
registry.reconcile_sessions(create_missing=True)
record = registry.create_tag("10001", "daily-report")
print(record.tag_id, record.session_name)
```

Telegram bot for remote control server and Claude code.

## 配置与认证

* `config.example.json` 提供默认配置结构，启动时请传入实际配置路径。
* 支持 token/key 过期、轮换、IP 失败次数限制。
* 白名单用户支持 `user_id -> key` 独立映射。

```python
from claude_tgbot.main import startup

config_manager, auth = startup("config.json")
```

## 管理命令

管理员可以通过以下命令更新或撤销 key：

* `/update_key <user_id> <new_key> [expires_at]`
* `/revoke_key <user_id>`
* `/rotate_token <new_token>`
