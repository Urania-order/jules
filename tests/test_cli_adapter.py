import pytest
from pathlib import Path
from smos.adapters.jules_cli import JulesCLIAdapter

def test_cli_adapter_add_task(tmp_path, monkeypatch):
    scripts_dir = Path("scripts")
    adapter = JulesCLIAdapter(scripts_dir=scripts_dir)
    res = adapter.add_task("Test task from unit test", priority=3)
    assert res["success"] is True
    assert "Task added to queue successfully" in res["stdout"]

def test_cli_adapter_nonexistent_script(tmp_path):
    adapter = JulesCLIAdapter(scripts_dir=tmp_path)
    res = adapter.add_task("Test non-existent", priority=1)
    assert res["success"] is False
    assert res["exit_code"] == 127
    assert "Script not found" in res["error"]
