# Board data (`research-board/0.1`)

| Key | Holds |
|---|---|
| `board` | `title`, `subtitle`, `as_of`, `state`, `question`, `headline`, `source` (`kind`, `title`, `id`, `parent_id`, `forked_at`, `fork_note`), `focus` (node ids to ring), `constraints`, `ledger_note` |
| `refs` | source papers or repos: `id`, `label`, `note`; nodes point at them with `refs` |
| `lanes` | the DAG's columns, one per line of work: `id`, `tag`, `title`, `question`, `status` (`active`, `closed`, `parked`), `verdict` |
| `nodes` | `id`, `lane`, `kind` (`seed`, `experiment`, `discussion`, `finding`, `candidate`), `status`, `origin` (`user`, `agent`), `date`, `title`, `summary`; optional `rank`, `badge`, `detail[]`, `metrics[]` (`label`, `value`, `verdict`: `pass`, `fail`, `tie`, `info`), `cost` (`gpu_h`, `device`, `note`), `refs[]`, `artifacts[]` |
| `edges` | `from`, `to`; optional `kind` (`weak` is dashed, `aside` keeps the row) and `label` |
| `decisions` | the user's inputs: `at`, `quote`, `effect`, `nodes[]`, optional `focus` |
| `charts` | line charts: `y` (`key`, `label`, `scale`: `log` or linear, `digits`), `x_modes[]` (`key`, `label`, `digits`; the reader toggles between them), `series[]` (`label`, `short`, `points[]`), `annotations[]` (`label`, `at` keyed by x mode), `note` |

A node's `status` is one of `insight`, `supported`, `rejected`, `mixed`, `conclusion`, `stopped`, `discussed`, `running`, `proposed`, `parked`. Without `rank`, a node sits one row below its deepest parent. A time with a UTC offset shows in the viewer's timezone, so write the offset. `build.py` sets `as_of` to the latest such time among `base.json`'s `as_of`, the nodes, the decisions and the rounds' `progress`.

## What `build.py` reads from a round's `STATUS.json`

- `node`: a node as above. `id` defaults to the round's path under `experiments/` (`<line>/<round>`). `parents` (ids, or edge objects without `to`) become edges into it.
- `gpu_hours_used` and `compute.machine`: the node's `cost`, unless the node sets one.
- `decisions`: the user's decisions about the round; `nodes` defaults to the round's node.
- A `README.md` beside the STATUS becomes the node's artifact unless it lists its own.

A round's node replaces a `base.json` node with the same id, so a line can move from hand-written to round-owned one node at a time.
