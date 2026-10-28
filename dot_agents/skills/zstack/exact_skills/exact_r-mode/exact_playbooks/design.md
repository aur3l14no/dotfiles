# Design

For a candidate that should become a round. The output is the round's STATUS file, written before any result exists.

1. Ask whether a direct measurement on what already exists settles it: a checkpoint, a log, a minutes-long probe. If so, design that instead of a training round.
2. Write each hypothesis with its reading: the number, how it is computed, and the values that confirm it, kill it or leave it open.
3. Arms and controls: the control that would explain the effect away (a matched baseline, a detached gradient, an oracle input), and, per positive-control, the check that the measurement can see the effect at all.
4. Protocol, per like-with-like: what must match across arms, and which comparison answers the question (equal samples, equal wall-clock or equal training time).
5. The method carries only the mechanisms the hypothesis needs, each one listed. Anything else the executor proposes in its report instead of adding it.
6. The compute request: GPUs, memory, hours, GPU-hours, whether it needs the machine alone, whether it can resume. The stop-loss: the partial result or spend that ends the round early.
7. Size it: the smallest round that can move a verdict. The bigger version is a named follow-up with its cost.
