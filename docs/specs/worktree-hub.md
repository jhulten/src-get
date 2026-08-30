# src-get Worktree Hub Specification

## Status

Proposed. Extends the core behavior described in [`SPEC.md`](../../SPEC.md).

---

## Overview

Today `src-get <url>` clones a single working checkout to
`<root>/<host>/<path>`. That's ideal for a repo you touch on one branch at a
time, but it fights any workflow with several branches in flight at once:
review branches, long-lived feature work, and — increasingly — parallel
coding agents that each need an isolated tree.

The common fixes are worse than the problem. Re-cloning duplicates the entire
object store. Ad-hoc tooling scatters worktrees into `/tmp`,
`~/.cache/<tool>/<hash>`, and other unpredictable places, so your editor,
`direnv`, and muscle memory all break because the code isn't where the URL
says it should be.

The **worktree hub** layout keeps everything under the one predictable path
`src-get` already derives from the URL. A single bare object store backs any
number of sibling worktrees, no checkout is privileged, and nothing lands
outside `<root>/<host>/<path>`.

```
src-get --worktree git@github.com:jhulten/src-get.git
```

produces:

```
$HOME/src/github.com/jhulten/src-get/     ← the hub (== the usual target path)
├── .bare/                                ← bare clone: the shared object store
├── .git                                  ← file: "gitdir: ./.bare"
└── main/                                 ← worktree for the default branch
```

Adding another branch adds a sibling, never a new clone:

```
$HOME/src/github.com/jhulten/src-get/
├── .bare/
├── .git
├── main/
└── feature-x/                            ← git worktree add, same object store
```

---

## Terminology

| Term | Meaning |
|------|---------|
| **Hub** | The directory `<root>/<host>/<path>` — the container for the bare store and all worktrees. Not itself a checkout. |
| **Bare store** | `<hub>/.bare`, a `--bare` clone holding all objects and refs. |
| **Hub pointer** | `<hub>/.git`, a gitfile containing `gitdir: ./.bare`, so git commands run from the hub root resolve to the bare store. |
| **Worktree** | `<hub>/<branch>`, a working tree checked out from the bare store for one branch. |

A hub is recognized by the presence of both `<hub>/.bare/` (a bare repo) and a
`<hub>/.git` file whose contents point at `./.bare`.

---

## CLI Interface

```
src-get --worktree <url> [--branch <name>] [--src-dir <path>] [-- <git-flags>]
```

### New options

| Flag | Description |
|------|-------------|
| `--worktree`, `-w` | Opt into hub mode. Without it, `src-get` behaves exactly as in `SPEC.md` (single checkout). |
| `--branch <name>`, `-b <name>` | The branch to materialize as a worktree and `cd` into. Defaults to the remote's default branch. |

All existing options (`--src-dir`, `--` passthrough) and the root-directory
resolution rules from `SPEC.md` are unchanged. The hub path is exactly the
target path the core spec already computes — hub mode changes what is created
*at* that path, not *where* it is.

### Opting in via environment

`SRC_GET_WORKTREE=1` makes hub mode the default so plain `src-get <url>`
creates a hub. An explicit `--worktree` on the command line is redundant but
harmless; there is no flag to force single-checkout mode when the env var is
set (out of scope — see Future Work).

### Passthrough

Passthrough args after `--` are forwarded to the underlying `git clone --bare`
that creates the bare store (first invocation only). They are **not** forwarded
to `git worktree add` or to fetches on subsequent invocations. `--bare` in the
passthrough is redundant in hub mode (the store is always bare) and MUST NOT
alter the hub path the way it does in single-checkout mode.

---

## Behavior

Hub mode resolves the hub path, then reconciles four things in order: the bare
store, the default-branch worktree, the requested worktree, and the working
directory to report. Each step is idempotent so the same command works for
"get", "add a branch", and "update".

### 1. Resolve the hub

Compute `<hub> = <root>/<host>/<path>` using the existing resolution and
URL-parsing rules. The `.git` suffix is always stripped from the final path
component in hub mode (the hub is a directory of worktrees, not a `.git`
directory).

### 2. Ensure the bare store

- **Hub does not exist:** create intermediate directories, then
  `git clone --bare [<git-flags>] <url> <hub>/.bare`. Write `<hub>/.git`
  containing `gitdir: ./.bare`. Configure the remote so fetches populate
  remote-tracking refs like a normal clone:

  ```sh
  git -C <hub>/.bare config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
  git -C <hub>/.bare fetch origin
  ```

- **Hub already exists and is a valid hub:** run
  `git -C <hub>/.bare fetch origin` to update refs. Do not clone.

- **Path exists but is *not* a valid hub** (e.g. an ordinary single checkout
  from earlier, non-hub use): refuse with a clear error and a non-zero exit
  code. Do not convert, delete, or clobber it. Migration is out of scope
  (see Future Work).

### 3. Ensure the default-branch worktree

Determine the remote's default branch (resolved from `refs/remotes/origin/HEAD`,
falling back to `git -C <hub>/.bare symbolic-ref` /
`ls-remote --symref origin HEAD`). If its worktree `<hub>/<default>` does not
exist, add it: `git -C <hub>/.bare worktree add <hub>/<default> <default>`.

The default-branch worktree is **always seeded on hub creation**, even when
`--branch` names a different branch. It serves as a stable anchor — new
branches are cut from `origin/HEAD`, and the hub is never left without a
checkout. On an existing hub, this step is a no-op if the worktree is already
present.

### 4. Ensure the requested worktree

Determine the target branch: `--branch` if given, otherwise the default branch
resolved in Step 3. When it equals the default branch, Step 3 already created
it and this step is a no-op.

- **Worktree `<hub>/<branch>` does not exist:**
  - If the branch exists on the remote, add a tracking worktree:
    `git -C <hub>/.bare worktree add <hub>/<branch> <branch>`.
  - If the branch does not exist anywhere, create it from the default branch:
    `git -C <hub>/.bare worktree add -b <branch> <hub>/<branch> origin/HEAD`.
- **Worktree already exists:** leave it in place. Optionally
  `git -C <hub>/<branch> pull --ff-only` when it is on a tracking branch;
  never force or discard local changes.

A branch may be checked out in only one worktree at a time (git enforces this).
If the requested branch is already checked out in a *different* worktree
directory, report that path rather than failing.

### 5. Report the working directory

Print the absolute path of the resolved worktree (`<hub>/<branch>`) as the last
line of stdout — never the hub root, since the hub root is not a checkout. This
preserves the `SPEC.md` contract that stdout carries exactly the directory the
shell integration should `cd` into. Git's own output continues to stream to the
terminal.

---

## Worktree naming

The worktree directory name is the branch name with slashes preserved as
nested directories, matching how the branch reads:

| Branch | Worktree directory |
|--------|--------------------|
| `main` | `<hub>/main` |
| `feature-x` | `<hub>/feature-x` |
| `release/v1.2` | `<hub>/release/v1.2` |

Because `.bare` and `.git` are reserved names at the hub root, a branch literally
named `bare` or `git` is rejected with a clear error.

---

## Interaction with `.gitignore`d per-worktree files

Worktrees share history and objects but **not** untracked, ignored files —
`.env`, `node_modules/`, build caches, and the like exist per worktree and are
not copied when a new worktree is added. `src-get` does not attempt to copy or
symlink them; doing so silently would be surprising and occasionally dangerous
(secrets, machine-specific paths). Documenting this, and any future opt-in
hook, is deferred to Future Work.

---

## Shell integration

The existing `shell/src-get.sh` function needs no change: it captures the last
line of stdout and `cd`s to it. In hub mode that line is the worktree path, so
`src-get --worktree <url>` drops the user directly into the default branch's
working tree, and `src-get -w <url> -b feature-x` drops them into that branch's
tree — creating both the hub and the worktree first if needed.

---

## Examples

```sh
# First get: bare store + default-branch worktree, cd into it.
src-get -w git@github.com:jhulten/src-get.git
# → $HOME/src/github.com/jhulten/src-get/main

# On a fresh hub, the default branch is still seeded alongside the request.
src-get -w git@github.com:jhulten/src-get.git -b feature-x
# → creates both main/ and feature-x/, cd into:
# → $HOME/src/github.com/jhulten/src-get/feature-x

# Later, add another feature branch worktree beside them, cd into it.
src-get -w git@github.com:jhulten/src-get.git -b feature-y
# → $HOME/src/github.com/jhulten/src-get/feature-y

# Re-run to fetch refs and land back in an existing worktree.
src-get -w git@github.com:jhulten/src-get.git -b feature-x
# → $HOME/src/github.com/jhulten/src-get/feature-x  (no re-clone)

# Nested GitLab groups work identically.
src-get -w https://gitlab.com/org/team/sub/repo.git
# → $HOME/src/gitlab.com/org/team/sub/repo/main
```

---

## Exit codes

Unchanged from `SPEC.md`: git's exit code propagates on failure; `0` on
success. Refusing to operate on a non-hub path at the target location is a
`src-get`-level error and exits non-zero without invoking git.

---

## Future Work (Out of Scope)

- **`src-get worktree rm <branch>`** and pruning (`git worktree remove` /
  `prune`) from within a hub.
- **Migration** of an existing single checkout into a hub in place.
- **Per-worktree file provisioning:** an opt-in hook or config to symlink or
  copy `.env`-style files into new worktrees.
- **Minimal mode:** a flag/config to skip seeding the default-branch worktree
  and create only the requested `--branch`, for hubs where the default branch
  is never worked on directly.
- **`--no-worktree`** to force single-checkout mode when `SRC_GET_WORKTREE=1`.
- **Listing** all worktrees in a hub (`git worktree list` passthrough).
- **`git worktree repair`** integration after a hub directory is moved.

---

## Implementation Notes

- Reuses `parse_url`, `resolve_root`, and target-path construction from the
  core implementation; hub mode diverges only after the target path is known.
- The `<hub>/.git` pointer is written as the literal text `gitdir: ./.bare`
  (relative), so the hub remains portable if the whole tree is moved and
  `git worktree repair` is run.
- Default-branch detection should not assume `main` or `master`; resolve it
  from the remote.
