"""Tests for src-get URL parsing and directory resolution."""

import subprocess
from pathlib import Path

import pytest

from src_get import main, parse_url, resolve_root, target_directory


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


class FakeCompletedProcess:
    def __init__(self, returncode: int):
        self.returncode = returncode


def make_fake_run(returncode=0, calls=None, *, raises=None, create_target=None):
    """Build a fake subprocess.run that records invocations.

    - returncode: value returned for every call.
    - calls: list to append (args, cwd) tuples to.
    - raises: exception instance to raise instead of returning.
    - create_target: if set, a Path created when a clone command is seen
      (simulates git clone materializing the target directory).
    """
    if calls is None:
        calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append((cmd, cwd))
        if raises is not None:
            raise raises
        if create_target is not None and len(cmd) >= 2 and cmd[1] == "clone":
            create_target.mkdir(parents=True, exist_ok=True)
        return FakeCompletedProcess(returncode)

    fake_run.calls = calls
    return fake_run


class TestMain:
    """End-to-end coverage of main()'s clone/fetch/pull branching."""

    def _run_main(self, monkeypatch, tmp_path, argv_extra=None):
        """Set argv for main() with SRC_DIR unset and root at tmp_path/src."""
        monkeypatch.delenv("SRC_DIR", raising=False)
        root = tmp_path / "src"
        argv = ["src-get", "--src-dir", str(root)] + (argv_extra or [])
        monkeypatch.setattr("sys.argv", argv)
        return root

    def test_new_repo_clones(self, monkeypatch, tmp_path, capsys):
        root = self._run_main(
            monkeypatch, tmp_path, ["https://github.com/owner/repo.git"]
        )
        target = root / "github.com" / "owner" / "repo"
        fake_run = make_fake_run(returncode=0, create_target=target)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        # A single git clone was invoked with the URL and target path.
        assert len(fake_run.calls) == 1
        cmd, cwd = fake_run.calls[0]
        assert cmd[:2] == ["git", "clone"]
        assert "https://github.com/owner/repo.git" in cmd
        assert str(target) in cmd
        # Parent directory was created.
        assert target.parent.is_dir()
        # Target path is the last line of stdout.
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)

    def test_existing_repo_fetches_then_pulls(self, monkeypatch, tmp_path, capsys):
        root = self._run_main(
            monkeypatch, tmp_path, ["https://github.com/owner/repo.git"]
        )
        target = root / "github.com" / "owner" / "repo"
        target.mkdir(parents=True)
        fake_run = make_fake_run(returncode=0)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        # git fetch then git pull, both against the target dir; no clone.
        assert [cmd[1] for cmd, _ in fake_run.calls] == ["fetch", "pull"]
        assert all(cwd == target for _, cwd in fake_run.calls)
        assert all(cmd[1] != "clone" for cmd, _ in fake_run.calls)
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)

    def test_clone_nonzero_exit_propagates(self, monkeypatch, tmp_path):
        self._run_main(monkeypatch, tmp_path, ["https://github.com/owner/repo.git"])
        fake_run = make_fake_run(returncode=42)
        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 42

    def test_fetch_nonzero_exit_propagates(self, monkeypatch, tmp_path):
        root = self._run_main(
            monkeypatch, tmp_path, ["https://github.com/owner/repo.git"]
        )
        target = root / "github.com" / "owner" / "repo"
        target.mkdir(parents=True)
        fake_run = make_fake_run(returncode=7)
        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 7
        # Fetch failed, so pull must not have run.
        assert [cmd[1] for cmd, _ in fake_run.calls] == ["fetch"]

    def test_git_not_found(self, monkeypatch, tmp_path, capsys):
        self._run_main(monkeypatch, tmp_path, ["https://github.com/owner/repo.git"])
        fake_run = make_fake_run(raises=FileNotFoundError())
        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "git not found" in capsys.readouterr().err
