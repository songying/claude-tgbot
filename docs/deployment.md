# 部署与运行

## 1) systemd 示例

创建 `/etc/systemd/system/claude-tgbot.service`：

```ini
[Unit]
Description=Claude Telegram Bot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/claude-tgbot
ExecStart=/usr/bin/python -m claude_tgbot.main /opt/claude-tgbot/config.json
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

启用并启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now claude-tgbot
sudo systemctl status claude-tgbot
```

## 2) 容器化示例

```Dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "-m", "claude_tgbot.main", "/app/config.json"]
```

示例运行：

```bash
docker build -t claude-tgbot .
docker run --rm -v $(pwd)/config.json:/app/config.json claude-tgbot
```

## 3) 日志监控

- 命令审计日志输出到 `logs/dispatch.log`，支持轮转。
- 建议在部署节点配置 logrotate 或集中式日志采集。

示例 logrotate 配置（/etc/logrotate.d/claude-tgbot）：

```
/opt/claude-tgbot/logs/dispatch.log {
    daily
    rotate 7
    compress
    missingok
    notifempty
}
```
