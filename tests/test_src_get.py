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

    - returncode: value returned for every call, or a dict mapping the git
      subcommand (e.g. "fetch") to its return code.
    - calls: list to append (args, cwd) tuples to.
    - raises: exception instance to raise instead of returning.
    - create_target: if set, a Path created when a clone command is seen
      (simulates git clone materializing the target directory). Only the
      leaf directory is created (no parents=True), so the fake requires
      main() to have created target.parent first -- a regression that drops
      that mkdir surfaces as FileNotFoundError.
    """
    if calls is None:
        calls = []

    def fake_run(cmd, cwd=None, **kwargs):
        calls.append((cmd, cwd))
        if raises is not None:
            raise raises
        subcommand = cmd[1] if len(cmd) >= 2 else None
        if create_target is not None and subcommand == "clone":
            create_target.mkdir(exist_ok=True)
        code = returncode[subcommand] if isinstance(returncode, dict) else returncode
        return FakeCompletedProcess(code)

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

        # A single git clone was invoked with the exact command and no cwd.
        assert len(fake_run.calls) == 1
        cmd, cwd = fake_run.calls[0]
        assert cmd == [
            "git",
            "clone",
            "https://github.com/owner/repo.git",
            str(target),
        ]
        assert cwd is None
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

    def test_pull_nonzero_exit_propagates(self, monkeypatch, tmp_path):
        root = self._run_main(
            monkeypatch, tmp_path, ["https://github.com/owner/repo.git"]
        )
        target = root / "github.com" / "owner" / "repo"
        target.mkdir(parents=True)
        # Fetch succeeds, pull fails with a distinct code.
        fake_run = make_fake_run(returncode={"fetch": 0, "pull": 13})
        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 13
        # Both ran, in order.
        assert [cmd[1] for cmd, _ in fake_run.calls] == ["fetch", "pull"]

    def test_git_not_found(self, monkeypatch, tmp_path, capsys):
        self._run_main(monkeypatch, tmp_path, ["https://github.com/owner/repo.git"])
        fake_run = make_fake_run(raises=FileNotFoundError())
        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        assert "git not found" in capsys.readouterr().err


class TestBarePassthrough:
    """End-to-end coverage of --bare detection within the -- passthrough."""

    def _run_main(self, monkeypatch, tmp_path, argv_extra):
        monkeypatch.delenv("SRC_DIR", raising=False)
        root = tmp_path / "src"
        argv = ["src-get", "--src-dir", str(root)] + argv_extra
        monkeypatch.setattr("sys.argv", argv)
        return root

    def test_bare_keeps_git_suffix_and_forwards_flag(
        self, monkeypatch, tmp_path, capsys
    ):
        url = "git@github.com:owner/repo.git"
        root = self._run_main(monkeypatch, tmp_path, [url, "--", "--bare"])
        target = root / "github.com" / "owner" / "repo.git"
        fake_run = make_fake_run(returncode=0, create_target=target)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        cmd, cwd = fake_run.calls[0]
        # --bare is forwarded to git clone, before the URL and target.
        assert cmd == ["git", "clone", "--bare", url, str(target)]
        assert cwd is None
        # Target directory name retains the .git suffix.
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)
        assert str(target).endswith("repo.git")

    def test_without_bare_strips_git_suffix(self, monkeypatch, tmp_path, capsys):
        url = "git@github.com:owner/repo.git"
        root = self._run_main(monkeypatch, tmp_path, [url])
        target = root / "github.com" / "owner" / "repo"
        fake_run = make_fake_run(returncode=0, create_target=target)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        cmd, _ = fake_run.calls[0]
        assert cmd == ["git", "clone", url, str(target)]
        assert "--bare" not in cmd
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)
        assert not str(target).endswith(".git")

    def test_other_passthrough_flag_does_not_trigger_bare(
        self, monkeypatch, tmp_path, capsys
    ):
        url = "git@github.com:owner/repo.git"
        root = self._run_main(monkeypatch, tmp_path, [url, "--", "--depth", "1"])
        # --depth is not --bare, so the .git suffix is still stripped.
        target = root / "github.com" / "owner" / "repo"
        fake_run = make_fake_run(returncode=0, create_target=target)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        cmd, _ = fake_run.calls[0]
        # Passthrough flags are forwarded to git clone; bare not triggered.
        assert cmd == ["git", "clone", "--depth", "1", url, str(target)]
        assert "--bare" not in cmd
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)
        assert not str(target).endswith(".git")


class TestFilePathErrors:
    """A file where a directory is expected yields a clean error, not a traceback."""

    def _run_main(self, monkeypatch, argv_extra):
        monkeypatch.delenv("SRC_DIR", raising=False)
        monkeypatch.setattr("sys.argv", ["src-get"] + argv_extra)

    def _no_git(self, monkeypatch):
        """Install a git mock that fails loudly if git is ever invoked."""

        def fake_run(cmd, cwd=None, **kwargs):
            raise AssertionError(f"git should not run, got: {cmd}")

        monkeypatch.setattr(subprocess, "run", fake_run)

    def test_root_is_a_file(self, monkeypatch, tmp_path, capsys):
        root_file = tmp_path / "not-a-dir"
        root_file.write_text("")
        self._run_main(
            monkeypatch,
            ["--src-dir", str(root_file), "git@github.com:owner/repo.git"],
        )
        self._no_git(monkeypatch)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert err.startswith("src-get: error:")
        assert "Traceback" not in err
        assert str(root_file) in err

    def test_intermediate_component_is_a_file(self, monkeypatch, tmp_path, capsys):
        root = tmp_path / "src"
        root.mkdir()
        # The host component of the target path already exists as a file.
        (root / "github.com").write_text("")
        self._run_main(
            monkeypatch,
            ["--src-dir", str(root), "git@github.com:owner/repo.git"],
        )
        self._no_git(monkeypatch)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert err.startswith("src-get: error:")
        assert "Traceback" not in err
        assert str(root / "github.com") in err

    def test_target_itself_is_a_file(self, monkeypatch, tmp_path, capsys):
        root = tmp_path / "src"
        target = root / "github.com" / "owner" / "repo"
        target.parent.mkdir(parents=True)
        target.write_text("")  # target path exists but is a regular file
        self._run_main(
            monkeypatch,
            ["--src-dir", str(root), "git@github.com:owner/repo.git"],
        )
        self._no_git(monkeypatch)

        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert err.startswith("src-get: error:")
        assert "Traceback" not in err
        assert str(target) in err

    def test_valid_nested_root_still_clones(self, monkeypatch, tmp_path, capsys):
        # Regression: a valid root needing intermediate dirs created still works.
        root = tmp_path / "src"
        self._run_main(
            monkeypatch,
            ["--src-dir", str(root), "git@github.com:owner/repo.git"],
        )
        target = root / "github.com" / "owner" / "repo"
        fake_run = make_fake_run(returncode=0, create_target=target)
        monkeypatch.setattr(subprocess, "run", fake_run)

        main()

        cmd, _ = fake_run.calls[0]
        assert cmd[:2] == ["git", "clone"]
        assert target.parent.is_dir()
        out = capsys.readouterr().out
        assert out.strip().splitlines()[-1] == str(target)
