---
name: bitwarden-vault
description: Read credentials from a dedicated self-hosted Bitwarden/Vaultwarden account through the bundled read-only bw wrapper. Use when the user asks to inspect available vault entries, retrieve a username, password, or TOTP, or use a stored credential for the current task.
---

# Bitwarden Vault

Resolve `scripts/bw-agent` relative to this `SKILL.md` and use it instead of calling `bw` directly.

## Commands

```bash
bash scripts/bw-agent status
bash scripts/bw-agent list
bash scripts/bw-agent get username ITEM_ID_OR_EXACT_NAME
bash scripts/bw-agent get password ITEM_ID_OR_EXACT_NAME
bash scripts/bw-agent get totp ITEM_ID_OR_EXACT_NAME
```

`list` emits only item id, name, type, collection, folder, and custom-field names.

## Rules

- Prefer an item id returned by `list`.
- Retrieve only the field required for the task.
- Treat `get` output as secret: use it immediately and never repeat it in commentary or the final response.
- Do not run wrapper invocations concurrently.
- Do not bypass the wrapper or perform mutating vault operations.
