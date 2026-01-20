# claude-tgbot

Telegram bot utilities for remote control servers and Claude code.

## New utilities

- `TmuxManager` standardizes tmux window/pane sizing per session and captures pane output
  using `capture-pane -p -S` for precise range control.
- Telegram text formatting helpers normalize encoding and line wrapping to avoid truncation
  or garbled messages.
