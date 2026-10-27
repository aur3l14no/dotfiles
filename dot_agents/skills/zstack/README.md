# zstack

A way to lead software work through agents: you frame the work and decide, implementer agents write the code, a reviewer from another model family checks the risky changes. It runs in Claude Code and Codex.

## Use

Start a lead session with the `z-mode` skill: `/zstack:z-mode` in Claude Code, `$zstack:z-mode` in Codex. Every skill is explicit-only, so nothing in zstack loads unless you ask for it.

z-mode reads two things before it acts:

- the project's `AGENTS.md` and its local card: machines, permissions, the merge gate, the reviewer's route, and the lines added to every brief;
- `~/.agents/zstack-models.md`: the model and effort for each role, one line each.

## How the work is split

Work starts at the first level still open:

1. **intent**: what the work is for is not settled. Hypotheses, probes and prototypes; goals that cost too much get dropped.
2. **architect**: a settled intent changes the codebase's shape. Owners, interfaces, types, and what depends on them.
3. **unit**: one issue, one branch, one implementer. The brief carries the intent, the sketch and the spec; the lead gates, reviews when the change is risky, and merges.

The other playbooks are progress, investigate, diagnose, cleanup and skill.

## Layout

```
skills/z-mode/SKILL.md        the router: playbooks, principles, asking and reporting, subagents
skills/z-mode/playbooks/*.md  one file per kind of request, read by path
skills/<name>/SKILL.md        situational skills (adversarial-review, blast-radius, correct,
                              create- and maintain-verification-skill) and principle-* skills
plugin.json                   manifest on the agent-plugins schema; .claude-plugin/ holds a copy
upstream.json                 what was adapted from other plugins, at which commit, and how
```

Skills stay one level deep because Claude Code finds nothing deeper.

## Changing it

The source is the nix-config repository, `chezmoi/dot_agents/skills/zstack/`. Edit there, run `chezmoi apply`, commit. The rules for what goes in are in `skills/z-mode/playbooks/skill.md`: only what a strong model would not do unprompted, the markdown under 60,000 characters.

Parts are adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT); `upstream.json` lists them.
