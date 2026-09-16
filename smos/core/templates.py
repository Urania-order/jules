"""Task Template Manager for Co-SMOS Control Room v1.1."""

import json
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from smos.core.task import Task
from smos.core.queue import QueueManager


class TaskTemplate(BaseModel):
    id: str
    name: str
    request: str
    priority: int = 5
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TemplateManager:
    def __init__(self, templates_dir: Optional[Path] = None):
        if templates_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            templates_dir = project_root / ".jules" / "templates"
        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def create_template_from_task(self, name: str, task: Task) -> TaskTemplate:
        template_id = f"tpl-{uuid.uuid4().hex[:8]}"
        req_text = task.request or task.title or task.description or "Unnamed task"
        tpl = TaskTemplate(
            id=template_id,
            name=name,
            request=req_text,
            priority=task.priority,
            tags=getattr(task, "tags", []) or [],
            notes=getattr(task, "notes", None),
            description=task.description,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        self.save_template(tpl)
        return tpl

    def save_template(self, template: TaskTemplate) -> None:
        filepath = self.templates_dir / f"{template.id}.json"
        data = template.model_dump()
        filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def list_templates(self) -> List[TaskTemplate]:
        templates = []
        for p in sorted(self.templates_dir.glob("tpl-*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                templates.append(TaskTemplate(**data))
            except Exception:
                continue
        templates.sort(key=lambda x: x.created_at, reverse=True)
        return templates

    def get_template(self, template_id: str) -> Optional[TaskTemplate]:
        p = self.templates_dir / f"{template_id}.json"
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return TaskTemplate(**data)
        except Exception:
            return None

    def delete_template(self, template_id: str) -> bool:
        p = self.templates_dir / f"{template_id}.json"
        if p.exists():
            p.unlink()
            return True
        return False

    def use_template(self, template_id: str, queue_manager: Optional[QueueManager] = None) -> Optional[Task]:
        tpl = self.get_template(template_id)
        if not tpl:
            return None

        qm = queue_manager or QueueManager()
        task_id = f"task-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
        
        task = Task(
            id=task_id,
            request=tpl.request,
            title=tpl.name or tpl.request[:50],
            description=tpl.description,
            priority=tpl.priority,
            tags=list(tpl.tags) if tpl.tags else [],
            notes=tpl.notes,
            proposed_by="template",
        )
        qm.save_task(task)
        return task
