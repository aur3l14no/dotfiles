---
name: adversarial-review
description: One adversarial review round of a z-mode unit by a reviewer of another model family, ending in a decision on each finding and a summary on the PR. Use only for a unit whose change is risky enough to need it.
disable-model-invocation: true
---

# Adversarial review

It slows the whole project down, so it is for changes where a mistake is costly: safety, hardware, real-time or concurrent code, a public interface, a persisted or wire format, or a large diff. A small change, docs, tests or scripts skip it; the gate and your own read of the diff are their review.

**Dispatch.** A fresh reviewer from another model family, through the project's route, on a snapshot of the final head. The prompt gives the intent, the diff, your own suspicions, and the project's forbidden list, which binds the reviewer too. A finding names the input or state that triggers it; a guard, check or validation that no realistic input needs is not a finding. Word it neutrally. If a safety classifier blocks it, rephrase once and resend without asking.

**Triage.** Make the most minimal possible changes to appease the reviewers. Be careful of scope creep and don't be scared to push back. A P1 needs a realistic trigger and how often it fires; an impossible trigger is noted, not acted on. Decide each finding: act, consider, noted, dismissed, or hook (keep a field or a hook for later, build nothing now). Adopting nearly everything means you are not triaging.

**Rounds.** One full round, then verification rounds scoped to the fixes. The same guarantee reopened a third time is an intent or architecture finding, per attack-the-premise: no fourth full round, take it to the user with a recommendation. Only the user can reclassify an open P1 so the PR merges.

**Record.** Post a summary on the PR in the user's language: the findings, the decision on each, what changed. Then delete the round's scratch.
