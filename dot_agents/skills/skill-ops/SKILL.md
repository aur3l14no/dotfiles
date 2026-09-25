---
name: skill-ops
description: Initialize, install, update, remove, or repair skills and their executable dependencies.
---

# Skill Ops

Make skills usable and reproducible without silently accumulating software. These conventions override upstream maintenance instructions. Explain the impact of persistent installation, updates, removal, or repair and obtain user authorization; existing authorization counts. Normal execution using temporary environments or standard caches is allowed.

## Text and executables

Treat a skill as two parts: instructions and executable dependencies. APM manages third-party skill text and bundled files; it does not provision every executable they refer to. Tool and skill versions can differ: verify compatibility rather than assuming they move together.

Choose the simplest usable execution form from what upstream provides:

| Upstream form | Local approach |
| --- | --- |
| Instructions only, or an existing tool/API | No additional executable installation. |
| Bundled script | Run directly with an available runtime; prefer PEP 723 with `uv run` for Python dependencies. Avoid incidental project environment changes. |
| Published Python or npm CLI / SDK | Prefer `uvx` / `uv tool run`, `npm exec` / `npx`, or a task-scoped environment. Establish the actual package, entry point, and compatible version. |
| Standalone binary, application, or source requiring a build | Check for an upstream cache-friendly distribution first; otherwise agree on an explicit managed installation/build and update source. Do not invent a cache mechanism for every tool. |
| System integration: extension, native host, service, OS permissions | Treat as an explicit prerequisite; document setup, location, and update method. A cached CLI does not make its integration ephemeral. |

Prefer direct ephemeral commands in the skill. If upstream's ordinary invocation would leave unmanaged software and the safe invocation becomes unwieldy, maintain a thin chezmoi-owned wrapper with a short command name. Keep its source/version and cache behavior explicit; preserve arguments and exit status, and never silently bootstrap missing runtimes or integrations. Retain useful existing wrapper protections.

Ephemeral means dependencies live in disposable environments or standard caches, not that commands are sandboxed or everything is deleted afterward. Preserve normal authentication, configuration, and task output. Account for installer side effects and runtime downloads separately.

## Special Cases

Both CLIs use `npm-user install -g <package>@<version>` with an explicit compatible version, under `~/.local/opt/npm-global`. Resolve commands from its `bin` directory; a PATH miss alone does not mean uninstalled. APM still owns their skill text.

- `open-browser-use`: Persistent CLI, Chrome extension, and stable native-host registration. Verify the host points to the managed native binary and remains compatible with the extension after updates. SDK dependencies remain task-scoped.
- `open-computer-use`: Persistent CLI and bundled runtime. Preserve macOS permissions and verify them after moving or updating the app; avoid installs tied to a mise Node-version directory.

## Init and update

Resolve executable sources, invocation choices, and difficult prerequisites during the user-attended maintenance session. Tell the user what must be installed or configured and offer a concrete recommendation. Put settled invocation choices into the target documentation; retain only enduring local exceptions as per-skill policy. Wrapper versions and arguments belong in the wrapper.

- Third-party skills: `~/.apm/apm.yml` and `~/.apm/apm.lock.yaml`. Add with positional `apm install -g <package-with-explicit-ref>`; preview with `--dry-run`. Bare install can redeploy all dependencies and erase patches.
- Updates: inspect `apm outdated -g`, preview `apm update -g --dry-run`, then perform the authorized update. Review audit findings; the known Lark hidden-character false positive is not blanket permission to ignore findings.
- Fresh setup: restore chezmoi targets and establish APM and its uv/Python runtime before `apm install -g --frozen`. The APM lock restores skills, not all tool dependencies. Resolve the executable prerequisites above as part of initialization.
- Carry forward still-applicable local execution decisions onto the new upstream text, not the old patched wording. Backups are for rollback and identifying those decisions; restore patched files directly only when recovering an unchanged upstream revision from incidental redeployment. Sync authorized manifest/lockfile changes back to chezmoi. Do not substitute upstream installer scripts or `npx skills add` for APM.

## Delegate adaptation

After installation or update, spawn a sub-agent to load `~/.agents/skills/skill-patcher/SKILL.md`. Supply the affected skill directories and clean upstream source for the resolved revision, settled invocation choices, any per-skill policies, and whether the user requested a full pass. For an explicit patch audit, derive the requested APM-managed scope from the lockfile. Avoid overlapping edits to the same skills.

Wait for the sub-agent's result and read its handoff. Handle dependency or wrapper changes in this attended session, bring necessary decisions to the user, and delegate unfinished adaptation again when resolved. Completion means usable adapted documentation, known executable prerequisites, and outstanding decisions surfaced to the user; an APM command finishing alone is insufficient.

Skill Patcher owns completion-marker-based incremental selection and semantic adaptation. Direct APM commands do not automatically patch skills; Skill Ops is the maintenance entry point. Self-owned skills are maintained in chezmoi sources rather than patched in their deployed copies.

## Sources

Self-owned skills: `~/.nix-config/chezmoi/dot_agents/skills/`. Skill Patcher and its META template live alongside Skill Ops in that source tree; APM manifest/lockfile live under `~/.nix-config/chezmoi/dot_apm/`. Wrappers: `~/.nix-config/chezmoi/dot_local/bin/`. Edit sources and apply specific chezmoi targets; retain only enduring local exceptions as per-skill policy so redeployment can reproduce them.
