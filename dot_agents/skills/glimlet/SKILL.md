---
name: glimlet
description: Share local HTML artifacts on Glimlet.
---

# Glimlet Skill

Use this skill when the user wants to publish a local artifact to Glimlet.

## Rules

- Only upload local artifact paths; a path may be a single HTML file or a directory, or a JSON file with `--template`.
- Pages are public by default: anyone with the link can read them. Use `--private` for anything meant only for the user, such as dashboards, briefs or notes with private details.
- Content going public is checked for local paths and for words passed with `--deny`. If a check fails, fix the content. Never pass `--skip-checks` unless the user explicitly asks.
- If the artifact exists only as HTML text, write it to a local `.html` file first.
- For a directory artifact, the root must contain `index.html`.
- Every new publish must include a human-readable `--title`.
- Do not call the Glimlet HTTP API directly unless the CLI is unavailable.
- Do not print or expose `GLIMLET_ADMIN_TOKEN`.
- Prefer CLI `--json` output when another agent will consume the result.
- After sharing, surface any marker warning and preserve the returned URL and ID.
- If the user gives a page id, update that page.
- If no page id is provided, use `share PATH`; use `--new` only to intentionally create a separate link.
- Final user-facing output should include the title, URL, expiration time, and whether the action created or updated the page.

## CLI Path

Resolve `scripts/glimlet.py` relative to this `SKILL.md`, regardless of the current working directory.

```bash
uv run scripts/glimlet.py
```

## Configuration

The CLI reads environment variables first:

```text
GLIMLET_BASE_URL=https://glimlet.example.com
GLIMLET_ADMIN_TOKEN=...
GLIMLET_DEFAULT_TTL_SECONDS=604800
```

It also reads a fixed TOML config path:

```text
~/.config/glimlet/config.toml
```

Example:

```toml
base_url = "https://glimlet.example.com"
admin_token = "..."
default_ttl_seconds = 604800
```

## Commands

Share using the marker (creates a page on first use, updates the same link afterward):

```bash
uv run scripts/glimlet.py share /path/to/artifact --title "Demo" --json
uv run scripts/glimlet.py share /path/to/artifact --title "Separate copy" --new --json
```

Preview the exact upload inventory without credentials or network access:

```bash
uv run scripts/glimlet.py share /path/to/artifact --title "Demo" --dry-run --json
```

All uploads refresh the TTL from the current time (default 7 days, configurable). Use a dedicated artifact directory: all non-excluded files are uploaded, up to 5 MiB total. Symbolic links are rejected; single files must use `.html` or `.htm`.

Create a new page:

```bash
uv run scripts/glimlet.py publish /path/to/artifact --title "Demo" --ttl 7d --json
```

Update using the artifact marker:

```bash
uv run scripts/glimlet.py update /path/to/artifact --json
```

Update a specific page:

```bash
uv run scripts/glimlet.py update PAGE_ID /path/to/artifact --ttl 7d --json
```

List pages:

```bash
uv run scripts/glimlet.py list --json
```

Private pages, and publishing one later (the upload runs the checks):

```bash
uv run scripts/glimlet.py share /path/to/brief.html --title "Brief" --private --json
uv run scripts/glimlet.py update PAGE_ID /path/to/brief.html --public --deny "internal-name" --json
```

A status board: a JSON file shown by the built-in `status` template. Later runs replace only the data. `--expect-every` makes Glimlet alert when the board stops being written; use it only for pages an unattended loop writes.

```bash
uv run scripts/glimlet.py share state.json --template status --title "Infra" --private --expect-every 1h --json
uv run scripts/glimlet.py data PAGE_ID state.json --json
```

```json
{"title": "Infra", "summary": "1 item needs attention", "sections": [
  {"title": "Hosts", "items": [{"name": "host-a", "state": "crit", "detail": "offline since 09:12",
    "since": "2026-10-19T09:12:00Z", "link": "https://example.com/runbook"}]}]}
```

`state` is `ok`, `warn`, `crit` or `unknown`; `detail`, `since` and `link` are optional.

Change the title, metadata or settings without uploading:

```bash
uv run scripts/glimlet.py set PAGE_ID --title "Infra" --private --expect-every 30m --grace 10m --json
uv run scripts/glimlet.py set PAGE_ID --no-expect --json
```

Expire a page:

```bash
uv run scripts/glimlet.py expire PAGE_ID --yes --json
```

Prune old content:

```bash
uv run scripts/glimlet.py prune --expired-older-than 90d --dry-run --json
uv run scripts/glimlet.py prune --expired-older-than 90d --yes --json
```

## Page Id Marker

- Directory artifact: `ARTIFACT_DIR/.glimlet_id`
- Single file artifact: `artifact.html.glimlet_id`

The marker contains only the page id.
