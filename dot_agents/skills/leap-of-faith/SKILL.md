---
name: leap-of-faith
description: Use only when explicitly invoked to trim agent instructions to what changes a capable agent's decisions.
---

# Leap of Faith

Assume the agent is capable. For each instruction, ask:

> Would a capable agent still do the right thing without this?

- Yes: delete it.
- No: keep the shortest version.
- Unsure: delete it.

State the goal, facts the agent cannot infer, constraints, and what counts as done. Leave the rest to the agent.

Delete cleanly. Do not leave notes about what was removed. If it matters later, let a future agent rediscover it.

Keep the user's explicit choices.
