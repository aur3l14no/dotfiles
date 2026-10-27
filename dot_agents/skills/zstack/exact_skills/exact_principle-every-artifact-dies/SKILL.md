---
name: principle-every-artifact-dies
description: Apply when creating a file, directory, doc, script or name that outlives the task. Give it a consumer and a death when you create it.
disable-model-invocation: true
---

# Every Artifact Dies

Give everything you create a consumer and a death at the moment you create it.

**Why:** an ignored directory grew to gigabytes of journals, drafts and archives. Merged worktrees held hundreds of GB of build output. A status doc tripled in two days. A working name leaked into the architecture doc, and tracked files cited ignored paths.

- The record is git, the PRs and the issues. Ignored dirs hold caches with a consumer, a few hand-kept facts, and a unit's files that die with the unit.
- Tracked files never reference ignored paths or names you coined.
- A status doc never grows: one line in, one line out.
- When a decision changes, grep every copy of the old one.
- Moving to an archive is not deleting.
