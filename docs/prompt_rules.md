# 提示匹配与增量输出设计

本设计提供一组可配置的提示匹配规则（正则/关键词），当检测到提示时立即发送增量输出并生成按钮交互；未匹配时保持静默，直到手动刷新或发送新命令。

## 设计目标

- 支持正则与关键词两种匹配方式。
- 匹配后即时触发增量输出与按钮交互。
- 未匹配时保持静默，避免噪音。
- 提供用户级覆盖开关（禁用或强制增量输出）。

## 规则配置结构

参考 `config/prompt_rules.yaml` 中的配置格式：

- `rules.enabled`: 全局开关。
- `rules.default_silence`: 未匹配时是否静默（默认 true）。
- `rules.matchers`: 匹配器列表。
- `user_overrides.default_mode`: 用户默认模式（例如 auto）。
- `user_overrides.users`: 用户覆盖配置，支持 `enabled` 与 `force_incremental`。

### 匹配器字段

| 字段 | 说明 |
| --- | --- |
| `id` | 规则唯一标识 |
| `description` | 规则描述 |
| `type` | `regex` 或 `keyword` |
| `pattern` | 正则表达式（type=regex） |
| `keywords` | 关键词列表（type=keyword） |
| `case_sensitive` | 是否区分大小写 |
| `incremental_output` | 命中后是否发送增量输出 |
| `buttons` | 命中后按钮列表（label/action） |

## 行为流程

1. 检查全局开关与用户禁用。
2. 遍历匹配器，命中即返回结果（增量输出 + 按钮）。
3. 未命中时，如果 `default_silence` 为 true，返回 `None` 并保持静默。
4. 用户可通过 `force_incremental` 覆盖规则的增量输出配置。

## 代码接口

`claude_tgbot/prompt_rules.py` 提供 `PromptRuleEngine`：

```python
engine = PromptRuleEngine(config)
result = engine.evaluate(message, user_id="12345")
if result:
    # 发送增量输出
    # 生成 result.buttons 中的交互按钮
    pass
```

当 `result` 为 `None` 时表示无需推送，保持静默直到手动刷新或新命令触发。

按钮的 `action` 字段会被当作要发送到 tmux 的文本命令（可用于数字选择或确认短语）。
