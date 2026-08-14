# src-get

Clone a git repository into a structured directory hierarchy that mirrors the
remote URL's host and path — similar to how Go organizes its workspace source
tree.

```
src-get git@github.com:jhulten/src-get.git
# → clones to $HOME/src/github.com/jhulten/src-get

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

`main` requires a reviewed, merged PR (see `protect-main` in the repo's
rulesets), so releases start locally but finish in CI once the version bump
actually lands on `main`.

### 1. Start the release

```sh
mise run release <version>
```

1. Branches from `main` as `release/v<version>`.
2. Bumps the version: `uv version <version>` — updates `pyproject.toml` and
   re-locks `uv.lock`.
3. Runs the test suite and does a sanity build: `uv run pytest`, `uv build`.
4. Commits the version bump and pushes the branch.
5. Opens a PR against `main` with `gh pr create`.

Get the PR reviewed and merged like any other change.

### 2. CI finishes the release automatically

`.github/workflows/finish-release.yml` triggers on any push to `main` that
touches `pyproject.toml` — which a merged release PR always does:

1. **`detect-version`** reads the version at `main`'s tip and checks whether a
   `v<version>` tag already exists. If it does (an unrelated `pyproject.toml`
   change, or this version was already released), the workflow stops here.
2. **`finish-release`** (only for a genuinely new version) builds the package
   fresh from `main`'s actual merged history, tags `v<version>`, pushes the
   tag, and publishes a GitHub release with the built artifacts.
3. **`publish-pypi`** takes the exact artifact `finish-release` built (handed
   off via a workflow artifact, not rebuilt) and publishes it via
   [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/) (OIDC
   — no stored API tokens). This job runs against the `pypi`
   [GitHub environment](https://github.com/jhulten/src-get/settings/environments),
   which requires manual approval on each run before it's allowed to publish.

Releases and tags are never created by pushing directly to `main` — only by
`finish-release` reacting to a merge, which keeps the whole flow compatible
with `main` requiring PRs.

CI separately builds and uploads a dev-versioned artifact
(`<version>.dev0+g<sha>`) as a build artifact on every push to `main`,
independent of this release process — that one never touches PyPI.
