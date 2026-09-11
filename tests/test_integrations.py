from smos.services.integrations import JulesService, GitHubService

def test_integrations():
    jules = JulesService()
    session = jules.create_session("Fix bug", repo="owner/repo")
    assert session["session_id"] == "mock-session-123"

    gh = GitHubService()
    issue = gh.create_issue("owner/repo", "Test Issue", "Body")
    assert "issue_url" in issue

    pr = gh.create_pull_request("owner/repo", "Test PR", "feature-branch")
    assert "pr_url" in pr

if __name__ == "__main__":
    test_integrations()
