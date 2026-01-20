# Requirements & Protocol Definition

## 1) Bot Command/Message Protocol

### 1.1 Message Types
- **Default text message**: treated as a shell command sent to the active tab (tmux pane).
- **Slash commands** (bot control):
  - `/start` — begin a session and show the main control panel.
  - `/help` — show usage and button legend.
  - `/login <server_ip> <key>` — authenticate and unlock the bot.
  - `/tabs` — list and select tabs (aliases to the Tabs button).
  - `/jobs` — list jobs (aliases to the Jobs button).
  - `/claude` — toggle CLAUDE CODE mode for the active tab.
  - `/interval` — show interval selector (aliases to the Interval button).
  - `/refresh` — immediate screen refresh (aliases to the Refresh button).
  - `/edit` — start file selection/editor flow (aliases to the Edit button).
  - `/cancel` — cancel the current edit/rename flow.

### 1.2 Callback Data (Buttons)
Callback data prefixes should be short and parseable:
- `tab:list` — open tab list menu.
- `tab:select:<tab_id>` — select existing tab.
- `tab:new` — create a new tab.
- `tab:rename:<tab_id>` — rename a tab.
- `tab:close:<tab_id>` — close and destroy a tab.
- `interval:list` — open interval selector.
- `interval:set:<value>` — set interval (values: `1m`, `5m`, `1h`, `never`).
- `refresh:now` — immediate screen refresh.
- `edit:list` — open file list in current directory.
- `edit:open:<rel_path>` — open file for editing.
- `edit:save:<edit_id>` — save edited content.
- `jobs:list` — open jobs list.
- `jobs:bg:<job_id>` — background job (e.g., `bg %1`).
- `jobs:ctrlz` — send CTRL-Z.
- `mode:claude` — toggle CLAUDE CODE mode.
- `mode:shell` — toggle normal mode.

### 1.3 Input Parsing Rules
- **Default**: plain text = command execution in active tab.
- **Edit mode**: user replies with new content for the active edit session; sending content saves.
- **CLAUDE CODE**: text input is forwarded, but the output handling differs (see §3.2).
- **Escape hatch**: allow `/cancel` to abort editing or long-running flows.

---

## 2) Button Structure (Top-Level UI)

### 2.1 Main Panel Buttons
- **Tabs**: opens list of existing tabs, plus "New Tab".
- **Interval**: opens interval selector (1m, 5m, 1h, never). Current selection highlighted.
- **Refresh**: immediate screen refresh of the active tab.
- **Edit**: browse files in current directory, open editor.
- **Jobs**: shows jobs list. First button below Jobs is CTRL-Z.
- **Mode**: toggle Normal / CLAUDE CODE.

### 2.2 Tabs Menu
- Existing tabs listed with active tab highlighted.
- Buttons: `New Tab`, `Rename`, `Close` for each tab.

### 2.3 Interval Menu
- Options: 1min, 5min, 1hr, never.
- Default: 5min.
- Persist per user.

### 2.4 Jobs Menu
- First entry: `CTRL-Z`.
- List of jobs: label = `#<id> <name_prefix>` (first 6 characters).

### 2.5 Editor Menu
- Show only files in current directory.
- Provide pagination if necessary.
- On open, bot sends file content with edit instructions.

---

## 3) State Machine

### 3.1 Shared Session State (per user)
- `active_tab_id`
- `mode`: `normal` | `claude`
- `interval`: `1m` | `5m` | `1h` | `never`
- `edit_session`: `{edit_id, path, started_at, state}` or `null`
- `authorized`: `true`/`false`
- `server_ip`: last authenticated server IP

### 3.2 Mode Behavior

#### Normal Mode
- Timer-driven output: every interval, send last screen contents.
- Refresh button sends last screen immediately.

#### CLAUDE CODE Mode
- **No periodic refresh**.
- After each command, bot waits.
- Output is only sent on:
  - Manual refresh.
  - Detected prompt requiring confirmation/selection.
- On confirmation/selection prompts, output newly added text since last flush.

### 3.3 Edit Flow
- Enter edit: `edit:open:<path>` creates edit session.
- User sends new content → save → close edit session.
- `/cancel` or `edit:save` with no content cancels.

---

## 4) Auth & Permission Model

### 4.1 Configured Whitelist
- Server holds whitelist entries with fields:
  - `telegram_user_id`
  - `server_ip`
  - `access_key`

### 4.2 Login Flow
- User must provide: server IP + key.
- Bot validates user id + IP + key against config.
- On failure: deny and do not expose menus.

### 4.3 Permissions
- Bot operates with OS user permissions of the running process.
- No privilege escalation.

---

## 5) Tabs & Tmux Lifecycle

### 5.1 Mapping Strategy
- Each tab has a stable `tab_id` (UUID).
- Tmux session name = `tgbot_<tab_id>`.
- A tab corresponds to a tmux session with one window/pane.

### 5.2 Lifecycle
- **Create**: allocate tab_id → create tmux session → mark active.
- **Reload**: on bot restart, load persisted tab list and attach to existing tmux sessions (or recreate if missing).
- **Destroy**: close tab → kill tmux session → remove from registry.

### 5.3 Persistence
- Store state on disk:
  - tab list (id, name, created_at)
  - active tab
  - per-user preferences (interval, mode)
- On startup, reconcile registry with actual tmux sessions.

---

## 6) Output Handling

- Use `tmux capture-pane` to get screen text for sending.
- Enforce message size constraints and split into chunks if needed.
- Normalize line endings and strip unsupported characters.

---

## 7) Error Handling & Recovery

- If tmux session missing: mark tab as broken and offer recreate.
- If edit save fails: keep edit session open and return error.
- If access denied: no menus exposed; prompt for credentials.
