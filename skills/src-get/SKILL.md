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

`src-get` cannot change your shell's directory (a child process never can). It instead prints the **absolute repo path as the last line of stdout**, then `cd` yourself. Git's own output is *not* redirected, so `git pull`/`git clone` may also write lines to stdout (e.g. `Already up to date.`) — only the *last* line is guaranteed to be the path. Take the last line, never the whole capture:

```sh
out=$(command src-get "$URL") && cd "$(printf '%s\n' "$out" | tail -n1)"
```

- `command` bypasses the interactive `cd`-wrapper shell function, which is not loaded in the non-interactive shell you run in. Capture stdout and `cd` yourself regardless — do not assume the wrapper moved you.
- Keep `src-get` out of a pipe so its exit status survives: capture into `out` first (the `&&` then gates on `src-get`'s own status), and extract the last line separately. On failure it exits non-zero and the `cd` never fires.

## Reaching a repo without network

To resolve where a repo *would* live on disk without cloning, build the path directly — `<root>/<host>/<path...>` — rather than running `src-get`, which always touches the network (clone, or fetch+pull on an existing checkout). The trailing `.git` is stripped **unless** the clone is `--bare`, which keeps it (so a bare clone lands at `<root>/<host>/<path>.git`).
