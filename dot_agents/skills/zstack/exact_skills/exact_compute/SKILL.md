---
name: compute
description: Place experiment runs on shared GPU machines. Read live use, keep the ledger of our allocations across projects and sessions, queue, release. Use when a round needs compute, or for "what's free".
disable-model-invocation: true
---

# Compute

The machines are shared with other people and with the user's other sessions. Hold an allocation only while a run uses it.

**Facts.** The repo's `.local/MACHINES.md` describes each machine: access, scheduler, per-user limits, preemption, how to read its live use, storage, network gaps, etiquette, and where the owners' rules live. When it is missing or a machine is new, write the section with the **setup-zstack** skill. Before a large request, check the limits against the owners' rules; they change.

**Look before placing.** Read each candidate machine's live use the way its section says, and the ledger. When a command there no longer works, fix the section. Other people's load counts as much as ours. On a GPU shared without a scheduler, processes in other containers can be invisible while their memory use is not.

**The ledger.** `~/.local/state/zstack/compute.jsonl` holds one JSON line per live allocation of ours, across all repos: the round, machine (by its ssh alias, the same in every repo), GPUs, memory cap, whether it needs the machine alone, queued or running, since, expected end, the session that owns it, and the job or tmux name. It exists so the user's parallel sessions don't collide. A line is deleted when its allocation is released; history goes to the round's STATUS.

**Placing.**
- Under a scheduler, the scheduler is the queue. Submit within its limits; our own rounds share the per-user slots in the order you set. A run longer than the job limit is split into segments that resume from a checkpoint. Where the owners can preempt, every run must resume.
- On a GPU shared without a scheduler, co-run only with a memory cap and only while the load leaves room. A large run follows the machine's etiquette, such as a note to the group: draft it for the user to send.
- A wall-clock comparison needs the machine alone. Check it is quiet before and during the run; a run disturbed by foreign load is provisional and says so.
- The arms of one comparison run on the same machine class.

**Waiting.** When nothing fits, the round stays queued in the ledger. Wake on a scheduled check with backoff, not a loop. If the wait outlasts a day, tell the user what waits and why.

**Release.** At acceptance: no process of ours left on the machine, the ledger line deleted, the GPU-hours used written to the round's STATUS per machine. Hours on different cards are not interchangeable.
