---
name: src-get
description: Clone or update a git repo into a structured local source tree, then work in it. Use when cloning a repo, fetching/updating a repo you already have, or locating where a repo lives on disk.
---

`src-get` clones a repository into `<root>/<host>/<path...>`, mirroring the remote URL (like Go's workspace tree). It is idempotent: if the target already exists it runs `git fetch && git pull` instead of cloning, so the **same command both gets and updates** a repo.

```
src-get <url> [--src-dir <path>] [-- <git-flags>]
```

Root resolves in order: `--src-dir` → `$SRC_DIR` → `$HOME/src`. Anything after `--` forwards verbatim to `git clone` (e.g. `-- --depth 1 --branch main`).

## Getting a repo and working in it

`src-get` cannot change your shell's directory (a child process never can). It instead prints the **absolute repo path as the last line of stdout**; all git output goes to stderr. That split is the contract an agent uses: capture stdout for the path, then `cd` yourself.

```sh
repo=$(command src-get "$URL") && cd "$repo"
```

- `command` bypasses the interactive `cd`-wrapper shell function, which is not loaded in the non-interactive shell you run in. Capture stdout and `cd` yourself regardless — do not assume the wrapper moved you.
- On failure `src-get` exits non-zero and prints nothing to stdout, so the `&& cd` never fires. Let the non-zero status surface.

## Reaching a repo without network

To resolve where a repo *would* live on disk without cloning, build the path directly — `<root>/<host>/<path-without-.git>` — rather than running `src-get`. `src-get` always touches the network (clone, or fetch+pull on an existing checkout).
