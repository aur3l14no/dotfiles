---
name: bitwarden-vault
description: Retrieve or use stored Bitwarden/Vaultwarden credentials, or list available vault entries, when requested.
---

# Bitwarden Vault

Run `scripts/bw-agent` (relative to this `SKILL.md`) instead of `bw`. It gives
every call a private disposable session, so concurrent agents — in any harness —
never invalidate each other and never need the master password.

Every `bw` command works unchanged. The wrapper adds no verbs of its own:

```bash
bash scripts/bw-agent list items --search github   # ids and names, no secrets
bash scripts/bw-agent get password ITEM_ID
bash scripts/bw-agent get totp ITEM_ID
bash scripts/bw-agent sync
```

`bw --help` is the command reference. Prefer item ids over names; `bw get`
matches names by substring and fails when the match is ambiguous.

Writes are built with `bw get template item | jq … | bw encode` and committed
with `bw create item <payload>`. Set `organizationId` and `collectionIds`
explicitly — the personal vault is the default.

## Rules

- `list items` and `get item` are **projected, not raw**: they return id, name,
  type, username, URIs, and custom-field *names* only. Passwords, TOTP seeds,
  notes, and field values are stripped on the way out, so use them freely to
  find an id. `export` is refused outright.
- `get` and `list` read the snapshot frozen at `--setup`: items added since are
  invisible until `sync`. Run `sync` only when the user asks for it.
- Retrieve one field at a time and **pipe it straight into the consumer**, e.g.
  `... get password ITEM_ID | pbcopy`. Never print a secret on its own line, and
  never repeat one in commentary or the final response.
- Never put a secret in a command's arguments (`ps` sees them); use a pipe.
- Never run `lock` or `unlock`; they destroy the session this skill depends on.
- Write to the vault only when the user explicitly authorizes that specific
  write in the current task. Name the target collection on every write: an item
  left in the personal vault is invisible to members of a shared collection.
- If `sync` or a write fails with an auth error the frozen session is dead.
  Reads keep working. Tell the user to re-run `--setup` as a human.

## Setup (human only, one time)

```bash
bash scripts/bw-agent --setup https://vault.example.com   # fresh machine
BW_AGENT_STATE_DIR=~/.config/bitwarden-agent/cli \
  bash scripts/bw-agent --setup                           # reuse an existing sign-in
```

Pass a server URL, or point `BW_AGENT_STATE_DIR` at an existing CLI state
directory to adopt its sign-in instead of registering a new device; exactly one
of the two is required. Setup asks for the master password (twice on a fresh
machine: once for `bw login`, once to freeze the session) and writes it nowhere.
It freezes the unlocked session into `~/.config/bitwarden-agent/template/`.
Run it again only when the session dies.

The template is an unrevocable credential for the whole vault: `--setup` does
not invalidate a copy that leaked. Keep it at 0600 and treat it like the master
password itself.
