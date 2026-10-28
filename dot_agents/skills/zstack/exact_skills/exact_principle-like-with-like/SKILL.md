---
name: principle-like-with-like
description: Apply before comparing arms, runs or numbers from different rounds. Match the protocol, or name the difference and what it can explain.
disable-model-invocation: true
---

# Like With Like

A comparison answers its question only when everything except the variable under test matches.

**Why:** in one project, an evaluation cadence that differed between arms changed the training itself, because evaluation reset environments and sampling priorities. Wall-clock numbers taken on a GPU shared with other jobs were off by several times. Two runs of one configuration diverged by 5% from GPU nondeterminism alone.

- Pick the axis before running. Equal samples, equal wall-clock and equal training time answer different questions; report the chosen one, and the others as descriptive.
- Whatever runs inside the training loop (evaluation, logging, checkpointing) is part of the algorithm. Keep it identical across arms.
- Know the noise before calling a difference real: rerun one configuration, or evaluate one checkpoint repeatedly. A difference inside the noise is a tie.
- A number from an earlier round is comparable only if its protocol, code and machine class match. Otherwise rerun the baseline, or say why not.
