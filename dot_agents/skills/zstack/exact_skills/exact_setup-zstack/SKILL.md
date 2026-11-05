---
name: setup-zstack
description: "Write or refresh zstack's settings with the user: global and project model, effort and harness choices, and the repo's description of the build and GPU machines its work may use over ssh. Use for /setup-zstack, when a mode finds one of them missing, or when a model or a machine changes."
disable-model-invocation: true
---

# Setup zstack

The modes read global model defaults and project overrides, plus a machines file. Project-local files live in the main checkout's ignored `.local/zstack/`, shared by its worktrees. This skill writes the requested scope with the user. On a re-run, read what exists first and keep the user's choices; only what changed is asked again.

## Models

Global defaults: `~/.agents/zstack-models.md`; project overrides: `.local/zstack/models.md`. Read z-mode's Subagents rules (`../z-mode/SKILL.md`) for format and precedence. The roles are `implementer`, `reviewer` and `reader`. Write only overridden roles in the project file.

1. Check available models and harnesses through the host's tools or provider CLIs. Write only combinations the host can launch.
2. Propose one model per role and two for `reader`, preferring the strongest models and high where supported. By default, readers use different families, as do `reviewer` and `implementer`. Never a fast or priority tier.
3. Show the resolved choices and scope, take the user's changes, and write that scope's file.

If a dotfiles manager deploys the file, change its source and apply it; otherwise the next apply reverts the change.

## Machines: `.local/zstack/machines.md`

The machines this repo's work may use over ssh: build and test hosts for z-mode, GPU machines for r-mode's runs. The file names hosts, accounts and paths, so it stays out of git.

Ask the user only what exploring cannot tell you: which machines, how to connect to each (an ssh alias, or host, user and jump host), and what this repo will use it for. Access is theirs: if a connection fails, stop and say so. Then explore each machine yourself, read-only, and write what an agent needs before it puts work there:

- what it has: CPUs, memory, GPUs and any power cap, the toolchains the work will need;
- how work gets a share: under a scheduler, this account's limits on GPUs, jobs and time, and what preemption does to a job; without one, who else uses it and whether their processes are visible;
- how to read its live use: the commands that worked during setup;
- storage: which tier is fast and which is large, so data a run reads at speed and results it keeps go to different places; where code, environments, data and results go; quotas, automatic cleanup, who else can read each area, and what belongs to someone else. A world-writable area under the default umask leaves new files readable by everyone. `df` on a directory under a project quota reports the quota, not the disk, and behind a RAID controller the rotational flag says nothing about SSD or HDD;
- network: which package indexes, code hosts and model hubs it reaches, since a gap decides where downloads happen;
- the owners' rules and where they live, and the pitfalls you hit while exploring.

With several accounts on one machine, say which one runs work and what the others may not be used for.

What exploring leaves open goes to the user in one batch, each item with your best guess: rules and measurements that disagree, whether a GPU is shared, etiquette such as whom to tell before a large run or how to reserve the whole machine. Etiquette is never guessed.

One section per machine, headed by the name agents will use for it, with the date of the check. The user's answers go in as they gave them. On a re-run, re-measure what can be measured and keep what the user said.

## Project cards

Each mode writes its own card with the user in a new project: z-mode's `.local/zstack/card.md` and r-mode's `research/CARD.md`. When the current project lacks the card for the mode the user is about to start, offer once to write it.
