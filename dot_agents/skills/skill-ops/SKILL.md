---
name: skill-ops
description: Initialize, install, update, remove, or repair skills and their executable dependencies.
---

# Skill Ops

These local maintenance conventions override upstream maintenance instructions. Persistent changes need user authorization; existing authorization covering the work is sufficient. Settled commands using temporary environments or standard caches need no additional installation approval.

Self-owned skills live in `~/.nix-config/chezmoi/dot_agents/skills/`: edit the source and apply the specific chezmoi target. Use APM for third-party skill text and bundled files; executable dependencies are managed separately.

Keep shared skills in `~/.agents/skills` and both clients’ private skill directories independent. Codex reads shared skills directly; `uv run ~/.agents/skills/skill-ops/scripts/sync_skill_links.py` links them individually into `~/.claude/skills`. Run it after adding or removing skills; a full chezmoi apply also runs it.

## Executables

Prefer `uvx` / `uv tool run` for published Python tools, PEP 723 / `uv run` for scripts, and `npm exec` / `npx` for npm tools. Verify the package, entry point, and compatible version, then record the invocation in the adapted skill.

Use a thin chezmoi-owned wrapper when direct invocation becomes unwieldy. Wrappers live in `~/.nix-config/chezmoi/dot_local/bin/`; keep their version, arguments, and cache behavior there, preserving caller arguments, exit status, and existing protections.

Agree on managed installations when ephemeral execution is impractical. Runtimes, extensions, native hosts, services, and OS permissions remain explicit prerequisites even when the CLI is cached. Bring unresolved setup choices to the user.

## APM

Before changing an existing deployment, run the patch helper's `status` and investigate `uncaptured` edits. Preview installs, updates, and removals with `--dry-run`; review audit findings.

- Add: `apm install -g <package-with-explicit-ref>`.
- Update: inspect `apm outdated -g`, then `apm update -g`.
- Fresh setup: restore chezmoi targets, establish APM and its uv/Python runtime, then `apm install -g --frozen`. Executable prerequisites still need separate setup.
- Other hosts: before installing from a lock written elsewhere, bring the host's APM to the version that wrote it; older APM scans and rewrites the lock differently.
- Remove: `apm uninstall -g <package>`. Clean up its orphaned patches and obsolete skill-specific wrappers, rules, and registrations. Remove executable dependencies only when authorized and no longer used elsewhere; preserve credentials and user output.

APM can redeploy files and erase adaptations. After installation or update, follow the adaptation workflow below. Sync manifest/lockfile changes with `chezmoi re-add ~/.apm/apm.yml ~/.apm/apm.lock.yaml`.

## Adaptation

Use `uv run ~/.agents/skills/skill-ops/scripts/skill_patches.py <command>`. Patches live in `~/.nix-config/chezmoi/dot_apm/patches/<skill>/` and are not deployed.

1. `apply` replays patches or merges them onto changed upstream. It refuses unexpected deployment edits; conflicts leave the deployment untouched and produce a marked work directory.
2. Delegate unreviewed skills, merged upstream deltas, and conflicts to a sub-agent using `~/.agents/skills/skill-patcher/SKILL.md`. Supply affected directories, clean locked upstream, settled invocation choices, local constraints, and any full-pass request; include old patches for conflicts. Recorded skills with unchanged upstream need no delegation. Merged upstream still needs review even if `status` says `captured`.
3. Read the handoff, resolve dependency or wrapper decisions, and `capture <skill>...` only completed adaptations, including those needing no changes. Delegate unfinished work again when ready, then confirm with `status`.

For an explicit patch audit, derive the requested scope from the lockfile. Report unresolved prerequisites or decisions rather than treating a successful APM command as completion.
