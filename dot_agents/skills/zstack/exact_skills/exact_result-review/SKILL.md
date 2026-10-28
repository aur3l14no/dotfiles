---
name: result-review
description: One review of an experiment result by an auditor of another model family, before the result changes a verdict or gets cited, ending in a decision on each finding. Use only for results that matter that much.
disable-model-invocation: true
---

# Result review

For a result that would change a line's verdict, close a line, or be cited outside the project. Routine rounds skip it; your own recomputation from the raw outputs is their review.

**Dispatch.** A fresh auditor from a family other than the executor's. Give it the pre-registered readings, the design, read access to the raw outputs and to the code at the round's head, the executor's report, and your own suspicions. Ask it to recompute the readings from the raw outputs, check that the protocol matched across arms, and look for whatever else would produce the same numbers: a confound, a leak, a mismatched control, a metric artifact, seed or GPU nondeterminism. Word it neutrally. It says first whether the verdict stands, then gives at most seven findings, each with the check that would settle it.

**Triage.** Decide each finding: act, consider, noted or dismissed. A finding a cheap check can settle gets the check, not an argument. A finding that needs a new round is a design question for the user, with its cost. Adopting nearly every finding means you are not triaging.

**Record.** In the round's README: the findings, the decision on each, and whether the verdict changed.
