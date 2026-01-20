# 配置与启动

本项目基于 Telegram Bot API 工作，获取/管理 Bot Token 请参考官方文档：
- Bot API: https://core.telegram.org/bots/api
- 创建机器人与 Token: https://core.telegram.org/bots#botfather

## 1) 安装依赖

```bash
pip install -r requirements.txt
```

## 2) 配置文件

复制示例配置并填写：

```bash
cp config.example.json config.json
```

### 关键字段说明

- `telegram.bot_token`: 从 @BotFather 获取的 bot token。
- `telegram.use_webhook`: 是否使用 webhook。
- `telegram.webhook_url`: webhook 公网 URL（使用 webhook 时必填）。
- `telegram.listen_host` / `listen_port`: webhook 监听地址和端口。
- `tmux`: tmux 窗口大小与抓取范围。
- `paths.state_path`: 用户状态持久化路径。
- `paths.tag_registry_path`: 标签/会话映射持久化路径。
- `paths.prompt_rules_path`: CLAUDE CODE 提示匹配规则配置。
- `whitelist_keys`: 用户白名单，包含 `key` 与 `server_ip`。
- `command_policy`: 命令执行限制策略。

## 3) 启动 bot

### 轮询模式（默认）

```bash
python -m claude_tgbot.main config.json
```

### Webhook 模式

确保 `telegram.use_webhook=true` 且 `telegram.webhook_url` 配置正确：

```bash
python -m claude_tgbot.main config.json
```

## 4) 登录与使用

- 用户发送 `/login <服务器IP> <KEY>` 完成认证。
- 发送普通消息默认执行命令。
- 使用按钮或命令进行切换与管理：`/tabs` `/interval` `/refresh` `/edit` `/jobs` `/claude`。
