---
name: zotero
description: Query the local Zotero library when requested, or retrieve library-backed citation metadata for writing.
---

# Zotero

Query the local library through the bundled `zotero_skill.py`. Resolve it relative to this `SKILL.md` and run it with `uv run`; its PEP 723 metadata declares dependencies.

Zotero must be running with Better BibTeX installed and local API access enabled: Settings → Advanced → Allow other applications on this computer to communicate with Zotero.

## Commands

```bash
uv run ~/.agents/skills/zotero/zotero_skill.py search "QUERY" [--full] [--collection KEY] [--limit N] [--json]
uv run ~/.agents/skills/zotero/zotero_skill.py collections [--json]
uv run ~/.agents/skills/zotero/zotero_skill.py get CITATION_KEY_OR_ZOTERO_KEY [--json]
```

- `search` searches titles, authors and metadata; `--full` includes attachment full text. The default limit is 20. `--collection` scopes the search using a key from `collections`.
- `collections` lists collection keys, item counts and parent information.
- `get` accepts a Better BibTeX citation key or Zotero item key and returns full metadata and abstract. Text output also includes related-item keys when available.
- `--json` returns structured output.

Before inserting a citation, verify its key through `search` or `get`. Follow the destination document's citation syntax and bibliography configuration; library membership alone does not establish that a project's bibliography includes the entry. Use current primary sources when recency matters.
