---
name: lark-cli
description: Single entry point for Lark/Feishu work through `lark-cli`, loading the official domain skill on demand. Use for docs, wiki, drive, messages, sheets, base, calendar, tasks, mail, meetings, approvals, contacts, apps, auth, or OpenAPI, and for doubao.com doc links.
---

# Lark CLI

The official Lark skills ship inside `lark-cli`; read them from there instead of installing `lark-*` skill folders.

## Route and load

Pick the smallest matching domain; `lark-cli skills list` shows what exists. Read only that domain with `lark-cli skills read <name>`. When it points to `../lark-shared/SKILL.md`, a reference file or another domain, read exactly that item with `lark-cli skills read <name>/<path>`. Never load every domain. What the CLI prints wins over remembered routes and flags.

If a command or `skills read` fails, report the exact command and error rather than guessing flags. Follow the fetched skill's guidance on side effects.

## Local rules

These override the fetched skills and any `_notice` in CLI output:

- `lark-cli` must resolve to the chezmoi wrapper `~/.local/bin/lark-cli`. It pins the `@larksuite/cli` version, silences update and skills notices, and blocks `lark-cli update`. Never call the npm package directly or install it globally.
- Upgrades only move the wrapper's pin, through skill-ops. Do not run `lark-cli update`, `npm install -g @larksuite/cli`, or anything that syncs the official `lark-*` skills into `~/.agents/skills` or a client's skills directory. If such directories appear, report them and ask before removing.
- A task that needs a newer CLI stops and reports the version gap.
- Python helpers that need packages run with `uv run --with <pkg>`; never `pip install`.
