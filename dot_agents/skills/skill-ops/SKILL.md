---
name: skill-ops
description: Initialize, install, update, remove, or repair skills and their executable dependencies.
---

# Skill Ops

These local maintenance conventions override upstream maintenance instructions. Persistent changes need user authorization; existing authorization covering the work is sufficient. Settled commands using temporary environments or standard caches need no additional installation approval.

All skills live in `~/.nix-config/chezmoi/dot_agents/skills/`: edit the source and apply the specific chezmoi target. Third-party skills are vendored there as `exact_<name>/`, already adapted; `.upstream.toml` beside them records their upstream. Executable dependencies are managed separately.

Keep shared skills in `~/.agents/skills` and both clients’ private skill directories independent. Codex reads shared skills directly; `uv run ~/.agents/skills/skill-ops/scripts/sync_skill_links.py` links them individually into `~/.claude/skills`, including skills-directory plugins (a `.claude-plugin/plugin.json` in place of a `SKILL.md`). Run it after adding or removing skills; a full chezmoi apply also runs it.

## Executables

Prefer `uvx` / `uv tool run` for published Python tools, PEP 723 / `uv run` for scripts, and `npm exec` / `npx` for npm tools. Verify the package, entry point, and compatible version, then record the invocation in the adapted skill.

Use a thin chezmoi-owned wrapper when direct invocation becomes unwieldy. Wrappers live in `~/.nix-config/chezmoi/dot_local/bin/`; keep their version, arguments, and cache behavior there, preserving caller arguments, exit status, and existing protections.

Agree on managed installations when ephemeral execution is impractical. Runtimes, extensions, native hosts, services, and OS permissions remain explicit prerequisites even when the CLI is cached. Bring unresolved setup choices to the user.

## Third-party skills

Use `uv run ~/.agents/skills/skill-ops/scripts/skill_upstream.py <command>`. `status` compares each vendored skill with its upstream at the recorded commit; `diff <skill>` shows the local adaptation. Preview updates with `update --dry-run`.

- Add: put the repo, an explicit ref and the skill path in `.upstream.toml`, then `update`. The skill arrives as clean upstream.
- Update: `update` moves range and branch refs to the newest upstream; a pinned ref moves only when edited, and the dry run says when upstream has passed it. Naming a skill updates its whole source.
- Remove: drop it from the manifest and delete its vendored directory; chezmoi leaves `~/.agents/skills/<name>` on each host, so remove that too. Clean up obsolete skill-specific wrappers, rules, and registrations. Remove executable dependencies only when authorized and no longer used elsewhere; preserve credentials and user output.
- Fresh setup and other hosts: `chezmoi apply` deploys every skill. Executable prerequisites still need separate setup.

Review invisible characters the script reports in incoming upstream text. `links to missing` names skills a vendored skill refers to but that are not installed.

## Adaptation

`update` merges local adaptations onto new upstream three-way and, like git, leaves conflicts as markers in the vendored source. Nothing deploys until applied.

1. Delegate new skills, merged upstream deltas, and conflicts to a sub-agent with `~/.agents/skills/skill-ops/ADAPTATION.md` as its brief. Supply the vendored directories, the `update` output, settled invocation choices, local constraints, and any full-pass request. Unchanged upstream needs no delegation; a clean merge still needs its upstream delta reviewed.
2. Read the handoff and resolve dependency or wrapper decisions. Commit and apply only completed adaptations; `status` should show no conflicts and nothing unapplied. Delegate unfinished work again when ready.

For an explicit patch audit, derive the requested scope from the manifest. Report unresolved prerequisites or decisions rather than treating a successful command as completion.
