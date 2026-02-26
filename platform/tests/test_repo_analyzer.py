"""Tests for repo_analyzer: multi-host URL parsing & API base resolution."""
import pytest

from app.services.repo_analyzer import (
    _resolve_api_config,
    parse_repo_url,
)


# ── parse_repo_url ──────────────────────────────────────


class TestParseRepoUrl:
    def test_github_https(self):
        owner, repo, host = parse_repo_url("https://github.com/owner/my-repo")
        assert owner == "owner"
        assert repo == "my-repo"
        assert host == "github.com"

    def test_github_https_dot_git(self):
        owner, repo, host = parse_repo_url("https://github.com/acme/app.git")
        assert owner == "acme"
        assert repo == "app"
        assert host == "github.com"

    def test_github_ssh(self):
        owner, repo, host = parse_repo_url("git@github.com:owner/repo.git")
        assert owner == "owner"
        assert repo == "repo"
        assert host == "github.com"

    def test_ghe_https(self):
        owner, repo, host = parse_repo_url(
            "https://scm.starbucks.com/team/cool-project"
        )
        assert owner == "team"
        assert repo == "cool-project"
        assert host == "scm.starbucks.com"

    def test_ghe_https_dot_git(self):
        owner, repo, host = parse_repo_url(
            "https://scm.starbucks.com/team/cool-project.git"
        )
        assert owner == "team"
        assert repo == "cool-project"
        assert host == "scm.starbucks.com"

    def test_ghe_ssh(self):
        owner, repo, host = parse_repo_url(
            "git@scm.starbucks.com:team/cool-project.git"
        )
        assert owner == "team"
        assert repo == "cool-project"
        assert host == "scm.starbucks.com"

    def test_arbitrary_domain_https(self):
        owner, repo, host = parse_repo_url(
            "https://git.example.org/group/subgroup"
        )
        assert owner == "group"
        assert repo == "subgroup"
        assert host == "git.example.org"

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_repo_url("not-a-url")


# ── _resolve_api_config ─────────────────────────────────


class TestResolveApiConfig:
    def test_github_dot_com(self):
        api_base, _ = _resolve_api_config("github.com")
        assert api_base == "https://api.github.com"

    def test_ghe_with_configured_base_url(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_BASE_URL",
            "https://scm.starbucks.com/api/v3",
        )
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_TOKEN",
            "ghe-test-token",
        )
        api_base, token = _resolve_api_config("scm.starbucks.com")
        assert api_base == "https://scm.starbucks.com/api/v3"
        assert token == "ghe-test-token"

    def test_ghe_fallback_without_config(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_BASE_URL", ""
        )
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_TOKEN", "fallback-tok"
        )
        api_base, token = _resolve_api_config("scm.starbucks.com")
        assert api_base == "https://scm.starbucks.com/api/v3"
        assert token == "fallback-tok"

    def test_ghe_base_url_trailing_slash(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_BASE_URL",
            "https://scm.starbucks.com/api/v3/",
        )
        monkeypatch.setattr(
            "app.services.repo_analyzer.settings.GHE_TOKEN", "tok"
        )
        api_base, _ = _resolve_api_config("scm.starbucks.com")
        assert not api_base.endswith("/")
