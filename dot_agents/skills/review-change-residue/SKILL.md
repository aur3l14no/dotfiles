---
name: review-change-residue
description: Use only when explicitly invoked by the user to review a change for residue from an abandoned attempt.
---

# Review Change Residue

Review one change at a time, and judge the change itself rather than anyone's summary of it.
The single question: would this belong if the final version had been written directly, without
the abandoned attempt?

The meme: asked for tomato scrambled eggs, the agent adds Dongpo pork; corrected, it serves
"tomato scrambled eggs (no Dongpo pork)", explains the omission, and adds pork detectors.

Report content that survives only because of that attempt: corrections of it, explanations of
why it was wrong, guards or tests proving it is gone, labels marking the result as a
correction, instructions about discarded artifacts.

Keep what would still be needed if the version had been written directly — constraints,
regression tests, and explanations with an independent purpose. Deleting a mistake is not a
new requirement: delete residue rather than rewording it.

Do not go looking for other kinds of problems (factual errors, numeric inconsistencies,
wording, file references, commit-message problems) — that is not what this pass is for. If you
notice one in passing, list it separately under "Outside this pass", one line each.

Report each finding once, with its location and one sentence of reason, or "No findings."
