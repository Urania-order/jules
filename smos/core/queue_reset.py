"""Queue Reset Manager for Co-SMOS Control Room v1.1."""

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Any, Optional


class QueueResetManager:
    def __init__(self, queue_dir: Optional[Path] = None):
        if queue_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            queue_dir = project_root / ".jules" / "queue"
        self.queue_dir = Path(queue_dir)
        self.pending_dir = self.queue_dir / "pending"
        self.running_dir = self.queue_dir / "running"
        self.completed_dir = self.queue_dir / "completed"
        self.deferred_dir = self.queue_dir / "deferred"

        for d in [self.pending_dir, self.running_dir, self.completed_dir, self.deferred_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def reset_queue(self, scope: str = "all") -> Dict[str, Any]:
        valid_scopes = {"all", "pending", "running", "completed"}
        if scope not in valid_scopes:
            raise ValueError(f"Invalid scope: {scope}. Must be one of {valid_scopes}")

        targets = []
        if scope == "all":
            targets = [("pending", self.pending_dir), ("running", self.running_dir), ("completed", self.completed_dir)]
        elif scope == "pending":
            targets = [("pending", self.pending_dir)]
        elif scope == "running":
            targets = [("running", self.running_dir)]
        elif scope == "completed":
            targets = [("completed", self.completed_dir)]

        cleared_counts = {"pending": 0, "running": 0, "completed": 0}
        total_moved = 0

        for name, folder in targets:
            for p in list(folder.glob("*.json")):
                try:
                    dest = self.deferred_dir / p.name
                    if dest.exists():
                        dest = self.deferred_dir / f"{p.stem}_reset_{os.urandom(4).hex()}.json"

                    try:
                        data = json.loads(p.read_text(encoding="utf-8"))
                        data["status"] = "deferred"
                        data["metadata"] = data.get("metadata", {})
                        data["metadata"]["reset_from_scope"] = name
                        dest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                        p.unlink()
                    except Exception:
                        shutil.move(str(p), str(dest))

                    cleared_counts[name] += 1
                    total_moved += 1
                except Exception:
                    continue

        return {
            "status": "success",
            "moved": total_moved,
            "cleared": cleared_counts
        }
