---
name: setup-zstack
description: Write or refresh zstack's settings with the user: this host's model and effort for each role, and the repo's description of the build and GPU machines its work may use over ssh. Use for /setup-zstack, when a mode finds one of them missing, or when a model or a machine changes.
disable-model-invocation: true
---

# Setup zstack

The modes read a models file on this host and a machines file in the repo, and keep no defaults of their own beyond a fallback. This skill writes both with the user. On a re-run, read what exists first and keep the user's choices; only what changed is asked again.

## Models: `~/.agents/zstack-models.md`

A one-line header comment, then one line per role: `role: model-id effort`. The roles are `implementer` and `reviewer` (z-mode), `reader`, `second-reader`, `executor` and `auditor` (r-mode).

1. List the models this host can actually start an agent on: the subagent tool's model options, the host's orchestration capabilities, a provider's CLI. Write only models seen there.
2. Propose one per role: the strongest model at xhigh effort, `reviewer` and `auditor` from a family other than `implementer` and `executor`, `second-reader` from a family other than `reader`. Never a fast or priority tier.
3. Show the table, take the user's changes, and write the whole file.

If a dotfiles manager deploys the file, change its source and apply it; otherwise the next apply reverts the change.

## Machines: `.local/MACHINES.md`

The machines this repo's work may use over ssh: build and test hosts for z-mode, GPU machines for r-mode's runs. The file sits beside the local card in `.local/`, which stays out of git, because it names hosts, accounts and paths.

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

Each mode writes its own card with the user in a new project: z-mode's local card and r-mode's `research/CARD.md`. When the current project lacks the card for the mode the user is about to start, offer once to write it.
