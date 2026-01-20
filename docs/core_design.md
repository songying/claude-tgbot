# Core Service Design

## 1) Telegram Bot Service Layer

### 1.1 Responsibilities
- Receive updates from Telegram (messages, callbacks, edits).
- Enforce authentication and route user actions to the right session/tab.
- Translate user inputs into tmux commands or internal state transitions.
- Render responses (screen output, menus, editor content) and handle rate limits.

### 1.2 Update Flow
1. **Ingress**: Telegram update arrives.
2. **Auth gate**: verify user against whitelist and login token/IP requirements.
3. **Session load**: load or create per-user session context.
4. **Dispatch**:
   - Text messages → command execution (unless in edit flow).
   - Slash commands → system actions (tabs, jobs, interval, mode, refresh).
   - Callback queries → button actions (parse prefix and route).
5. **Render + send**: send screen output or UI menus to user.

### 1.3 Routing Map (Example)
- `/start` → `ui.render_main_menu()`
- `/login <server_ip> <key>` → `auth.login()` and `ui.render_main_menu()`
- `/tabs` → `tabs.open_list()`
- `tab:select:<id>` → `tabs.activate(id)`
- `tab:new` → `tabs.create()`
- `/interval` or `interval:list` → `prefs.show_interval_menu()`
- `interval:set:<value>` → `prefs.set_interval(value)`
- `/refresh` or `refresh:now` → `screen.capture_and_send()`
- `/edit` or `edit:list` → `editor.list_files()`
- `edit:open:<path>` → `editor.open(path)`
- `/jobs` or `jobs:list` → `jobs.list()`
- `jobs:ctrlz` → `tmux.send_ctrlz()`
- `jobs:bg:<id>` → `tmux.send_bg(id)`
- `/claude` or `mode:claude` → `mode.set("claude")`
- `mode:shell` → `mode.set("normal")`

### 1.4 State Awareness
- **Active tab** required for command routing.
- **Edit flow** overrides default message handling.
- **Mode** influences output scheduling.
- **Interval** controls periodic capture in normal mode.

---

## 2) Tmux Management Layer

### 2.1 Responsibilities
- Create/reload/kill tmux sessions for tabs.
- List sessions and map tab IDs to tmux sessions.
- Execute commands in the active session/pane.
- Capture screen output for rendering.
- Support job control (ctrl-z, bg, fg).

### 2.2 Required Operations
- `create_session(tab_id)` → create tmux session `tgbot_<tab_id>`.
- `attach_session(tab_id)` → validate session exists; recreate if missing.
- `kill_session(tab_id)` → kill the session and cleanup.
- `list_sessions()` → list tmux sessions for reconciliation.
- `send_keys(tab_id, cmd)` → execute command.
- `capture_pane(tab_id, limit)` → capture visible screen (last screen).
- `send_ctrlz(tab_id)` / `send_bg(tab_id, job_id)` / `send_fg(tab_id, job_id)`.

### 2.3 Session ↔ Tab Mapping
- tmux session name: `tgbot_<tab_id>`.
- Each tab has one tmux session, one window, one pane.
- Use a consistent window size and environment for reliable output.

---

## 3) Persistence Layer

### 3.1 Responsibilities
- Persist user preferences (interval, mode).
- Persist tab registry: tab IDs, names, created_at, active tab.
- Persist auth configuration (whitelist, server keys, allowed IPs).
- Restore state on bot startup and reconcile with tmux.

### 3.2 Data Model (Logical)
- `users`:
  - `telegram_user_id`
  - `last_active_tab_id`
  - `interval`
  - `mode`
- `tabs`:
  - `tab_id`
  - `user_id`
  - `name`
  - `created_at`
  - `last_used_at`
- `auth_whitelist`:
  - `telegram_user_id`
  - `server_ip`
  - `access_key`

### 3.3 Storage Strategy
- Simple JSON/YAML for bootstrap; migrate to SQLite when needed.
- Maintain a single durable state file, written atomically.
- On startup, load state and reconcile with tmux sessions:
  - If session exists but not in state → mark as orphan.
  - If state exists but session missing → recreate or mark broken.

---

## 4) Cross-Cutting Concerns

### 4.1 Error Handling
- Enforce clear error messages for missing sessions, denied access, or IO failures.
- Provide user-friendly feedback for invalid commands or actions.

### 4.2 Rate Limits
- Apply message chunking and rate limiting for Telegram output.
- Avoid flooding from periodic refresh in large output tabs.

### 4.3 Audit Logging
- Log command execution (user, tab, command, timestamp).
- Retain logs for troubleshooting and security audit.
