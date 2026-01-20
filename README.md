# claude-tgbot

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
