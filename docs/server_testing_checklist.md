# 服务器测试部署清单（Ubuntu + Python 3.10.12 + Docker）

本文档用于在 Ubuntu 服务器上进行测试环境部署与验证，适配 Python 3.10.12 并使用 Docker 进行容器化运行。

## 0) 前置条件清单

- Ubuntu 服务器（建议 20.04/22.04）
- Python 3.10.12（宿主机与容器镜像均可）
- Docker（用于容器化运行）
- 已获取 Telegram Bot Token

## 1) 宿主机准备

### 1.1 安装依赖工具

```bash
sudo apt-get update
sudo apt-get install -y git curl
```

### 1.2 安装 Docker

使用 Docker 官方脚本安装：

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
```

重新登录或执行 `newgrp docker` 使权限生效。

### 1.3 安装 Python 3.10.12（可选）

如果宿主机需要运行脚本/测试，确认 Python 版本：

```bash
python3 --version
```

若不是 3.10.x，请自行安装 3.10.12 并确保 `python3` 指向该版本。

## 2) 获取代码与配置

### 2.1 拉取代码

```bash
git clone <YOUR_REPO_URL> claude-tgbot
cd claude-tgbot
```

### 2.2 生成配置文件

```bash
cp config.example.json config.json
```

至少填写以下字段：

- `telegram.bot_token`
- `whitelist_keys`
- `paths.state_path`
- `paths.tag_registry_path`
- `paths.prompt_rules_path`

## 3) Docker 镜像构建与启动（测试环境）

### 3.1 构建镜像

```bash
docker build -t claude-tgbot:testing .
```

### 3.2 运行容器（轮询模式）

```bash
docker run --rm \
  -v "$(pwd)/config.json:/app/config.json" \
  -v "$(pwd)/logs:/app/logs" \
  --name claude-tgbot-testing \
  claude-tgbot:testing
```

说明：

- `logs` 目录用于持久化 `dispatch.log`。
- 若使用 webhook，请在配置中开启并暴露端口。

### 3.3 运行容器（Webhook 模式示例）

确保 `config.json` 中已设置：

- `telegram.use_webhook=true`
- `telegram.webhook_url` 为公网可访问 URL
- `telegram.listen_host`/`listen_port` 设置正确

```bash
docker run --rm \
  -p 8080:8080 \
  -v "$(pwd)/config.json:/app/config.json" \
  -v "$(pwd)/logs:/app/logs" \
  --name claude-tgbot-testing \
  claude-tgbot:testing
```

> 将 `8080` 替换为 `config.json` 中的监听端口。

## 4) 测试运行检查清单

### 4.1 启动日志确认

```bash
docker logs -f claude-tgbot-testing
```

确认：

- 启动无异常报错。
- Telegram Bot 成功启动（轮询/ webhook）。

### 4.2 认证测试

- 使用 Telegram 向 bot 发送 `/login <服务器IP> <KEY>`。
- 验证认证成功与失败的反馈是否符合预期。

### 4.3 命令策略测试（示例）

在 Telegram 中发送命令，覆盖如下场景：

- 长度超限命令是否被拒绝。
- 命中 `blocked_patterns` 是否被拒绝。
- `require_allowlist=true` 时，非 allowlist 命令是否被拒绝。

### 4.4 标签与 tmux 会话测试

- 创建标签（tab），确认 tmux session 正常创建。
- 重启容器后，检查标签是否恢复。

### 4.5 日志检查

宿主机日志输出路径：

```bash
ls -l logs/dispatch.log
```

确认日志存在且持续写入。

## 5) 自动化测试（可选）

若要执行 pytest（在宿主机执行）：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## 6) 常见问题排查

### 6.1 无法启动容器

- 检查 Docker 是否已安装并可运行：`docker info`
- 检查镜像构建是否成功：`docker images`

### 6.2 Webhook 无回调

- 确认 `telegram.webhook_url` 能被公网访问。
- 检查防火墙端口是否放行（如 8080）。

### 6.3 命令不生效或无响应

- 确认已完成 `/login` 验证。
- 查看 `logs/dispatch.log` 是否有策略拒绝日志。
