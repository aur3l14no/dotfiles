# Synced Pages

`scripts/sync.py` keeps a page derived from one or more local source files. The page is one HTML file; layout and style are up to the agent that writes it. Each synced page keeps its mapping in its own Glimlet metadata, which is admin-only and never served: the host that maintains it, the source files, a short publishing prompt saying how to derive the page, a deny list, the TTL, and the hashes it was derived from. The published page itself is the base for the next derivation. Nothing is stored locally. Each machine maintains only the pages it created.

```bash
S=~/.agents/skills/glimlet/scripts/sync.py   # call as: uv run $S ...
```

## Sync Round

1. Run `uv run $S scan`. It renews pages close to expiry by itself. If it prints `nothing to do`, reply with one line saying so and stop.
2. Handle each page by its action:
   - `derive`: dispatch one sub-agent told only: "Read `<the brief path scan printed>` and do what it says." Several pages can run in parallel. If the harness has no sub-agents, follow the brief yourself.
   - `wait`: a source is still being edited, or an agent is still deriving the page. Don't report it; a later round picks it up.
   - `error`: report one line and leave it. Don't repeat an item already reported in an earlier round.
3. Report one line per derived page: what changed (from the sub-agent's report) and the link. On failure, quote the error.

## By Hand

- `show [PAGE_ID]` prints the mapping of this host's pages.
- New page: write the first version as one HTML file in the conversation and let the user review it, then run `create PAGE.html --title T --source FILE ... --prompt-file P --deny WORD ...`.
- Change the title, prompt, sources, deny list or TTL with `set PAGE_ID ...`. `--deny` replaces the whole list, so repeat the words to keep. A changed prompt, sources or deny list makes the next scan derive the page again.
- To stop syncing a page, expire it.

## Rules

- Anyone with the link can read a page. Create a synced page only for files the user asked to publish.
- Put words that must not appear on the page, such as private folder names or internal labels, in its deny list; the list lives in the private metadata.
- Before uploading, `create` and `push` check the page for local paths and words on the deny list. If a check fails, nothing is uploaded: fix the page or the prompt, never work around the check.
- The deriving agent edits only the page.html named in its brief. It does not change the sources or call Glimlet.
