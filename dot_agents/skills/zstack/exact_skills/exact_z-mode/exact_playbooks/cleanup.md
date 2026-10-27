# Cleanup

For docs, scratch, ignored dirs or disk that have grown.

1. List what exists: docs, ignored dirs, worktrees and their build output, images, helper scripts.
2. For each, name its consumer now and when it dies, per every-artifact-dies. No consumer: delete it. Doubtful: move it to a quarantine dir outside the repo, tell the user, delete it later.
3. Rewrite docs to the current state in plain words. Cut history, notes of which review or PR something came from, and agent jargon.
4. Grep tracked files for ignored paths and for names you coined.
5. Report what went and what stayed, with sizes.
