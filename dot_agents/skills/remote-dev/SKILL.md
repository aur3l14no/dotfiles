---
name: remote-dev
description: Set up and run workflows that edit locally and sync or execute remotely.
---

# Remote Dev

Edit locally; run tests, installs, downloads, simulators, and robot/runtime
commands remotely. Keep large or reusable data in the remote data/cache path.

Read `AGENTS.md` and ignored `AGENTS.local.md`. Keep the latter under 50 lines
and record only machine-specific host/workspace, storage, environment, network,
sudo, and runtime facts.

## Initialize

If connection facts are missing, ask for the remote host, workspace, and
data/cache path. Inspect the remote read-only for everything else; record only
durable facts.

Create an ignored root `justfile.local`, imported by the root `justfile`:

- Keep it to thin machine-specific sync recipes; delegate repository mirroring
  to this skill's `tools/rsync_repo.py`.
- Hard-code the direction from this machine's fixed role: sender uses `push`,
  receiver uses `pull`. Accept only optional `-y`; dry-run otherwise.

## Sync

Run `rsync_repo.py push|pull [-y] REMOTE` locally from the current worktree.
`push` makes local authoritative; `pull` makes remote authoritative without
remote access to local. Use `just sync-remote [-y]` for the machine's fixed
direction and invoke the opposite direction directly.

The selected source may overwrite or delete destination changes. The script
derives paths from Git and `.gitignore`, keeps ignored destination extras and
existing files behind source LFS pointers, and aborts on path blockers. It
mirrors the worktree and staged tree, and sets destination HEAD to the source
commit in detached state. Destination named branch refs and Git configuration
remain unchanged.

## Temporary CLI Migration

- `rsync_repo.py [-y] REMOTE` or `rsync_repo.py [-y] . REMOTE` becomes
  `rsync_repo.py push [-y] REMOTE`.
- `just sync-remote [-y]` is unchanged for existing sender recipes.

Remove this section after the transition window.
