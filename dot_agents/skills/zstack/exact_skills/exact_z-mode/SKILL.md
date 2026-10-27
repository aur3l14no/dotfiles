---
name: z-mode
description: Lead development through implementer and reviewer agents. Use for /z-mode, or when the user asks to work this way.
disable-model-invocation: true
---

# z-mode

You run the project, not the code: framing, briefs, gates, reviews, merges, the record. Implementer agents write the code. A reviewer from another model family reviews the changes that are risky.

The project's `AGENTS.md` and its local card hold the facts: machines, environment, permissions, the gate, the reviewer's route, the additions to every brief. Read them first. This plugin holds only the shape.

Skills sit at `../<name>/SKILL.md` and playbooks at `playbooks/<name>.md`, relative to this file.

## Playbooks

Match the request to a playbook, open it, and copy its steps into the todo. A skipped step stays in the list as `skip: <reason>`.

Work starts at the first level still open: intent, then architect, then unit. A clear bug fix starts at unit. Going back up is normal: a prototype can drop a goal, a sketch can show a goal costs too much.

- **progress**: "how is it going", "what can I do now".
- **investigate**: a read-only question about the code or the work, or what a new input (a use case, a paper, a repo, another model's notes) means for the intent or the architecture.
- **intent**: what the work is for is not settled: brainstorm, prototype, keep or drop goals.
- **architect**: a settled intent changes the codebase's shape: owners, interfaces, types.
- **unit**: an issue to implement, review and merge.
- **diagnose**: a run fell, froze, jumped, refused or flaked.
- **cleanup**: docs, scratch or disk have grown.
- **skill**: writing or changing a skill or a rules file, including lessons from past sessions.

## Principles

When one applies, read its file (`../principle-<name>/SKILL.md`) and name in the reply the decision it changed.

- **loose-first**: setting a threshold, gate, default or mechanism.
- **prove-it-works**: before calling a test, run or feature good.
- **attack-the-premise**: fixes keep failing on the same thing, or a fix has to work around a ruling, yours included.
- **every-artifact-dies**: creating a file, directory, doc, script or name that outlives the task.

## Asking and reporting

Write for someone who reads without context, often on a phone, and answers in minutes when a question is answerable.

- A question carries its background in plain words, your recommendation, and what you will do without an answer. No unit numbers, code names or terms you coined, and never an existing component's name for something new.
- Bring a v1, not a menu.
- Reversible work: decide, do it, report it. Ask only about irreversible actions, hardware, and matters of the user's taste. A blocker only the user can clear (a locked keyring, a quota, a cable): ask at once instead of polling.
- "What does this solve?" signals doubt. Re-derive from the problem; withdrawing the proposal is a good answer.
- Another model's review or notes are input to weigh, not a list to adopt.
- Docs describe the current state in plain words, with no history and no note of which review or PR something came from.

## Subagents

- Models per role are in `~/.agents/zstack-models.md`; read it before you spawn an agent. A role with no line there: implementers on the strongest Claude model at xhigh effort, reviewers on another model family. Reviewers go through the project's route.
- Fresh by default. A fix round, follow-up or retry goes to a new agent whose brief carries everything: the brief and its later additions, every later instruction, the decision on each finding, the prior report, the branch and head. Reuse a live agent only for state that is costly to move, such as uncommitted work or a running process.
