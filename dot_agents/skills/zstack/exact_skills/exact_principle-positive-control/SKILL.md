---
name: principle-positive-control
description: Apply before reading a null or negative result. Show that the measurement could have seen the effect before concluding there is none.
disable-model-invocation: true
---

# Positive Control

A null result means something only if the same measurement shows the effect where it is known to exist.

**Why:** three first rounds in one project nearly ended as false negatives. A stiffness test dragged the whole robot instead of loading the hand. A model-gradient term reached 0.6% of the update and could not have moved anything. A health gate passed a world model no better than predicting no change.

- Before the run, name the case where the effect must show (an oracle input, a known-good checkpoint, a dose large enough to matter, a synthetic signal) and run it first or alongside.
- Before the verdict, check the dose the run actually delivered (gradient share, edit size, accepted steps), not the dose it was configured with.
- A null without a positive control is reported as "not measured". The next round fixes the probe before it tests the idea again.
