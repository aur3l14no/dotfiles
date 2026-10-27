# Diagnose

For a run that fell, froze, jumped, refused or flaked.

1. Look the way the user looks, through the project's verification skill. If the project has none, write one with the **create-verification-skill** skill first.
2. Find the cause before loosening anything. An unexplained failure is never just recorded. A flake gets a causal fix (wait on the real condition), not a wider number; reproduce a timing flake under a starved CPU before calling it fixed.
3. Check what a viewer or a summary shows against the system's own record, per prove-it-works.
