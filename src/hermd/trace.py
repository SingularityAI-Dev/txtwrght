"""JSONL run trace: every browser state, LLM output, action result, timing.

One file per run. This is the "measure, do not assume" artifact and the input
to the Phase 5 distillation loop. Values typed into password inputs are
scrubbed by the agent before they reach write().
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Trace:
    def __init__(self, directory: str | Path = "traces", run_id: str | None = None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = run_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        self.path = self.directory / f"run-{stamp}.jsonl"
        self._file = self.path.open("a", encoding="utf-8")

    def write(self, event_type: str, **data: Any) -> None:
        record = {"ts": round(time.time(), 3), "type": event_type, **data}
        self._file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "Trace":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
