---
name: research-board
description: Render a project's research record as a private Glimlet page: the lines, the exploration DAG, the user's decisions, key curves and GPU-hours. Use after every round and close, and when the user wants to see the exploration.
disable-model-invocation: true
---

# Research board

One page per project, published privately with the **glimlet** skill. `site/index.html` next to this file is the template: on Glimlet it reads `./data`, and it renders every value as text, never as HTML. `schema.md` describes the data.

Each fact is written once, in one of two places:

- `research/board/base.json` holds what no round owns: the header, source papers, lanes, seeds, discussions, conclusions, candidates, the edges among them, decisions not tied to a round, and charts.
- Each round's `STATUS.json` holds its `node`, its `parents`, its GPU-hours and the user's decisions about it.

`build.py <project>` merges them into `research/board/board.json`, uploads `research/board/site/` as a private page (created on the first run, its id kept in `site/.glimlet_id`) and pushes the data. Run it after every round and every close; each run renews the page's expiry. `--local` only builds; `--html FILE` also writes a standalone copy.

Write each node for someone who did not follow the thread: a title that names the thing, one or two plain sentences, numbers in the metrics with a verdict on each. Discussions and the user's inputs belong on the board as much as experiments; they explain why the lines turned.

Keep the page private: it carries machine names, paths and unpublished results.
