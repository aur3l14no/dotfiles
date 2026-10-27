# Unit

One issue, one branch, one worktree, one implementer.

1. Write the brief below. GOAL is the settled intent; CONTEXT carries the architecture sketch and what depends on it; ACCEPTANCE and VERIFY are the spec, the tests that pin what the code does. Check its facts about the environment before sending, and mark what you could not check.
2. Launch the implementer. It runs only the tests its change touches.
3. On the implementer's report, push and open the PR: what the prototype kept and dropped, one or two sentences on what the change touches and why that is safe, `Closes #N`.
4. Run the project's full gate yourself, once, on the final head.
5. If the change is risky by the **adversarial-review** skill's measure, review it with that skill. A smaller diff you don't fully trust gets the **blast-radius** skill instead. Otherwise the gate and your read of the diff are the review. While a review runs, brief the next unit and start it off main unless it touches the same files. Builds still take turns under the project's load rule.
6. Send the fix round to a fresh agent, with a fix-round brief. A fix round changes no behavior the user relies on. If a fix would, ask the user first and say in plain terms what they would lose.
7. A fix that must cross a freeze or contradict the brief comes back to you. Re-decide the ruling per attack-the-premise instead of letting the fix copy around it.
8. Merge as soon as the project's merge rule allows. Don't stack new units on an unapproved base.
9. Close: delete the unit's brief and review scratch, fast-forward local main, remove the worktree, and replace one line of the status doc.

## The brief

The implementer cannot ask you questions, so the brief is the product. A field you cannot fill is a unit you have not scoped yet.

```
GOAL         one sentence: the outcome, executable by a stranger with no chat access
SCOPE        its worktree's absolute path, branch and head: the only place it works. Paths it may write and
             may not; each frozen path with why. A frozen path that lacks something stops it: it reports what and why
CONTEXT      files and PRs to read; the reports of units it depends on, pasted in full
FACTS        verified (and how) / unverified (marked)
ACCEPTANCE   checkable criteria, one per line
VERIFY       exact commands for only the tests its change touches, plus known gotchas. Loose: numbers printed,
             no new hard timing gates. The full gate is yours
TIMEBOX      a rough cap on runtime; when it runs out, return partial findings and stop
FORBIDDEN    push, rebase, merge, open a PR; fixes outside scope; staging anything but named paths; asking the
             user (it states the assumption and keeps going); comments that cite review rounds, PRs or phases
REPORT       in its reply: status, branch, head and commits, what it actually ran, deviations, what the prototype
             kept and dropped, numbers, what it did not run or verify, open questions
PROJECT      the project card's additions, verbatim
```

Size the brief to the unit: a one-command change gets one paragraph that still names the goal, scope, verify command and report.

A fix-round brief: the original brief and its later additions, the act items only (each with a budget, and a fallback if it does not fit), the prior report, the branch and head. Decide consider items yourself before sending; an implementer treats whatever it receives as an order.
