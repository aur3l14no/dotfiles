# zstack

A way to lead software and research work through agents: you frame the work and decide, implementer and executor agents write the code and run the experiments, and a reviewer or auditor from another model family checks what is risky. It runs in Claude Code and Codex.

## Use

Start a lead session with the `z-mode` skill for development (`/zstack:z-mode` in Claude Code, `$zstack:z-mode` in Codex) or the `r-mode` skill for research. Every skill is explicit-only, so nothing in zstack loads unless you ask for it. Run `setup-zstack` first, on a new host or in a repo whose work runs on other machines: it writes the models file and the repo's machines file.

z-mode reads two things before it acts:

- the project's `AGENTS.md` and its local card: permissions, the merge gate, the reviewer's route, and the lines added to every brief;
- `~/.agents/zstack-models.md`: the model and effort for each role, one line each.

Both modes read the repo's `.local/MACHINES.md`: the build and GPU machines its work may use over ssh, their limits, storage and etiquette. It names hosts and accounts, so it stays out of git. r-mode also reads the project's `research/CARD.md` and the same models file.

## How the work is split

Work starts at the first level still open:

1. **intent**: what the work is for is not settled. Hypotheses, probes and prototypes; goals that cost too much get dropped.
2. **architect**: a settled intent changes the codebase's shape. Owners, interfaces, types, and what depends on them.
3. **unit**: one issue, one branch, one implementer. The brief carries the intent, the sketch and the spec; the lead gates, reviews when the change is risky, and merges.

The other playbooks are progress, investigate, diagnose, cleanup and skill.

Research follows the same pattern in r-mode: **survey** turns seeds and papers into hypotheses, **design** turns a candidate into a round whose readings are fixed before any data, and a **round** gets one executor and one GPU allocation, then acceptance, a verdict and the record. **close** ends a line. The **compute** skill places runs on shared machines and keeps a ledger of live allocations, so parallel sessions don't collide.

## Layout

```
skills/z-mode/SKILL.md        the development router: playbooks, principles, asking and reporting, subagents
skills/z-mode/playbooks/*.md  one file per kind of request, read by path
skills/r-mode/SKILL.md        the research router; its playbooks reuse z-mode's where they fit
skills/r-mode/playbooks/*.md  progress, survey, design, round, close
skills/<name>/SKILL.md        situational skills (adversarial-review, blast-radius, correct, compute,
                              result-review, research-board, setup-zstack,
                              create- and maintain-verification-skill)
                              and principle-* skills
plugin.json                   manifest on the agent-plugins schema; .claude-plugin/ holds a copy
upstream.json                 what was adapted from other plugins, at which commit, and how
```

Skills stay one level deep because Claude Code finds nothing deeper.

## Changing it

The source is the nix-config repository, `chezmoi/dot_agents/skills/zstack/`. Edit there, run `chezmoi apply`, commit. The rules for what goes in are in `skills/z-mode/playbooks/skill.md`: only what a strong model would not do unprompted, the markdown under 100,000 characters.

Parts are adapted from [pstack](https://github.com/cursor/plugins/tree/main/pstack) (MIT); `upstream.json` lists them.
