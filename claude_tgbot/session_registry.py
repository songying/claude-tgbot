"""Persistent tag <-> tmux session registry."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .tmux import TmuxClient


STATUS_ACTIVE = "active"
STATUS_MISSING = "missing"


@dataclass
class TagRecord:
    tag_id: str
    user_id: str
    tag_name: str
    session_name: str
    status: str = STATUS_ACTIVE


class TagSessionRegistry:
    """Maintain stable tag identifiers and tmux session mappings."""

    def __init__(self, storage_path: Path, tmux_client: Optional[TmuxClient] = None) -> None:
        self._storage_path = storage_path
        self._tmux = tmux_client or TmuxClient()
        self._records: Dict[str, TagRecord] = {}
        self._tag_index: Dict[str, str] = {}
        self.load()

    def load(self) -> None:
        if not self._storage_path.exists():
            self._records = {}
            self._tag_index = {}
            return
        data = json.loads(self._storage_path.read_text(encoding="utf-8"))
        records = {}
        tag_index = {}
        for item in data.get("records", []):
            record = TagRecord(
                tag_id=item["tag_id"],
                user_id=str(item.get("user_id", "default")),
                tag_name=item["tag_name"],
                session_name=item["session_name"],
                status=item.get("status", STATUS_ACTIVE),
            )
            if record.tag_id in records:
                continue
            records[record.tag_id] = record
            key = self._tag_key(record.user_id, record.tag_name)
            if key not in tag_index:
                tag_index[key] = record.tag_id
        self._records = records
        self._tag_index = tag_index

    def save(self) -> None:
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "records": [asdict(record) for record in self._records.values()],
        }
        self._storage_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def get_by_tag(self, user_id: str, tag_name: str) -> Optional[TagRecord]:
        tag_id = self._tag_index.get(self._tag_key(user_id, tag_name))
        if not tag_id:
            return None
        return self._records.get(tag_id)

    def get_by_id(self, tag_id: str) -> Optional[TagRecord]:
        return self._records.get(tag_id)

    def create_tag(self, user_id: str, tag_name: str) -> TagRecord:
        existing = self.get_by_tag(user_id, tag_name)
        if existing:
            return existing
        tag_id = self._generate_tag_id()
        session_name = self._generate_session_name(tag_id)
        record = TagRecord(
            tag_id=tag_id,
            user_id=user_id,
            tag_name=tag_name,
            session_name=session_name,
            status=STATUS_ACTIVE,
        )
        self._records[record.tag_id] = record
        self._tag_index[self._tag_key(user_id, tag_name)] = record.tag_id
        self._tmux.new_session(session_name)
        self.save()
        return record

    def reconcile_sessions(self, create_missing: bool = True) -> List[TagRecord]:
        existing_sessions = self._tmux.list_sessions()
        updated: List[TagRecord] = []
        for record in self._records.values():
            if record.session_name in existing_sessions or self._tmux.has_session(record.session_name):
                if record.status != STATUS_ACTIVE:
                    record.status = STATUS_ACTIVE
                    updated.append(record)
                continue
            if create_missing:
                session_name = record.session_name
                if session_name in existing_sessions:
                    session_name = self._generate_session_name(record.tag_id)
                    record.session_name = session_name
                self._tmux.new_session(record.session_name)
                record.status = STATUS_ACTIVE
            else:
                record.status = STATUS_MISSING
            updated.append(record)
        if updated:
            self.save()
        return updated

    def list_records(self, user_id: Optional[str] = None) -> Iterable[TagRecord]:
        if user_id is None:
            return list(self._records.values())
        return [record for record in self._records.values() if record.user_id == user_id]

    def rename_tag(self, tag_id: str, new_name: str) -> TagRecord:
        record = self._records.get(tag_id)
        if not record:
            raise ValueError("Tag not found")
        existing = self.get_by_tag(record.user_id, new_name)
        if existing and existing.tag_id != tag_id:
            raise ValueError("Tag name already exists")
        old_key = self._tag_key(record.user_id, record.tag_name)
        self._tag_index.pop(old_key, None)
        record.tag_name = new_name
        self._tag_index[self._tag_key(record.user_id, new_name)] = record.tag_id
        self.save()
        return record

    def delete_tag(self, tag_id: str) -> None:
        record = self._records.pop(tag_id, None)
        if not record:
            return
        self._tag_index.pop(self._tag_key(record.user_id, record.tag_name), None)
        self._tmux.kill_session(record.session_name)
        self.save()

    def _generate_tag_id(self) -> str:
        existing_ids = set(self._records.keys())
        for _ in range(100):
            candidate = str(uuid.uuid4())
            if candidate not in existing_ids:
                return candidate
        raise RuntimeError("Unable to generate unique tag id")

    def _generate_session_name(self, tag_id: str) -> str:
        candidate = f"tgbot_{tag_id}"
        if self._tmux.has_session(candidate):
            raise RuntimeError("Generated tmux session already exists")
        return candidate

    @staticmethod
    def _tag_key(user_id: str, tag_name: str) -> str:
        return f"{user_id}:{tag_name}"
