---
name: skill-patcher
description: Adapt installed skill documentation to local execution policy, usually delegated by skill-ops.
---

# Skill Patcher

Adapt the skill bundles supplied by the parent agent, preserving their useful capabilities. Work on their documentation only; implementation code, executables, unrelated skills, and lockfiles are outside scope. Apply any supplied per-skill policies and settled execution choices.

## Scope

Process exactly the skills the parent supplies; Skill Ops' patch store, not anything in the documents, records which skills are complete. A `local-policy:start/end` block is runtime policy for the skill, not a completion marker. Report malformed or duplicate policy blocks. For an explicitly requested full pass, redo the supplied skills from clean upstream.

## Adaptation

For each selected skill, start from clean upstream documentation at the APM-locked revision, including an explicit full pass. Use the fresh APM deployment or its matching unmodified package source; if unavailable, report the missing base to the parent. Old patched documents may help identify local requirements, but are not the editing base: reapply still-relevant decisions to the new text rather than restoring old documents and adding selected upstream changes.

Two exceptions come from Skill Ops' patch replay. For a cleanly merged skill, edit the deployed merge and review only the supplied upstream delta for new install, update, or global-environment instructions. For a conflict, resolve the marked merge in the supplied work dir against the new upstream, using the old patch to understand the local decision. Write the result to the deployed skill and leave no conflict markers.

Prefer ephemeral execution: uvx / uv tool run for published Python tools, PEP 723 / uv run for scripts, and npm exec / npx for npm tools. Verify package, entry point, compatible version, and effects. Preserve approved wrappers and existing system integrations. Rewrite commands, examples, and related explanations consistently; do not guess replacements or silently provision missing runtimes.

Remove persistent installation, update, removal, and repair recipes; route maintenance to `~/.agents/skills/skill-ops/SKILL.md`. Keeping an installer behind an authorization reminder is insufficient. Preserve normal operation, authentication, configuration, diagnostics, task outputs, and temporary environments or standard caches. Cache execution does not make extra runtimes, native hosts, extensions, or background services ephemeral.

If adaptation needs a dependency decision or an out-of-scope code/wrapper change, explain it to the parent agent with a concrete suggestion. Do not wait for user input, install tools, or exercise authenticated business operations while patching. The resulting documentation must allow package resolution through settled ephemeral commands without renewed approval. Missing system-level prerequisites (runtimes, native hosts, extensions, services, or OS permissions) and persistent installation or repair decisions require stopping the affected operation, explaining the missing prerequisite, and suggesting options. Follow `skill-ops`; existing authorization counts, and only unresolved decisions require waiting for the user.

Review the result against that clean upstream base: differences should implement current local adaptation while retaining upstream capabilities and corrections. When the skill needs the [local policy block](META.md), place it near the beginning of `SKILL.md`, after frontmatter and title, exactly once. Keep frontmatter valid. Report each skill as complete or unfinished; the parent records only completed skills. A documented but uninstalled prerequisite may still need user attention even when adaptation is complete.

Return a concise handoff directly to the parent agent: changes, skipped or unfinished skills, new dependencies or decisions, and suggested next steps. Clearly state when nothing remains outstanding.
