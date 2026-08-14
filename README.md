# src-get

Clone a git repository into a structured directory hierarchy that mirrors the
remote URL's host and path — similar to how Go organizes its workspace source
tree.

```
src-get git@github.com:jhulten/git-get.git
# → clones to $HOME/src/github.com/jhulten/git-get

src-get https://gitlab.com/myorg/team/subteam/myrepo.git
# → clones to $HOME/src/gitlab.com/myorg/team/subteam/myrepo
```

If the target directory already exists, `src-get` runs `git fetch` and
`git pull` inside it instead of cloning again — so the same command works for
both "get" and "update".

## Install

Requires Python ≥ 3.13. Install with [uv](https://github.com/astral-sh/uv):

```sh
uv tool install .
```

This exposes the `src-get` entry point on your `PATH`.

## Usage

```
src-get <url> [--src-dir <path>] [-- <git-flags>]
```

| Argument | Description |
|----------|-------------|
| `url` | Repository URL to clone. Required. |
| `--src-dir <path>` | Root of the source tree. Overrides `$SRC_DIR`. |

Anything after `--` is forwarded verbatim to `git clone`:

```sh
src-get https://github.com/owner/repo -- --depth 1 --branch main
```

### Root directory resolution

Resolved in order of precedence:

1. `--src-dir` flag
2. `$SRC_DIR` environment variable
3. `$HOME/src` (default)

### Supported URL formats

| Format | Example |
|--------|---------|
| SSH (scp-style) | `git@github.com:owner/repo.git` |
| SSH (URL) | `ssh://git@github.com/owner/repo.git` |
| HTTPS | `https://github.com/owner/repo.git` |
| HTTPS (no `.git`) | `https://github.com/owner/repo` |

The target directory is `<root>/<host>/<path-components...>`, preserving all
intermediate path segments (so nested GitLab groups work). The trailing
`.git` is stripped unless `--bare` is present in the passthrough args, in
which case it's kept.

On success, `src-get` prints the absolute path of the repository as the last
line of output; git's own output streams straight to the terminal.

## Shell integration

A subprocess can't change its parent shell's working directory, so `src-get`
ships a shell function that `cd`s into the repo after a successful clone or
pull. Source it from `~/.bashrc` or `~/.zshrc`:

```sh
source /path/to/src-get/shell/src-get.sh
```

The function shadows the `src-get` binary; use `command src-get` to invoke
the binary directly.

## Development

```sh
uv sync
uv run pytest
```

## Release

Releases are cut manually via a [mise](https://mise.jdx.dev) task — there's no
automated version-bump workflow.

```sh
mise run release <version>
```

This runs the full release sequence in order:

1. Bump the version: `uv version <version>`. Updates `pyproject.toml` and
   re-locks `uv.lock`.
2. Run the test suite: `uv run pytest`
3. Build the package: `uv build`
4. Commit the version bump: `git commit -am "Release v<version>"`
5. Tag and push: `git tag v<version> && git push origin main --tags`
6. Publish a GitHub release with the built artifacts:
   `gh release create v<version> dist/* --generate-notes`

The task aborts if `<version>` is omitted, and each step must succeed before
the next runs (`set -euo pipefail`) — a failed test run or build stops the
release before anything is tagged or pushed.

There's no PyPI publishing step yet — releases ship as GitHub Releases with
attached wheel/sdist files. CI separately builds and uploads a dev-versioned
artifact (`<version>.dev0+g<sha>`) as a build artifact on every push to
`main`, independent of this manual release process.
