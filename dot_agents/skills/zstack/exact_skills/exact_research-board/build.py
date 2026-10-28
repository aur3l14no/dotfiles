"""Merge a project's board data and publish the page privately on Glimlet.

    uv run python build.py <project> [--html FILE [--embed]] [--local]

Reads <project>/research/board/base.json and the `node` of every <project>/experiments/**/STATUS.json,
writes <project>/research/board/board.json, copies the template to <project>/research/board/site/,
then uploads that directory as a private page (created on the first run, its id kept in
site/.glimlet_id) and pushes board.json as its data. --local skips the upload. --html also writes
a standalone page with the data inlined; --embed makes it transparent and unpadded for an inline preview.
"""

import argparse
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "site" / "index.html"
GLIMLET = Path.home() / ".agents" / "skills" / "glimlet" / "scripts" / "glimlet.py"
SLOT = '<script type="application/json" id="board-data"></script>'


def round_parts(root: Path, status_path: Path, status: dict) -> tuple[dict, list, list]:
    rel = status_path.relative_to(root)
    node = dict(status["node"])
    node.setdefault("id", "/".join(rel.parent.parts[1:]))
    edges = [p if isinstance(p, dict) else {"from": p} for p in node.pop("parents", [])]
    edges = [{**e, "to": node["id"]} for e in edges]
    hours = status.get("gpu_hours_used")
    if "cost" not in node and isinstance(hours, (int, float)):
        node["cost"] = {"gpu_h": hours, "device": status.get("compute", {}).get("machine")}
    readme = status_path.with_name("README.md")
    if "artifacts" not in node and readme.exists():
        node["artifacts"] = [str(readme.relative_to(root))]
    decisions = [{**d, "nodes": d.get("nodes") or [node["id"]]} for d in status.get("decisions", [])]
    return node, edges, decisions


def latest(times: list) -> str | None:
    """The latest of the times that carry a UTC offset, as written."""
    best = None
    for s in times:
        try:
            t = datetime.fromisoformat(s)
        except (TypeError, ValueError):
            continue
        if t.tzinfo and (best is None or t > best[0]):
            best = (t, s)
    return best and best[1]


def merge(root: Path) -> dict:
    board = json.loads((root / "research" / "board" / "base.json").read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in board.get("nodes", [])}
    edges = {(e["from"], e["to"]): e for e in board.get("edges", [])}
    decisions = list(board.get("decisions", []))
    progress = []
    for path in sorted((root / "experiments").glob("**/STATUS.json")):
        status = json.loads(path.read_text(encoding="utf-8"))
        if "node" not in status:
            continue
        node, new_edges, new_decisions = round_parts(root, path, status)
        nodes[node["id"]] = node
        edges.update({(e["from"], e["to"]): e for e in new_edges})
        decisions += new_decisions
        progress += [p.get("at") for p in status.get("progress", [])]
    board["nodes"], board["edges"], board["decisions"] = list(nodes.values()), list(edges.values()), decisions
    head = board.setdefault("board", {})
    times = [head.get("as_of"), *progress] + [n.get("date") for n in board["nodes"]] + [d.get("at") for d in decisions]
    head["as_of"] = latest(times) or head.get("as_of")
    return board


def glimlet(*args: str) -> dict:
    out = subprocess.run(["uv", "run", "--quiet", str(GLIMLET), *args, "--json"], check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


def publish(out: Path, title: str) -> None:
    # An upload replaces every file of the page, its data included, so the data goes up after it.
    glimlet("share", str(out / "site"), "--private", "--title", title)
    page_id = (out / "site" / ".glimlet_id").read_text(encoding="utf-8").strip()
    pushed = glimlet("data", page_id, str(out / "board.json"))
    print(pushed["url"], "expires", pushed["expires_at"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", type=Path)
    ap.add_argument("--html", type=Path, help="also write a standalone page with the data inlined")
    ap.add_argument("--embed", action="store_true", help="transparent background, no page padding")
    ap.add_argument("--local", action="store_true", help="build only, don't publish")
    args = ap.parse_args()
    root = args.project.resolve()
    board = merge(root)
    out = root / "research" / "board"
    (out / "board.json").write_text(json.dumps(board, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "site").mkdir(exist_ok=True)
    shutil.copyfile(TEMPLATE, out / "site" / "index.html")
    print(out / "board.json", f"({len(board['nodes'])} nodes, {len(board['edges'])} edges)")
    if args.html:
        # Escaping every "<" keeps the JSON from closing the script element.
        blob = json.dumps(board, ensure_ascii=False).replace("<", "\\u003c")
        html = TEMPLATE.read_text(encoding="utf-8").replace(SLOT, f'<script type="application/json" id="board-data">{blob}</script>')
        if args.embed:
            html = html.replace('<html lang="zh-CN">', '<html lang="zh-CN" data-embed>', 1)
        args.html.parent.mkdir(parents=True, exist_ok=True)
        args.html.write_text(html, encoding="utf-8")
        print(args.html)
    if not args.local:
        publish(out, board["board"]["title"])


if __name__ == "__main__":
    main()
