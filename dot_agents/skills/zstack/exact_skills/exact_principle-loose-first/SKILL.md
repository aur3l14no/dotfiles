---
name: principle-loose-first
description: Apply when setting a threshold, gate, default or mechanism. Start loose and tighten only on evidence.
disable-model-invocation: true
---

# Loose First

Start loose. Tighten only when a measurement or an incident shows the loose version failing.

**Why:** "只要架构上保留了后续增加的可能性，就不要提前去做太死": while the architecture leaves room to add something later, don't fix it early. Hard gates on soft goals and mechanisms built early cost code and review rounds, and seldom pay back.

- A soft goal (a latency, a rate, a nicety) is observed and reported, never a hard gate.
- A default is the simplest thing that works. A mechanism that wins a bench becomes an option, not the default.
- A capability not needed yet gets a hook (a field, a parameter), not an implementation.

**Not covered:** an unexplained failure is not a soft goal; find its cause. A tolerance in a correctness assertion needs a measured basis.
