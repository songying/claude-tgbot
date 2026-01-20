# 测试方案

## 1) 集成测试（模拟 Telegram 交互、tmux 行为）

建议使用 pytest + mock：

- 模拟 `AuthManager` 与 `UserStateStore` 行为。
- 为 `TagSessionRegistry` 注入假的 tmux client（模拟 `list_sessions`, `has_session`, `new_session`, `kill_session`）。
- 使用 `BotService` 的命令校验逻辑，确保命令策略生效。

### 示例用例

1. **认证流程**
   - 正确 key + server_ip 通过。
   - 错误 key 或 server_ip 被拒绝并记录失败。

2. **命令策略**
   - 长度超过上限拒绝。
   - 命中 `blocked_patterns` 拒绝。
   - `require_allowlist=true` 时未命中 allowlist 拒绝。

3. **标签/会话恢复**
   - 记录存在但 tmux 会话丢失时，`reconcile_sessions` 重新创建。

4. **状态持久化**
   - `UserStateStore` 保存/重载后保留 active_tab、interval、mode。

## 2) 断线重连/重启恢复测试

- 启动 bot → 创建多个标签 → 终止进程 → 重新启动：
  - `TagSessionRegistry` 应恢复标签列表。
  - tmux session 仍存在时可继续使用。

## 3) 数据一致性测试

- 删除标签后不应留下孤儿 session。
- 重命名标签后应保持 `tag_id` 不变且映射更新。

## 4) 推荐命令（手工）

```bash
pytest -q
```
