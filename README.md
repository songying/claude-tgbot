# claude-tgbot
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
record = registry.create_tag("daily-report")
print(record.tag_id, record.session_name)
```
