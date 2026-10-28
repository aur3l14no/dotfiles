# Round

One round, one executor, one allocation.

1. Place it with the **compute** skill and write the allocation into the STATUS file. Above the card's threshold, or when it needs a machine alone, ask first.
2. Write the brief below. Check its facts about the machines and the code before sending, and mark what you could not check.
3. Launch the executor. Its first act is a dry run or a short preflight that prints the effective configuration; compare it with the design before the full run starts.
4. While it runs: answer its questions and keep the STATUS current at milestones. A protocol change mid-round is a decision, written into the STATUS with its reason before the results it affects.
5. Accept: recompute the readings from the raw outputs yourself, not from the report or its plots. Check that no process of ours is left on the machine, release the allocation, delete the wake-ups.
6. Verdict by the pre-registered readings. A result that changes a line's verdict or will be cited goes through the **result-review** skill first. A number outside the readings is reported as descriptive, not as a pass.
7. Record: the README (what ran, the numbers, the verdict, deviations, GPU-hours), the STATUS node for the board, the card's status line. Refresh the board with the **research-board** skill.
8. Report per Asking and reporting, with the next step and its cost.

## The brief

The executor cannot ask the user, and a run is costly to redo, so the brief is the product. A field you cannot fill is a round you have not designed yet.

```
GOAL         one sentence: what this round decides
QUESTION     the hypotheses with their pre-registered readings, verbatim from the STATUS
ARMS         each arm and control, in run order
PROTOCOL     what must match across arms (seed, data, evaluation cadence, machine alone or shared) and the
             comparison that answers the question
SCOPE        repo, branch and head; the paths it may change; frozen code and why
COMPUTE      the allocation: machine, GPUs, memory cap, how to submit, wall-clock and GPU-hour budget, how the run
             resumes after preemption
CONTEXT      the design, the earlier rounds' reports in full, the synthesis sections it rests on
FACTS        verified (and how) / unverified (marked)
MECHANISMS   the only mechanisms the method may contain; a missing one is proposed in the report, not added
STOP         the partial result or spend that ends the round early, and what to hand back then. Any other
             problem: it takes the most reasonable low-risk reading, records it as a deviation, and keeps going
FORBIDDEN    other machines or more GPUs than allocated; bypassing the scheduler; secrets in files or logs; fast or
             priority tiers; asserts, gates or checks the brief did not ask for; hedging boilerplate in the report
REPORT       status, commits, what ran (configs, seeds), raw output paths, each reading with its number,
             deviations, GPU-hours used, what it did not run, open questions
PROJECT      the card's brief additions, verbatim
```

A follow-up round goes to a fresh executor whose brief carries the earlier brief, its report, the decisions since, and the branch and head.
