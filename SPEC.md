# git-get Specification

## Overview

`git-get` clones a git repository into a structured directory hierarchy that mirrors the remote URL's host and path components — similar to how Go organizes workspace source trees.

**Example:**

```
git-get git@github.com:jhulten/git-get.git
# → clones to $HOME/src/github.com/jhulten/git-get

git-get https://gitlab.com/myorg/team/subteam/myrepo.git
# → clones to $HOME/src/gitlab.com/myorg/team/subteam/myrepo
```

---

## CLI Interface

```
git-get <url> [--src-dir <path>] [-- <git-flags>]
```

### Positional Arguments

| Argument | Description |
|----------|-------------|
| `url` | The repository URL to clone. Required. Exactly one per invocation. |

### Options

| Flag | Description |
|------|-------------|
| `--src-dir <path>` | Root directory for the source tree. Overrides `$SRC_DIR`. |

### Passthrough

Everything after `--` is forwarded verbatim to `git clone`. Example:

```
git-get https://github.com/owner/repo -- --depth 1 --branch main
```

---

## Root Directory Resolution

The root directory is resolved in order of precedence (highest first):

1. `--src-dir` CLI flag
2. `$SRC_DIR` environment variable
3. Default: `$HOME/src`

---

## URL Parsing

### Supported Formats

| Format | Example |
|--------|---------|
| SSH (scp-style) | `git@github.com:owner/repo.git` |
| SSH (URL) | `ssh://git@github.com/owner/repo.git` |
| HTTPS | `https://github.com/owner/repo.git` |
| HTTPS (no .git) | `https://github.com/owner/repo` |

### Path Extraction

The target directory is constructed as:

```
<root>/<host>/<path-components...>
```

Where `<path-components>` is the full path from the URL, preserving all intermediate segments. This supports deeply nested GitLab group structures.

**Examples:**

| URL | Target Directory |
|-----|-----------------|
| `git@github.com:jhulten/git-get.git` | `<root>/github.com/jhulten/git-get` |
| `https://github.com/jhulten/git-get` | `<root>/github.com/jhulten/git-get` |
| `https://gitlab.com/org/team/sub/repo.git` | `<root>/gitlab.com/org/team/sub/repo` |

### `.git` Suffix

- The `.git` suffix is stripped from the final path component by default.
- If `--bare` is present in the passthrough args (after `--`), the `.git` suffix is **preserved** in the directory name.

---

## Behavior

### New Repository

If the target directory does not exist:

1. Create all intermediate directories as needed.
2. Run `git clone [<git-flags>] <url> <target>`.

### Existing Repository

If the target directory already exists:

1. Run `git fetch` inside the target directory.
2. Run `git pull` inside the target directory.
3. Passthrough args are **not** forwarded for fetch/pull (they are clone-only flags).

### After Clone or Pull

- Always print the absolute path of the repository to stdout on its own line.
- This is the last line of output so shell integration can capture it reliably.

---

## `--bare` Handling

`--bare` is **not** a first-class CLI flag. It is only recognized when it appears in the passthrough (after `--`).

- The tool scans passthrough args for `--bare`.
- If found, the `.git` suffix is kept in the target directory name.
- The full passthrough (including `--bare`) is forwarded to `git clone`.

**Example:**

```
git-get git@github.com:jhulten/git-get.git -- --bare
# → clones to $HOME/src/github.com/jhulten/git-get.git
```

---

## Git Output and Exit Codes

- git's stdout and stderr are streamed directly to the terminal (not buffered or suppressed).
- On git failure, `git-get` exits with the same exit code git returned.
- On success, `git-get` exits with code `0`.

---

## Shell Integration

Because a subprocess cannot change the parent shell's working directory, `git-get` ships shell integration snippets for **bash** and **zsh**.

The integration wraps `git-get` in a shell function that:
1. Runs the `git-get` binary, capturing the final line of output as the repo path.
2. On success, `cd`s to that path.
3. On failure, propagates the exit code without changing directory.

### Installation (bash / zsh)

Add to `~/.bashrc` or `~/.zshrc`:

```sh
git-get() {
  local repo_path
  repo_path=$(command git-get "$@" | tee /dev/stderr | tail -1)
  local exit_code=${PIPESTATUS[0]}
  if [ $exit_code -eq 0 ] && [ -n "$repo_path" ]; then
    cd "$repo_path"
  fi
  return $exit_code
}
```

> **Note:** The shell function shadows the binary. Use `command git-get` to invoke the binary directly.

---

## Future Work (Out of Scope)

- **Short aliases:** `gh:owner/repo` → `git@github.com:owner/repo`, `glab:` → GitLab equivalent.
- **Multiple URLs in one invocation.**
- **Fish shell integration.**
- **`git-get update`** subcommand to fetch/pull all repos under `$SRC_DIR`.

---

## Implementation Notes

- Language: Python ≥ 3.13
- CLI parsing: `argparse` (stdlib only — no external dependencies)
- Build backend: `uv_build`
- Entry point: `git-get` (defined in `[project.scripts]`)
