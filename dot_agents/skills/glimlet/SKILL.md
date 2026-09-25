---
name: glimlet
description: Publish, update or manage local HTML artifacts on Glimlet when requested.
---

# Glimlet Skill

Use this skill when the user wants to publish a local artifact to Glimlet.

## Rules

- Only upload local artifact paths; a path may be a single HTML file or a directory.
- If the artifact exists only as HTML text, write it to a local `.html` file first.
- For a directory artifact, the root must contain `index.html`.
- Every new publish must include a human-readable `--title`.
- Do not call the Glimlet HTTP API directly unless the CLI is unavailable.
- Do not print or expose `GLIMLET_ADMIN_TOKEN`.
- Prefer CLI `--json` output when another agent will consume the result.
- After `publish`, confirm that the CLI wrote the page id marker.
- If the user gives a page id, update that page.
- If no page id is provided, call `update PATH` first only when the artifact has a Glimlet id marker; otherwise call `publish PATH`.
- Final user-facing output should include the title, URL, expiration time, and whether the action created or updated the page.

## CLI Path

Resolve `scripts/glimlet.py` relative to this `SKILL.md`, regardless of the current working directory.

```bash
python3 scripts/glimlet.py
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

Create a new page:

```bash
python3 scripts/glimlet.py publish /path/to/artifact --title "Demo" --ttl 7d --json
```

Update using the artifact marker:

```bash
python3 scripts/glimlet.py update /path/to/artifact --json
```

Update a specific page:

```bash
python3 scripts/glimlet.py update PAGE_ID /path/to/artifact --ttl 7d --json
```

List pages:

```bash
python3 scripts/glimlet.py list --json
```

Expire a page:

```bash
python3 scripts/glimlet.py expire PAGE_ID --yes --json
```

Prune old content:

```bash
python3 scripts/glimlet.py prune --expired-older-than 90d --dry-run --json
python3 scripts/glimlet.py prune --expired-older-than 90d --yes --json
```

## Page Id Marker

- Directory artifact: `ARTIFACT_DIR/.glimlet_id`
- Single file artifact: `artifact.html.glimlet_id`

The marker contains only the page id.
