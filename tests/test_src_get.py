"""Tests for src-get URL parsing and directory resolution."""

from pathlib import Path

import pytest

from src_get import parse_url, resolve_root, target_directory


class TestParseUrl:
    def test_ssh_scp_style(self):
        host, parts = parse_url("git@github.com:jhulten/src-get.git")
        assert host == "github.com"
        assert parts == ["jhulten", "src-get.git"]

    def test_ssh_scp_style_nested(self):
        host, parts = parse_url("git@gitlab.com:org/team/sub/repo.git")
        assert host == "gitlab.com"
        assert parts == ["org", "team", "sub", "repo.git"]

    def test_https(self):
        host, parts = parse_url("https://github.com/jhulten/src-get.git")
        assert host == "github.com"
        assert parts == ["jhulten", "src-get.git"]

    def test_https_no_git_suffix(self):
        host, parts = parse_url("https://github.com/jhulten/src-get")
        assert host == "github.com"
        assert parts == ["jhulten", "src-get"]

    def test_https_nested_gitlab(self):
        host, parts = parse_url("https://gitlab.com/org/team/subteam/myrepo.git")
        assert host == "gitlab.com"
        assert parts == ["org", "team", "subteam", "myrepo.git"]

    def test_ssh_url_style(self):
        host, parts = parse_url("ssh://git@github.com/owner/repo.git")
        assert host == "github.com"
        assert parts == ["owner", "repo.git"]

    def test_unsupported_bare_path_raises(self):
        with pytest.raises(ValueError, match="Unsupported URL format"):
            parse_url("github.com/owner/repo")

    def test_empty_host_scp_raises(self):
        with pytest.raises(ValueError, match="Could not determine host"):
            parse_url("git@:owner/repo.git")

    def test_https_missing_host_raises(self):
        # urlparse with no host in an https URL
        with pytest.raises(ValueError, match="Could not determine host"):
            parse_url("https:///owner/repo.git")

    def test_git_scheme_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported URL format"):
            parse_url("git://github.com/owner/repo.git")


class TestResolveRoot:
    def test_flag_takes_precedence(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SRC_DIR", "/env/src")
        result = resolve_root(str(tmp_path / "flag_src"))
        assert result == (tmp_path / "flag_src").resolve()

    def test_env_var(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SRC_DIR", str(tmp_path / "env_src"))
        result = resolve_root(None)
        assert result == (tmp_path / "env_src").resolve()

    def test_default_home_src(self, monkeypatch):
        monkeypatch.delenv("SRC_DIR", raising=False)
        result = resolve_root(None)
        assert result == Path.home() / "src"

    def test_empty_string_flag_uses_cwd_resolution_not_fallback(self, monkeypatch):
        """Empty string is a valid (if odd) explicit value, not a fallback trigger."""
        monkeypatch.delenv("SRC_DIR", raising=False)
        # Empty string resolves to cwd, not $HOME/src
        result = resolve_root("")
        assert result != Path.home() / "src"


class TestTargetDirectory:
    def test_strips_git_suffix(self):
        root = Path("/src")
        target = target_directory(root, "github.com", ["jhulten", "src-get.git"], bare=False)
        assert target == Path("/src/github.com/jhulten/src-get")

    def test_keeps_git_suffix_when_bare(self):
        root = Path("/src")
        target = target_directory(root, "github.com", ["jhulten", "src-get.git"], bare=True)
        assert target == Path("/src/github.com/jhulten/src-get.git")

    def test_nested_gitlab_path(self):
        root = Path("/src")
        target = target_directory(
            root, "gitlab.com", ["org", "team", "sub", "repo.git"], bare=False
        )
        assert target == Path("/src/gitlab.com/org/team/sub/repo")

    def test_no_git_suffix_in_url(self):
        root = Path("/src")
        target = target_directory(root, "github.com", ["owner", "repo"], bare=False)
        assert target == Path("/src/github.com/owner/repo")

    def test_empty_components_raises(self):
        with pytest.raises(ValueError):
            target_directory(Path("/src"), "github.com", [], bare=False)
