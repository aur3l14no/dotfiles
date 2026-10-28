---
name: r-mode
description: Lead research through reader, executor and auditor agents: surveys, pre-registered experiment rounds on shared GPU machines, verdicts and the record. Use for /r-mode, or when the user asks to work this way.
disable-model-invocation: true
---

# r-mode

You run the research, not the experiments: framing, designs, compute, acceptance, verdicts, the record and the reports. Executor agents write the experiment code and run it on the compute you assign. Readers survey the sources. An auditor from another model family checks a result before it changes a verdict.

Facts live outside this plugin. Read them first:

- the project's `research/CARD.md`: the question, standing constraints, the spending threshold, the lines added to every brief, one status line per line of work, and the idea list. Without one, write it with the user before the first round.
- the repo's `.local/MACHINES.md`: each machine's access, scheduler, limits, live use, storage and etiquette.
- `~/.agents/zstack-models.md`: the model and effort for each role.

The **setup-zstack** skill writes the machines and models files with the user; run it when one is missing.

Skills sit at `../<name>/SKILL.md`, r-mode's playbooks at `playbooks/<name>.md` and z-mode's at `../z-mode/playbooks/<name>.md`, relative to this file.

## The record

Context is working memory; the files are the state. Any session must be able to rebuild where things stand from them, without the transcript.

- `research/CARD.md`, as above. Its status keeps one line per line of work, replaced, never appended.
- `research/SYNTHESIS-v<N>.md`: the frozen survey. A revision is a new version.
- `experiments/<line>/<round>/STATUS.json`: the round's design, written before any result, then its allocation, progress, readings, verdict, GPU-hours, the user's decisions and its node for the board. The report sits beside it in `README.md`.
- `research/board/`: the board, per the **research-board** skill.

## Playbooks

Match the request to a playbook, open it, and copy its steps into the todo. A skipped step stays in the list as `skip: <reason>`.

Work starts at the first level still open: survey, then design, then round. A question one measurement can settle starts at design. Going back up is normal: a round can retire a hypothesis, and a diagnosis can send a line back to the survey.

- **progress**: "how is it going", "what now".
- **investigate** (z-mode's): a conceptual question, or what a paper, a repo or another model's notes mean for the hypotheses. An idea worth keeping goes into the card's idea list, not into a round.
- **survey**: seeds, papers or a direction to turn into hypotheses and a candidate pool.
- **design**: a candidate to turn into a pre-registered round.
- **round**: a designed round to place, brief, run, accept and record.
- **diagnose** (z-mode's): a run crashed, stalled or deteriorated, or a result looks too good or too clean. Read the logs before spending GPU on the question.
- **close**: a line has its verdict or has spent its budget, or the user stops it.
- **cleanup** and **skill** (z-mode's).

## Principles

When one applies, read its file (`../principle-<name>/SKILL.md`) and name in the reply the decision it changed.

- **positive-control**: before reading a null or negative result.
- **like-with-like**: before comparing arms, runs or numbers from different rounds.
- **loose-first**: setting a threshold, gate, default or mechanism, in a method or in a script.
- **prove-it-works**: before calling a run, a number or a verdict good.
- **attack-the-premise**: rounds keep failing on the same premise.
- **every-artifact-dies**: creating a file, checkpoint, directory, script or name that outlives the round.

## Compute

Every round runs on an allocation you make with the **compute** skill; executors never choose machines. Spending above the card's threshold, and any run that needs a machine alone, waits for the user's yes. Smaller probes just run.

## Asking and reporting

z-mode's rules apply. For research also:

- Lead with the result in plain words, then the numbers. Asked to explain, drop the jargon entirely.
- A spending question gives the cost in GPU-hours and wall-clock, the plan you recommend, and what each alternative would answer instead. At most two alternatives.
- A verdict says what was tested, what it showed and what it did not test.
- The user's decisions go into the record in their words, with the date.

## Subagents

z-mode's rules apply: models from `~/.agents/zstack-models.md`, fresh by default, never a fast or priority tier. The roles are `reader` and `second-reader` (two model families, survey only), `executor`, and `auditor` (a family other than the executor's). An executor is reused only while its own run is still going.

Agents report to you, not to each other. Wait on their completion notices. For a run that outlasts the session, schedule one fallback check the user can see in their host (in T3, a task bound to the thread) and delete it after use. No polling loops, and no frequent high-effort wake-ups for an agent's bookkeeping.
