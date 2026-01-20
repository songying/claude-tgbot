# 安全与权限

## 1) 白名单与认证流程

- 白名单配置在 `config.json` 的 `whitelist_keys` 中，键为 Telegram 用户 ID。
- 每个用户可配置 `key` 与 `server_ip`，登录时需使用 `/login <服务器IP> <KEY>`。
- `AuthManager` 会校验：
  - 用户 ID 是否在白名单。
  - `server_ip` 是否匹配（若配置）。
  - key 是否过期。
- 失败尝试会按 `lockout_seconds` 进行锁定（基于 server IP 记录）。

## 2) 并发隔离

- 每个用户使用独立的 asyncio 锁进行串行化命令发送。
- 避免同一用户同时触发多条命令导致 tmux 会话错乱。

## 3) 命令执行限制

通过 `command_policy` 配置命令限制：

```json
"command_policy": {
  "max_length": 4096,
  "blocked_patterns": ["rm -rf /", ":\\s*\\(\\)\\s*\\{"],
  "allowed_patterns": [],
  "require_allowlist": false
}
```

- `max_length`：限制单条命令长度。
- `blocked_patterns`：正则列表，命中即拒绝执行。
- `allowed_patterns` + `require_allowlist`：启用允许名单，仅匹配允许规则的命令可执行。

## 4) 审计日志

- 所有命令执行经 `CommandDispatcher` 记录到 `logs/dispatch.log`。
- 日志包含用户、标签、命令与状态摘要，支持轮转。
