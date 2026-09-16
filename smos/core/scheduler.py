"""Background scheduler module for Co-SMOS batch execution."""

import os
import logging
from datetime import datetime, time, timezone
from typing import Dict, Any, List, Optional
from smos.core.batch import BatchManager

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}

ALL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WORKDAYS = ["mon", "tue", "wed", "thu", "fri"]


class Scheduler:
    def __init__(self, batch_manager: Optional[BatchManager] = None):
        self.schedules: Dict[str, Dict[str, Any]] = {}
        self.batch_manager = batch_manager or BatchManager()
        self.last_run: Optional[str] = None
        self._load_default_schedules()

    def _load_default_schedules(self) -> None:
        night_start = os.environ.get("JULES_SCHEDULE_NIGHT_START", "02:00")
        night_end = os.environ.get("JULES_SCHEDULE_NIGHT_END", "06:00")
        window_start = os.environ.get("JULES_SCHEDULE_WINDOW_START", "09:00")
        window_end = os.environ.get("JULES_SCHEDULE_WINDOW_END", "18:00")

        self.register_schedule("night", {
            "start": night_start,
            "end": night_end,
            "days": ALL_DAYS
        })

        self.register_schedule("window", {
            "start": window_start,
            "end": window_end,
            "days": WORKDAYS
        })

    def register_schedule(self, name: str, config: Dict[str, Any]) -> None:
        if "start" not in config or "end" not in config:
            raise ValueError("Schedule config must contain 'start' and 'end' keys")
        days = [d.lower()[:3] for d in config.get("days", ALL_DAYS)]
        self.schedules[name.lower()] = {
            "start": config["start"],
            "end": config["end"],
            "days": days
        }

    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        return self.schedules

    def is_due(self, name: str, now: Optional[datetime] = None) -> bool:
        schedule_name = name.lower()
        if schedule_name not in self.schedules:
            return False

        config = self.schedules[schedule_name]
        if now is None:
            now = datetime.now(timezone.utc)

        current_day = DAY_MAP.get(now.weekday())
        if current_day not in config["days"]:
            return False

        try:
            start_h, start_m = map(int, config["start"].split(":"))
            end_h, end_m = map(int, config["end"].split(":"))
        except ValueError:
            return False

        start_time = time(start_h, start_m)
        end_time = time(end_h, end_m)
        current_time = time(now.hour, now.minute)

        if start_time <= end_time:
            return start_time <= current_time < end_time
        else:
            # Crosses midnight (e.g. 22:00 to 04:00)
            return current_time >= start_time or current_time < end_time

    def check_due_batches(self, now: Optional[datetime] = None) -> List[str]:
        self.last_run = datetime.now(timezone.utc).isoformat()
        return self.batch_manager.run_due_batches(scheduler=self, now=now)

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "active",
            "last_run": self.last_run,
            "schedules": self.schedules
        }
