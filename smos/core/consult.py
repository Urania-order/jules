import os
import json
import secrets
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone


DEFAULT_SETTINGS = {
    "tokens": {
        "consultant": {"token": "dev-consultant-token", "status": "active"},
        "operator": {"token": "dev-operator-token", "status": "active"},
        "admin": {"token": "dev-admin-token", "status": "active"},
    },
    "rate_limits": {
        "consultant": 100,
        "operator": 1000,
        "admin": None,
    },
    "endpoints": {
        "/api/consult/state": True,
        "/api/consult/tasks": True,
        "/api/consult/task/{id}": True,
        "/api/consult/events": True,
        "/api/consult/errata": True,
        "/api/consult/health": True,
    },
}


class ConsultSettingsManager:
    def __init__(self):
        self._rate_limit_history: Dict[str, List[float]] = {
            "consultant": [],
            "operator": [],
            "admin": [],
            "public": [],
        }

    @property
    def project_root(self) -> Path:
        return Path(os.environ.get("JULES_PROJECT_ROOT", "."))

    @property
    def settings_path(self) -> Path:
        return self.project_root / ".jules" / "consult_settings.json"

    def get_settings(self) -> Dict[str, Any]:
        path = self.settings_path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            c_tok = os.environ.get("JULES_CONSULTANT_TOKEN", "dev-consultant-token")
            o_tok = os.environ.get("JULES_OPERATOR_TOKEN", "dev-operator-token")
            a_tok = os.environ.get("JULES_ADMIN_TOKEN", "dev-admin-token")
            defaults = json.loads(json.dumps(DEFAULT_SETTINGS))
            defaults["tokens"]["consultant"]["token"] = c_tok
            defaults["tokens"]["operator"]["token"] = o_tok
            defaults["tokens"]["admin"]["token"] = a_tok
            self.save_settings(defaults)
            return defaults
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = json.loads(json.dumps(DEFAULT_SETTINGS))
            if "tokens" in data and isinstance(data["tokens"], dict):
                merged["tokens"].update(data["tokens"])
            if "rate_limits" in data and isinstance(data["rate_limits"], dict):
                merged["rate_limits"].update(data["rate_limits"])
            if "endpoints" in data and isinstance(data["endpoints"], dict):
                merged["endpoints"].update(data["endpoints"])
            return merged
        except Exception:
            return json.loads(json.dumps(DEFAULT_SETTINGS))

    def save_settings(self, settings: Dict[str, Any]) -> None:
        path = self.settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)

    def reset_rate_limit_history(self, role: Optional[str] = None) -> None:
        if role:
            self._rate_limit_history[role] = []
        else:
            self._rate_limit_history = {
                "consultant": [],
                "operator": [],
                "admin": [],
                "public": [],
            }

    def update_settings(self, new_data: Dict[str, Any]) -> Dict[str, Any]:
        curr = self.get_settings()
        if "rate_limits" in new_data and isinstance(new_data["rate_limits"], dict):
            for k, v in new_data["rate_limits"].items():
                if k in curr["rate_limits"]:
                    curr["rate_limits"][k] = v
                    self.reset_rate_limit_history(k)
        if "endpoints" in new_data and isinstance(new_data["endpoints"], dict):
            for k, v in new_data["endpoints"].items():
                if k in curr["endpoints"]:
                    curr["endpoints"][k] = bool(v)
        if "tokens" in new_data and isinstance(new_data["tokens"], dict):
            for k, v in new_data["tokens"].items():
                if k in curr["tokens"] and isinstance(v, dict):
                    curr["tokens"][k].update(v)
        self.save_settings(curr)
        return curr

    def regenerate_token(self, role: str) -> str:
        if role not in ("consultant", "operator", "admin"):
            raise ValueError(f"Invalid role '{role}'")
        new_token = f"dev-{role}-token-{secrets.token_hex(8)}"
        settings = self.get_settings()
        settings["tokens"][role] = {
            "token": new_token,
            "status": "active"
        }
        self.save_settings(settings)
        return new_token

    def disable_token(self, role: str) -> None:
        if role not in ("consultant", "operator", "admin"):
            raise ValueError(f"Invalid role '{role}'")
        settings = self.get_settings()
        if role in settings["tokens"]:
            settings["tokens"][role]["status"] = "disabled"
        self.save_settings(settings)

    def check_rate_limit(self, role: str) -> bool:
        """Returns True if request is allowed, False if limit exceeded."""
        settings = self.get_settings()
        limit = settings.get("rate_limits", {}).get(role)
        if limit is None or limit <= 0:
            return True

        now = time.time()
        window_start = now - 3600.0
        if role not in self._rate_limit_history:
            self._rate_limit_history[role] = []

        self._rate_limit_history[role] = [
            ts for ts in self._rate_limit_history[role] if ts > window_start
        ]

        if len(self._rate_limit_history[role]) >= limit:
            return False

        self._rate_limit_history[role].append(now)
        return True

    def is_endpoint_enabled(self, endpoint_key: str) -> bool:
        settings = self.get_settings()
        return settings.get("endpoints", {}).get(endpoint_key, True)


class ConsultAuditLogger:
    @property
    def project_root(self) -> Path:
        return Path(os.environ.get("JULES_PROJECT_ROOT", "."))

    @property
    def audit_path(self) -> Path:
        return self.project_root / ".jules" / "consult_audit.jsonl"

    def log_request(self, role: str, method: str, path: str, status_code: int) -> None:
        file_path = self.audit_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        record = {
            "timestamp": now_str,
            "role": role,
            "method": method,
            "path": path,
            "status_code": status_code,
        }
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        file_path = self.audit_path
        if not file_path.exists():
            return []
        lines = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            lines.append(json.loads(line))
                        except Exception:
                            pass
        except Exception:
            return []
        return lines[-limit:][::-1]


consult_settings_manager = ConsultSettingsManager()
consult_audit_logger = ConsultAuditLogger()
