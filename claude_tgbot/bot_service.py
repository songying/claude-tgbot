from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (Application, ApplicationBuilder, CallbackQueryHandler,
                          CommandHandler, ContextTypes, MessageHandler, filters)

from claude_tgbot.admin import AdminCommandError, handle_admin_command
from claude_tgbot.auth import AuthManager
from claude_tgbot.config import AppConfig
from claude_tgbot.dispatch import CommandDispatcher, DispatchResult
from claude_tgbot.prompt_rules import MatchResult, PromptRuleEngine
from claude_tgbot.session_registry import TagRecord, TagSessionRegistry
from claude_tgbot.state_store import EditSession, UserState, UserStateStore
from claude_tgbot.telegram_format import split_for_telegram
from claude_tgbot.tmux_controller import TmuxController, TmuxJob
from claude_tgbot.tmux_manager import TmuxSessionConfig


@dataclass(frozen=True)
class IntervalOption:
    label: str
    value: str
    seconds: Optional[int]


INTERVAL_OPTIONS: List[IntervalOption] = [
    IntervalOption(label="1min", value="1m", seconds=60),
    IntervalOption(label="5min", value="5m", seconds=300),
    IntervalOption(label="1hr", value="1h", seconds=3600),
    IntervalOption(label="never", value="never", seconds=None),
]


class BotService:
    def __init__(
        self,
        config: AppConfig,
        auth: AuthManager,
        state_store: UserStateStore,
        tag_registry: TagSessionRegistry,
        prompt_engine: PromptRuleEngine,
        dispatcher: CommandDispatcher,
        config_manager,
    ) -> None:
        self._config = config
        self._auth = auth
        self._state_store = state_store
        self._tag_registry = tag_registry
        self._prompt_engine = prompt_engine
        self._dispatcher = dispatcher
        self._config_manager = config_manager
        self._tmux = TmuxController(
            session_config=TmuxSessionConfig(
                width=config.tmux.width,
                height=config.tmux.height,
                capture_start=config.tmux.capture_start,
            )
        )
        self._last_capture: Dict[str, str] = {}
        self._user_locks: Dict[str, asyncio.Lock] = {}

    def build_application(self) -> Application:
        application = ApplicationBuilder().token(self._config.telegram.bot_token).build()

        application.add_handler(CommandHandler("start", self._start))
        application.add_handler(CommandHandler("help", self._help))
        application.add_handler(CommandHandler("login", self._login))
        application.add_handler(CommandHandler("tabs", self._tabs))
        application.add_handler(CommandHandler("interval", self._interval))
        application.add_handler(CommandHandler("refresh", self._refresh))
        application.add_handler(CommandHandler("edit", self._edit))
        application.add_handler(CommandHandler("jobs", self._jobs))
        application.add_handler(CommandHandler("claude", self._toggle_claude))
        application.add_handler(CommandHandler("cancel", self._cancel))
        application.add_handler(CallbackQueryHandler(self._callbacks))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._text))

        return application

    async def _start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        state.chat_id = update.effective_chat.id if update.effective_chat else None
        self._state_store.update(state)
        if not state.authorized:
            await update.message.reply_text(
                "请输入 /login <服务器IP> <KEY> 以登录。"
            )
            return
        await self._render_main_menu(update, context, state)

    async def _help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        lines = [
            "默认发送文本即执行命令。",
            "常用命令:",
            "/tabs, /interval, /refresh, /edit, /jobs, /claude",
            "登录: /login <服务器IP> <KEY>",
        ]
        await update.message.reply_text("\n".join(lines))

    async def _login(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("用法: /login <服务器IP> <KEY>")
            return
        server_ip, provided_key = args[0], args[1]
        user_id = str(update.effective_user.id) if update.effective_user else ""
        if not self._auth.validate_token(provided_key, user_id, server_ip):
            await update.message.reply_text("认证失败，无法登录。")
            return
        state = self._state_for(update)
        state.authorized = True
        state.server_ip = server_ip
        state.chat_id = update.effective_chat.id if update.effective_chat else None
        self._state_store.update(state)
        await update.message.reply_text("登录成功。")
        await self._render_main_menu(update, context, state)
        self._ensure_interval_job(context, state)

    async def _tabs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        await self._send_tab_menu(update, state)

    async def _interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        await self._send_interval_menu(update, state)

    async def _refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        await self._send_capture(update, state, force=True)

    async def _edit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        await self._send_edit_menu(update, state)

    async def _jobs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        await self._send_jobs_menu(update, state)

    async def _toggle_claude(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        state.mode = "claude" if state.mode == "normal" else "normal"
        self._state_store.update(state)
        await update.message.reply_text(f"当前模式: {state.mode}")
        self._ensure_interval_job(context, state)

    async def _cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        state.edit_session = None
        state.rename_tab_id = None
        self._state_store.update(state)
        await update.message.reply_text("已取消当前操作。")

    async def _callbacks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if not query:
            return
        await query.answer()
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        data = query.data or ""
        if data == "tab:list":
            await self._send_tab_menu(update, state, edit_message=query.message)
            return
        if data.startswith("tab:select:"):
            tab_id = data.split(":", 2)[2]
            await self._activate_tab(update, state, tab_id)
            return
        if data.startswith("tab:rename:"):
            tab_id = data.split(":", 2)[2]
            await self._prompt_rename(update, state, tab_id)
            return
        if data.startswith("tab:close:"):
            tab_id = data.split(":", 2)[2]
            await self._close_tab(update, state, tab_id)
            return
        if data == "tab:new":
            await self._create_tab(update, state)
            return
        if data.startswith("interval:set:"):
            value = data.split(":", 2)[2]
            await self._set_interval(update, context, state, value)
            return
        if data == "interval:list":
            await self._send_interval_menu(update, state, edit_message=query.message)
            return
        if data == "refresh:now":
            await self._send_capture(update, state, force=True)
            return
        if data == "edit:list":
            await self._send_edit_menu(update, state, edit_message=query.message)
            return
        if data.startswith("edit:open:"):
            rel_path = data.split(":", 2)[2]
            await self._open_editor(update, state, rel_path)
            return
        if data.startswith("edit:save:"):
            await self._save_editor(update, state)
            return
        if data == "jobs:list":
            await self._send_jobs_menu(update, state, edit_message=query.message)
            return
        if data == "jobs:ctrlz":
            await self._ctrlz_job(update, state)
            return
        if data.startswith("jobs:bg:"):
            job_id = data.split(":", 2)[2]
            await self._bg_job(update, state, job_id)
            return
        if data == "mode:claude":
            state.mode = "claude"
            self._state_store.update(state)
            await self._render_main_menu(update, context, state)
            self._ensure_interval_job(context, state)
            return
        if data == "mode:shell":
            state.mode = "normal"
            self._state_store.update(state)
            await self._render_main_menu(update, context, state)
            self._ensure_interval_job(context, state)
            return
        if data.startswith("prompt:"):
            action = data.split(":", 1)[1]
            record = self._active_record(state)
            if not record:
                await self._send_text(update, "当前标签无效，请重新选择。")
                return
            policy_error = self._validate_command(action)
            if policy_error:
                await self._send_text(update, policy_error)
                return
            self._tmux.send_command(record.session_name, action)
            await self._send_text(update, f"已发送: {action}")
            if state.mode == "claude":
                await self._send_capture(update, state, force=False)
            return

    async def _text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message is None:
            return
        state = self._state_for(update)
        if not self._ensure_auth(update, state):
            return
        if state.edit_session:
            await self._handle_edit_content(update, state)
            return
        if state.rename_tab_id:
            await self._handle_rename(update, state)
            return
        text = update.message.text or ""
        if self._maybe_handle_admin(update, text):
            return
        if not state.active_tab_id:
            await update.message.reply_text("请先创建或选择一个标签。")
            return
        record = self._tag_registry.get_by_id(state.active_tab_id)
        if not record:
            await update.message.reply_text("当前标签无效，请重新选择。")
            return
        await self._execute_command(update, state, record, text)

    def _maybe_handle_admin(self, update: Update, text: str) -> bool:
        if not update.effective_user:
            return False
        if update.effective_user.id not in self._config.admin_user_ids:
            return False
        if not text.startswith("/"):
            return False
        if update.message is None:
            return False
        try:
            response = handle_admin_command(text, self._auth, self._config_manager)
        except AdminCommandError:
            return False
        except ValueError as exc:
            asyncio.create_task(update.message.reply_text(str(exc)))
            return True
        asyncio.create_task(update.message.reply_text(response))
        return True

    async def _execute_command(
        self,
        update: Update,
        state: UserState,
        record: TagRecord,
        command: str,
    ) -> None:
        policy_error = self._validate_command(command)
        if policy_error:
            await self._send_text(update, policy_error)
            return
        lock = self._user_locks.setdefault(state.user_id, asyncio.Lock())
        async with lock:
            def executor() -> DispatchResult:
                self._tmux.ensure_session(record.session_name)
                self._tmux.send_command(record.session_name, command)
                return DispatchResult(status="sent", output="")

            self._dispatcher.dispatch(
                user_id=state.user_id,
                tag_id=record.tag_id,
                command=command,
                executor=executor,
            )

            if state.mode == "claude":
                await self._send_capture(update, state, force=False)

    async def _send_capture(
        self,
        update: Update,
        state: UserState,
        force: bool,
    ) -> None:
        record = self._active_record(state)
        if not record:
            await update.message.reply_text("当前标签无效，请重新选择。")
            return
        self._tmux.ensure_session(record.session_name)
        capture = self._tmux.capture(record.session_name)
        previous = self._last_capture.get(record.tag_id, "")
        incremental = self._incremental(previous, capture)
        if state.mode == "claude" and not force:
            match = self._prompt_engine.evaluate(incremental, user_id=state.user_id)
            if not match:
                return
            await self._send_prompt_match(update, incremental, match)
        else:
            await self._send_text(update, capture)
        self._last_capture[record.tag_id] = capture

    async def _send_prompt_match(
        self,
        update: Update,
        incremental: str,
        match: MatchResult,
    ) -> None:
        if incremental:
            await self._send_text(update, incremental)
        if match.buttons:
            await self._send_prompt_buttons(update, match)

    async def _send_prompt_buttons(self, update: Update, match: MatchResult) -> None:
        keyboard = [
            [InlineKeyboardButton(item.label, callback_data=f"prompt:{item.action}")]
            for item in match.buttons
        ]
        message = update.effective_message
        if message:
            await message.reply_text(
                "检测到需要确认/选择的输出:",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )

    async def _send_tab_menu(
        self,
        update: Update,
        state: UserState,
        edit_message=None,
    ) -> None:
        records = list(self._tag_registry.list_records(user_id=state.user_id))
        keyboard: List[List[InlineKeyboardButton]] = []
        for record in records:
            prefix = "✅ " if record.tag_id == state.active_tab_id else ""
            keyboard.append(
                [
                    InlineKeyboardButton(prefix + record.tag_name, callback_data=f"tab:select:{record.tag_id}"),
                    InlineKeyboardButton("✏️", callback_data=f"tab:rename:{record.tag_id}"),
                    InlineKeyboardButton("🗑️", callback_data=f"tab:close:{record.tag_id}"),
                ]
            )
        keyboard.append([InlineKeyboardButton("➕ 新建标签", callback_data="tab:new")])
        markup = InlineKeyboardMarkup(keyboard)
        await self._send_or_edit(update, edit_message, "请选择标签:", markup)

    async def _send_interval_menu(
        self,
        update: Update,
        state: UserState,
        edit_message=None,
    ) -> None:
        keyboard = []
        for option in INTERVAL_OPTIONS:
            prefix = "✅ " if option.value == state.interval else ""
            keyboard.append(
                [InlineKeyboardButton(prefix + option.label, callback_data=f"interval:set:{option.value}")]
            )
        markup = InlineKeyboardMarkup(keyboard)
        await self._send_or_edit(update, edit_message, "选择显示间隔:", markup)

    async def _send_edit_menu(
        self,
        update: Update,
        state: UserState,
        edit_message=None,
    ) -> None:
        record = self._active_record(state)
        if not record:
            await self._send_text(update, "当前标签无效，请重新选择。")
            return
        self._tmux.ensure_session(record.session_name)
        cwd = self._tmux.get_cwd(record.session_name)
        paths = self._list_files(cwd)
        keyboard = []
        for path in paths:
            keyboard.append(
                [InlineKeyboardButton(path, callback_data=f"edit:open:{path}")]
            )
        markup = InlineKeyboardMarkup(keyboard)
        await self._send_or_edit(update, edit_message, f"当前目录: {cwd}\n选择要编辑的文件:", markup)

    async def _open_editor(self, update: Update, state: UserState, rel_path: str) -> None:
        record = self._active_record(state)
        if not record:
            await self._send_text(update, "当前标签无效，请重新选择。")
            return
        cwd = self._tmux.get_cwd(record.session_name)
        base = Path(cwd).resolve()
        target = (base / rel_path).resolve()
        if not str(target).startswith(str(base)):
            await self._send_text(update, "非法路径。")
            return
        if not target.exists() or not target.is_file():
            await self._send_text(update, "文件不存在或不可编辑。")
            return
        content = target.read_text(encoding="utf-8", errors="replace")
        edit_id = f"edit-{int(time.time())}"
        state.edit_session = EditSession(
            edit_id=edit_id,
            path=str(target),
            tab_id=record.tag_id,
            started_at=time.time(),
        )
        self._state_store.update(state)
        await self._send_text(update, f"编辑文件: {rel_path}\n发送新内容以保存。\n\n{content}")

    async def _handle_edit_content(self, update: Update, state: UserState) -> None:
        if update.message is None:
            return
        edit_session = state.edit_session
        if not edit_session:
            return
        content = update.message.text or ""
        target = Path(edit_session.path)
        target.write_text(content, encoding="utf-8")
        state.edit_session = None
        self._state_store.update(state)
        await update.message.reply_text("保存完成。")

    async def _save_editor(self, update: Update, state: UserState) -> None:
        if not state.edit_session:
            await self._send_text(update, "当前没有编辑会话。")
            return
        await self._send_text(update, "请发送内容以保存。")

    async def _send_jobs_menu(self, update: Update, state: UserState, edit_message=None) -> None:
        record = self._active_record(state)
        if not record:
            await self._send_text(update, "当前标签无效，请重新选择。")
            return
        self._tmux.ensure_session(record.session_name)
        jobs = self._tmux.list_jobs(record.session_name)
        keyboard = [[InlineKeyboardButton("CTRL-Z", callback_data="jobs:ctrlz")]]
        for job in jobs:
            label = f"#{job.job_id} {job.command[:6]}"
            keyboard.append([InlineKeyboardButton(label, callback_data=f"jobs:bg:{job.job_id}")])
        markup = InlineKeyboardMarkup(keyboard)
        await self._send_or_edit(update, edit_message, "Jobs 列表:", markup)

    async def _ctrlz_job(self, update: Update, state: UserState) -> None:
        record = self._active_record(state)
        if not record:
            await self._send_text(update, "当前标签无效，请重新选择。")
            return
        self._tmux.send_ctrlz(record.session_name)
        await self._send_text(update, "已发送 CTRL-Z")

    async def _bg_job(self, update: Update, state: UserState, job_id: str) -> None:
        record = self._active_record(state)
        if not record:
            await self._send_text(update, "当前标签无效，请重新选择。")
            return
        self._tmux.send_bg(record.session_name, job_id)
        await self._send_text(update, f"已后台化 job %{job_id}")

    async def _activate_tab(self, update: Update, state: UserState, tab_id: str) -> None:
        record = self._tag_registry.get_by_id(tab_id)
        if not record:
            await self._send_text(update, "标签不存在。")
            return
        state.active_tab_id = record.tag_id
        self._state_store.update(state)
        await self._send_text(update, f"已切换到标签 {record.tag_name}")

    async def _create_tab(self, update: Update, state: UserState) -> None:
        existing = {record.tag_name for record in self._tag_registry.list_records(state.user_id)}
        idx = len(existing) + 1
        name = f"tab-{idx}"
        while name in existing:
            idx += 1
            name = f"tab-{idx}"
        record = self._tag_registry.create_tag(state.user_id, name)
        self._tmux.ensure_session(record.session_name)
        state.active_tab_id = record.tag_id
        self._state_store.update(state)
        await self._send_text(update, f"已创建标签 {record.tag_name}")

    async def _prompt_rename(self, update: Update, state: UserState, tab_id: str) -> None:
        record = self._tag_registry.get_by_id(tab_id)
        if not record:
            await self._send_text(update, "标签不存在。")
            return
        state.rename_tab_id = tab_id
        self._state_store.update(state)
        await self._send_text(update, f"请输入新标签名（当前: {record.tag_name}）")

    async def _handle_rename(self, update: Update, state: UserState) -> None:
        if update.message is None:
            return
        new_name = (update.message.text or "").strip()
        if not new_name:
            await update.message.reply_text("标签名不能为空。")
            return
        tab_id = state.rename_tab_id
        if not tab_id:
            return
        try:
            record = self._tag_registry.rename_tag(tab_id, new_name)
        except ValueError as exc:
            await update.message.reply_text(str(exc))
            return
        state.rename_tab_id = None
        self._state_store.update(state)
        await update.message.reply_text(f"标签已重命名为 {record.tag_name}")

    async def _close_tab(self, update: Update, state: UserState, tab_id: str) -> None:
        record = self._tag_registry.get_by_id(tab_id)
        if not record:
            await self._send_text(update, "标签不存在。")
            return
        self._tag_registry.delete_tag(tab_id)
        if state.active_tab_id == tab_id:
            state.active_tab_id = None
        self._state_store.update(state)
        await self._send_text(update, f"已关闭标签 {record.tag_name}")

    async def _set_interval(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        state: UserState,
        value: str,
    ) -> None:
        if value not in {opt.value for opt in INTERVAL_OPTIONS}:
            await self._send_text(update, "无效的间隔选项。")
            return
        state.interval = value
        self._state_store.update(state)
        await self._send_text(update, f"已设置间隔: {value}")
        self._ensure_interval_job(context, state)

    async def _render_main_menu(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        state: UserState,
    ) -> None:
        keyboard = [
            [InlineKeyboardButton("标签", callback_data="tab:list")],
            [InlineKeyboardButton("间隔", callback_data="interval:list")],
            [InlineKeyboardButton("刷新", callback_data="refresh:now")],
            [InlineKeyboardButton("编辑", callback_data="edit:list")],
            [InlineKeyboardButton("JOBS", callback_data="jobs:list")],
            [InlineKeyboardButton("CLAUDE", callback_data="mode:claude")]
            if state.mode == "normal"
            else [InlineKeyboardButton("SHELL", callback_data="mode:shell")],
        ]
        markup = InlineKeyboardMarkup(keyboard)
        message = update.effective_message
        if message:
            await message.reply_text("控制面板:", reply_markup=markup)

    def _ensure_interval_job(self, context: ContextTypes.DEFAULT_TYPE, state: UserState) -> None:
        job_queue = context.job_queue
        if not job_queue:
            return
        job_name = f"interval:{state.user_id}"
        for job in job_queue.get_jobs_by_name(job_name):
            job.schedule_removal()
        if state.mode != "normal":
            return
        interval = next((opt for opt in INTERVAL_OPTIONS if opt.value == state.interval), None)
        if not interval or interval.seconds is None:
            return
        if state.chat_id is None:
            return
        job_queue.run_repeating(
            self._interval_job,
            interval=interval.seconds,
            first=interval.seconds,
            name=job_name,
            data={"user_id": state.user_id, "chat_id": state.chat_id},
            chat_id=state.chat_id,
        )

    async def _interval_job(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        job_data = context.job.data if context.job else None
        if not job_data:
            return
        user_id = job_data.get("user_id")
        if not user_id:
            return
        state = self._state_store.get(user_id)
        if not state.authorized:
            return
        chat_id = job_data.get("chat_id")
        if chat_id is None:
            return
        await self._send_capture_from_job(context, chat_id, state)

    async def _send_capture_from_job(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        chat_id: int,
        state: UserState,
    ) -> None:
        record = self._active_record(state)
        if not record:
            return
        self._tmux.ensure_session(record.session_name)
        capture = self._tmux.capture(record.session_name)
        self._last_capture[record.tag_id] = capture
        for chunk in split_for_telegram(capture):
            await context.bot.send_message(chat_id=chat_id, text=chunk)

    async def _send_text(self, update: Update, text: str) -> None:
        message = update.effective_message
        if message is None:
            return
        for chunk in split_for_telegram(text):
            await message.reply_text(chunk)

    async def _send_or_edit(self, update: Update, edit_message, text: str, markup: InlineKeyboardMarkup) -> None:
        if edit_message:
            await edit_message.edit_text(text, reply_markup=markup)
            return
        if update.message:
            await update.message.reply_text(text, reply_markup=markup)

    def _incremental(self, previous: str, current: str) -> str:
        if current.startswith(previous):
            return current[len(previous) :]
        return current

    def _validate_command(self, command: str) -> Optional[str]:
        policy = self._config.command_policy
        if not command.strip():
            return "命令不能为空。"
        if len(command) > policy.max_length:
            return "命令过长。"
        blocked = self._match_any(policy.blocked_patterns, command)
        if blocked:
            return "命令被策略阻止。"
        if policy.require_allowlist:
            if not self._match_any(policy.allowed_patterns, command):
                return "命令不在允许列表中。"
        return None

    @staticmethod
    def _match_any(patterns: List[str], command: str) -> bool:
        import re

        for pattern in patterns:
            if re.search(pattern, command):
                return True
        return False

    def _list_files(self, cwd: str) -> List[str]:
        path = Path(cwd)
        if not path.exists():
            return []
        files = [item.name for item in path.iterdir() if item.is_file()]
        return sorted(files)[:20]

    def _active_record(self, state: UserState) -> Optional[TagRecord]:
        if not state.active_tab_id:
            return None
        return self._tag_registry.get_by_id(state.active_tab_id)

    def _state_for(self, update: Update) -> UserState:
        user_id = str(update.effective_user.id) if update.effective_user else "unknown"
        state = self._state_store.get(user_id)
        chat_id = update.effective_chat.id if update.effective_chat else None
        if chat_id is not None and state.chat_id != chat_id:
            state.chat_id = chat_id
            self._state_store.update(state)
        return state

    def _ensure_auth(self, update: Update, state: UserState) -> bool:
        if state.authorized:
            return True
        if update.message:
            asyncio.create_task(update.message.reply_text("请先 /login <服务器IP> <KEY>"))
        return False
