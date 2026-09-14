"""Jules CLI Adapter for Co-SMOS Control Room v0.9.

Wraps execution of project shell scripts using subprocess.run strictly without shell=True.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from smos.core.events import EventTracker


class JulesCLIAdapter:
    def __init__(self, scripts_dir: Optional[Path] = None):
        if scripts_dir is None:
            project_root = Path(os.environ.get("JULES_PROJECT_ROOT", "."))
            scripts_dir = project_root / "scripts"
        self.scripts_dir = Path(scripts_dir)

    def _run_script(self, script_name: str, args: List[str]) -> Dict[str, Any]:
        script_path = self.scripts_dir / script_name
        if not script_path.exists():
            return {
                "success": False,
                "exit_code": 127,
                "stdout": "",
                "stderr": f"Script not found: {script_path}",
                "error": f"Script not found: {script_path}"
            }

        cmd = [str(script_path)] + args
        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False
            )
            success = (res.returncode == 0)
            result = {
                "success": success,
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "error": None if success else (res.stderr or res.stdout or f"Script failed with code {res.returncode}")
            }
            EventTracker.emit(
                event_type="cli_execution",
                source="JulesCLIAdapter",
                payload={"script": script_name, "args": args, "exit_code": res.returncode, "success": success}
            )
            return result
        except Exception as e:
            return {
                "success": False,
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "error": str(e)
            }

    def add_task(self, description: str, priority: int = 5) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-add.sh."""
        return self._run_script("jules-queue-add.sh", [description, str(priority)])

    def run_queue(self, mode: str = "once", dry_run: bool = False) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-runner.sh."""
        args = [f"--{mode}"]
        if dry_run:
            args.append("--dry-run")
        return self._run_script("jules-queue-runner.sh", args)

    def list_proposals(self, filter_priority: Optional[str] = None, filter_source: Optional[str] = None) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-review.sh list."""
        args = ["list"]
        if filter_priority:
            args.extend(["--priority", filter_priority])
        if filter_source:
            args.extend(["--source-task", filter_source])
        return self._run_script("jules-queue-review.sh", args)

    def accept_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-review.sh accept <id>."""
        return self._run_script("jules-queue-review.sh", ["accept", proposal_id])

    def defer_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-review.sh defer <id>."""
        return self._run_script("jules-queue-review.sh", ["defer", proposal_id])

    def reject_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """Wrapper for scripts/jules-queue-review.sh reject <id>."""
        return self._run_script("jules-queue-review.sh", ["reject", proposal_id])
