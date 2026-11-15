"""Append-only SHA-256 hash chain. Tamper-evident, NOT tamper-proof, NOT a blockchain.

The deck asks for HealthAudit.sol on an EVM chain. That is not implemented; see
docs/SAFETY_ISSUES.md S9. No raw measurement is written here — only event metadata.
"""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AuditEntry

GENESIS = "0" * 64


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def digest(payload: dict[str, Any]) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class AuditLog:
    """In-memory chain with optional JSONL persistence."""

    def __init__(self, path: Path | None = None) -> None:
        self._entries: list[AuditEntry] = []
        self._lock = threading.Lock()
        self._path = path
        if path is not None and path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._entries.append(AuditEntry.model_validate_json(line))

    def append(self, event: str, role: str, subject_id: str, lane: str,
               detail: dict[str, Any] | None = None) -> AuditEntry:
        with self._lock:
            prev = self._entries[-1].sha256 if self._entries else GENESIS
            payload = {
                "seq": len(self._entries),
                "ts": _now(),
                "event": event,
                "role": role,
                "subject_id": subject_id,
                "lane": lane,
                "detail": detail or {},
                "prev_sha256": prev,
            }
            entry = AuditEntry(**payload, sha256=digest(payload))
            self._entries.append(entry)
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(entry.model_dump_json() + "\n")
            return entry

    def entries(self) -> list[AuditEntry]:
        with self._lock:
            return list(self._entries)

    def verify(self) -> dict[str, Any]:
        """Recompute every link. Returns the first broken index, if any."""
        with self._lock:
            prev = GENESIS
            for i, entry in enumerate(self._entries):
                payload = {
                    "seq": entry.seq, "ts": entry.ts, "event": entry.event, "role": entry.role,
                    "subject_id": entry.subject_id, "lane": entry.lane, "detail": entry.detail,
                    "prev_sha256": entry.prev_sha256,
                }
                if entry.seq != i or entry.prev_sha256 != prev or digest(payload) != entry.sha256:
                    return {"ok": False, "entries": len(self._entries), "first_bad_index": i,
                            "reason": "hash chain mismatch"}
                prev = entry.sha256
            return {"ok": True, "entries": len(self._entries), "first_bad_index": None,
                    "reason": "chain intact", "head": prev}

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            if self._path is not None and self._path.exists():
                self._path.unlink()
