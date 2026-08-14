"""src-get: clone repositories into a structured directory hierarchy."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse


def parse_url(url: str) -> tuple[str, list[str]]:
    """Parse a git URL and return (host, path_components).

    Supports:
      - SSH scp-style:  git@github.com:owner/repo.git
      - SSH URL:        ssh://git@github.com/owner/repo.git
      - HTTPS:          https://github.com/owner/repo[.git]
    """
    # scp-style SSH: git@host:path/to/repo.git
    if not url.startswith(("http://", "https://", "ssh://")):
        if "://" in url:
            raise ValueError(
                f"Unsupported URL format: {url!r}. "
                "Expected SSH (git@host:path), ssh://, or https:// URL."
            )
        if ":" in url:
            host_part, path_part = url.split(":", 1)
            # host_part may be user@host — extract host
            host = host_part.split("@")[-1]
            if not host:
                raise ValueError(f"Could not determine host from URL: {url!r}")
            components = [p for p in path_part.split("/") if p]
            return host, components
        raise ValueError(
            f"Unsupported URL format: {url!r}. "
            "Expected SSH (git@host:path), ssh://, or https:// URL."
        )

    parsed = urlparse(url)
    host = parsed.hostname or ""
    if not host:
        raise ValueError(f"Could not determine host from URL: {url!r}")
    # strip leading slash and split
    components = [p for p in parsed.path.strip("/").split("/") if p]
    return host, components


def resolve_root(src_dir_flag: str | None) -> Path:
    """Resolve the root source directory from flag > env > default."""
    if src_dir_flag is not None:
        return Path(src_dir_flag).expanduser().resolve()
    env_val = os.environ.get("SRC_DIR")
    if env_val:
        return Path(env_val).expanduser().resolve()
    return Path.home() / "src"


def strip_git_suffix(name: str) -> str:
    if name.endswith(".git"):
        return name[:-4]
    return name


def target_directory(root: Path, host: str, components: list[str], bare: bool) -> Path:
    """Build the target directory path."""
    if not components:
        raise ValueError("Could not determine repository path from URL")
    repo_name = components[-1]
    if not bare:
        repo_name = strip_git_suffix(repo_name)
    path_parts = [host] + components[:-1] + [repo_name]
    return root.joinpath(*path_parts)


def run_git(args: list[str], cwd: Path | None = None) -> int:
    """Run a git command, streaming output to the terminal. Returns exit code."""
    try:
        result = subprocess.run(["git"] + args, cwd=cwd)
        return result.returncode
    except FileNotFoundError:
        print("src-get: error: git not found in PATH", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="src-get",
        description="Clone a git repository into a structured directory hierarchy.",
    )
    parser.add_argument("url", help="Repository URL to clone.")
    parser.add_argument(
        "--src-dir",
        metavar="PATH",
        help="Root directory for the source tree (overrides $SRC_DIR).",
    )
    # Everything after -- is forwarded to git clone
    parser.add_argument(
        "passthrough",
        nargs=argparse.REMAINDER,
        help=argparse.SUPPRESS,
    )

    args = parser.parse_args()

    # Extract passthrough args (strip leading '--' separator if present)
    passthrough: list[str] = args.passthrough
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]

    bare = "--bare" in passthrough

    try:
        host, components = parse_url(args.url)
    except ValueError as exc:
        print(f"src-get: error: {exc}", file=sys.stderr)
        sys.exit(1)

    root = resolve_root(args.src_dir)

    try:
        target = target_directory(root, host, components, bare)
    except ValueError as exc:
        print(f"src-get: error: {exc}", file=sys.stderr)
        sys.exit(1)

    if target.is_dir():
        # Existing repo: fetch then pull
        exit_code = run_git(["fetch"], cwd=target)
        if exit_code != 0:
            sys.exit(exit_code)
        exit_code = run_git(["pull"], cwd=target)
        if exit_code != 0:
            sys.exit(exit_code)
    else:
        # New repo: clone
        target.parent.mkdir(parents=True, exist_ok=True)
        clone_args = ["clone"] + passthrough + [args.url, str(target)]
        exit_code = run_git(clone_args)
        if exit_code != 0:
            sys.exit(exit_code)

    # Always print the repo path as the last line — shell integration depends on this
    print(str(target))
