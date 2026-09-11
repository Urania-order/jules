import subprocess
import json

class JulesService:
    def create_session(self, task: str, repo: str = None):
        cmd = ["jules", "remote", "new", task]
        if repo:
            cmd.extend(["--repo", repo])

        # Mocking the call since we don't have a real jules backend/token here
        # but the logic follows the spec
        print(f"Executing: {' '.join(cmd)}")
        # In a real scenario, we would parse the output to get the session ID
        return {"status": "success", "session_id": "mock-session-123", "task": task}

    def get_status(self, session_id: str):
        print(f"Checking status for session: {session_id}")
        return {"session_id": session_id, "status": "COMPLETED"}

class GitHubService:
    def create_issue(self, repo: str, title: str, body: str):
        print(f"Creating GitHub Issue in {repo}: {title}")
        return {"issue_url": f"https://github.com/{repo}/issues/1"}

    def create_pull_request(self, repo: str, title: str, head: str, base: str = "main"):
        print(f"Creating GitHub PR in {repo}: {title}")
        return {"pr_url": f"https://github.com/{repo}/pull/1"}
