---
name: remote-dev
description: Use for local-edit, remote-run workflows involving AGENTS.local.md, SSH, rsync, remote initialization, sudo, storage, proxies, or remote commands.
---

# Remote Dev

Agent guide for repos edited locally and run remotely.

## Read First

- `AGENTS.md`, then ignored `AGENTS.local.md` if present.
- Development-environment docs named by `AGENTS.md`.
- Env files only for needed variables; never print secrets.

## Private Files

- `AGENTS.local.md`: SSH alias/host, remote workspace, data/cache path, proxy,
  and operator notes. Must be kept <50 lines.
- Env files: development variables such as `UV_CACHE_DIR` and `VENV_*`.

Keep these git-ignored; they are machine-private, not contributor docs.

## Roles

- Local: edit, inspect, and do very light work such as building or serving docs.
- Remote: run tests, simulators, heavy installs, downloads, and robot/runtime
  commands.
- Put large or reusable files under the agreed remote data/cache path, not in
  source, unless the project explicitly tracks them.

## Initialize

If facts are missing, ask for the remote host, remote workspace, data/cache
path, proxy endpoint if downloads are blocked, and whether sudo is needed.

After getting enough connection facts, inspect the remote non-destructively
before asking for details the host can answer. Stop when this checklist is
filled:

- Host/workspace: SSH alias or host, remote workspace, and data/cache path.
- System: OS/arch, CPU, GPU, driver/CUDA when relevant, and usable storage.
- Project env: env file path, required vars, and venv roles.
- Constraints: proxy for GitHub/Hugging Face if needed, sudo needs, and any
  simulator/robot access required by the task.

Record durable facts only.

After initialization, provide a root `justfile.local` and reference it from the
root `justfile`. This file is VCS-ignored and dedicated to remote sync.

- It contains exactly one recipe, `sync-remote`; no other recipe is allowed.
- It is under 10 lines and under 500 total characters.
- `sync-remote` dry-runs unless invoked with `-y`; only `-y` may perform a real
  sync.
- Use `tools/rsync_repo.py` from this skill directory for Git worktree syncs.
  Do not hand-write rsync exclude/delete recipes.
- `rsync_repo.py` derives source files and deletion candidates from Git plus
  `.gitignore`, keeps ignored destination extras, and deletes non-ignored extras
  only after a successful `-y` transfer.
- A local `filter=lfs` pointer is not transferred: its existing destination
  file or symlink is preserved. A missing destination path or any file/directory
  path blocker stops the sync.

## Sync And Run

- Local source is authoritative; remote source is an execution copy.
- Remote source changes are not protected and may be overwritten or deleted.
- Before remote runs, sync through `just sync-remote` using the
  `justfile.local` contract above.

Branch switching is ordinary local Git; no workspace slots, manifests, or sync
sessions.
