#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Keep Glimlet pages in sync with local source files.

Each synced page is one HTML file that an agent derives from local source
files. Its mapping lives in its Glimlet metadata under "sync": the host that
maintains it, the sources, the publishing prompt, a deny list, the TTL, and the
hashes of the sources and settings it was last derived from. The published
page is the base for the next derivation, so no page content is kept anywhere
else; each machine maintains the pages it published.

    sync.py scan                 renew pages close to expiry; brief the pages to derive
    sync.py push PAGE_ID         check and upload a derived page
    sync.py show [PAGE_ID]       the mapping of this host's pages
    sync.py create PAGE.html --title T --source FILE ... --prompt-file P [--deny W ...] [--ttl 30d]
    sync.py set PAGE_ID [--title T] [--source FILE ...] [--prompt-file P] [--deny W ...] [--ttl 30d]

The host is the short hostname, or GLIMLET_SYNC_HOST when set.
"""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
GLIMLET = HERE / "glimlet.py"
HOST = os.environ.get("GLIMLET_SYNC_HOST") or platform.node().split(".")[0]
WORK_ROOT = Path(tempfile.gettempdir()) / "glimlet-sync"
QUIET_SECONDS = 300  # a source written more recently may still be being edited
STALE_SECONDS = 3600  # a workspace older than this was abandoned by its agent
LOCAL_PATHS = ["/Users/", "/home/", "~/", "file://"]
KEYS = ("host", "sources", "prompt", "deny", "ttl", "source_sha256", "settings_sha256")

BRIEF = """\
# Derive: {title}

Bring `{page}` (the page as published now) up to date with the source files, following the \
publishing prompt below. Edit only this file: do not change the sources, do not call Glimlet.

## Publishing prompt

{prompt}

## Sources

{sources}

## Rules

- Read the sources and the page through, find what the sources added, changed or removed that the \
page has not caught up with, and change only that. Keep the page's design and leave everything else \
as it is.{settings_note}
- Add nothing that is not in the sources.
- The page stays one HTML file; it cannot load or link to local files.{links}

## When done

Run `{push}`. It checks the page for local paths and words on the deny list, and uploads it. If a \
check fails, fix the page as it says and run it again; never work around a check. Then report what \
you changed (a sentence or two) and the result of push.
"""


class Failure(Exception):
    """A problem that stops the command; nothing past the failing step was uploaded."""


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def remote_hash(data: bytes) -> str:
    """Glimlet's content_sha256 for a single-file page (see artifactHash in its upload.ts)."""
    return sha256(f"index.html\0{sha256(data)}\0{len(data)}".encode())


def portable(file: str) -> str:
    """A source path as stored in metadata: relative to ~ when it is under the home directory."""
    path = Path(file).expanduser().resolve()
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return str(path)


def ttl_seconds(ttl: str) -> int:
    """A TTL glimlet.py already accepted, such as 30d, 12h or seconds."""
    ttl = ttl.strip().lower()
    return int(ttl[:-1]) * {"d": 86400, "h": 3600, "m": 60, "s": 1}[ttl[-1]] if ttl[-1].isalpha() else int(ttl)


def expires_in(page: dict) -> float:
    if not page.get("expires_at"):
        return float("inf")
    return (datetime.fromisoformat(page["expires_at"]) - datetime.now(timezone.utc)).total_seconds()


# --- glimlet ------------------------------------------------------------------------


def glimlet(*args: str) -> dict:
    process = subprocess.run([sys.executable, str(GLIMLET), *args, "--json"], capture_output=True, text=True)
    try:
        data = json.loads(process.stdout)
    except ValueError:
        data = {}
    if process.returncode or "error" in data:
        message = (data.get("error") or {}).get("message") or process.stderr.strip()[-300:]
        raise Failure(f"glimlet {args[0]}: {message or f'exit {process.returncode}'}")
    return data


def upload(data: bytes, command: list[str], *flags: str) -> dict:
    """Run `glimlet COMMAND PATH FLAGS` with DATA saved as a temporary index.html."""
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "index.html"
        path.write_bytes(data)
        return glimlet(*command, str(path), *flags)


def metadata(sync: dict) -> str:
    """The sync mapping to store; drops keys older versions of this script wrote."""
    return json.dumps({"sync": {key: sync.get(key) for key in KEYS}}, ensure_ascii=False)


def fetch(page: dict) -> bytes:
    """The published page, checked against the hash Glimlet stored for it."""
    request = urllib.request.Request(page["url"], headers={"user-agent": "glimlet-sync"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    if remote_hash(data) != page.get("content_sha256"):
        raise Failure(f"{page['url']} did not return the single HTML file Glimlet stored")
    return data


def synced_pages() -> list[dict]:
    """This host's live synced pages. Expired or pruned pages are no longer synced."""
    pages, cursor = [], None
    while True:
        data = glimlet("list", "--limit", "100", *(["--cursor", cursor] if cursor else []))
        pages += data.get("pages") or []
        cursor = data.get("next_cursor")
        if not cursor:
            break
    return [page for page in pages if page.get("status") == "active"
            and isinstance(page.get("metadata"), dict) and isinstance(page["metadata"].get("sync"), dict)
            and page["metadata"]["sync"].get("host") == HOST]


def page_sync(page_id: str) -> tuple[dict, dict]:
    page = glimlet("info", page_id)
    sync = page["metadata"].get("sync") if isinstance(page.get("metadata"), dict) else None
    if not isinstance(sync, dict):
        raise Failure(f"{page_id} has no sync metadata")
    if sync.get("host") != HOST:
        raise Failure(f"{page_id} is maintained by {sync.get('host')}, not {HOST}")
    return page, sync


# --- sources and checks -------------------------------------------------------------


def source_shas(sync: dict) -> dict[str, str]:
    shas = {}
    for source in sync["sources"]:
        path = Path(source).expanduser()
        if not path.is_file():
            raise Failure(f"source not found: {source} (renamed? fix it with `set --source`)")
        shas[source] = sha256(path.read_bytes())
    return shas


def settings_sha(sync: dict) -> str:
    """Changing any of these makes the next scan derive the page again."""
    return sha256(json.dumps([sync["prompt"], sync["sources"], sync["deny"]], ensure_ascii=False).encode())


def link_map(pages: list[dict]) -> dict[str, str]:
    """Source file name -> URL of the synced page built from it; ambiguous names stay unmapped."""
    urls: dict[str, set[str]] = {}
    for page in pages:
        for source in page["metadata"]["sync"]["sources"]:
            urls.setdefault(Path(source).name, set()).add(page["url"])
    return {name: next(iter(found)) for name, found in urls.items() if len(found) == 1}


def check(data: bytes, deny: list[str]) -> None:
    """Fail if the page contains a local path or a denied word."""
    html = data.decode("utf-8")
    problems = [f"contains {term!r}" for term in LOCAL_PATHS if term in html]
    problems += [f"contains denied {word!r}" for word in deny if word and word.lower() in html.lower()]
    if problems:
        raise Failure("checks failed, nothing uploaded:\n" + "\n".join(f"  - {item}" for item in problems))


# --- derivation ---------------------------------------------------------------------


def needs(page: dict) -> tuple[str | None, str]:
    sync = page["metadata"]["sync"]
    shas = source_shas(sync)
    changed = [source for source, sha in shas.items() if sha != sync["source_sha256"].get(source)]
    if changed or settings_sha(sync) != sync.get("settings_sha256"):
        work = WORK_ROOT / page["id"]
        busy = time.time() - work.stat().st_mtime if work.is_dir() else STALE_SECONDS
        if busy < STALE_SECONDS:
            return "wait", f"an agent has been deriving it for {int(busy) // 60}m"
        now = time.time()
        recent = [f"{source} ({int(now - mtime)}s ago)" for source in sync["sources"]
                  if now - (mtime := Path(source).expanduser().stat().st_mtime) < QUIET_SECONDS]
        if recent:
            return "wait", "just written, maybe still being edited: " + "; ".join(recent)
        return "derive", "changed: " + ("; ".join(changed) or "the prompt, sources list or deny list")
    if expires_in(page) < ttl_seconds(sync["ttl"]) / 2:
        return "renew", ""
    return None, ""


def prepare(page: dict, pages: list[dict]) -> Path:
    """Write the workspace for the deriving agent; return its brief."""
    sync = page["metadata"]["sync"]
    html = fetch(page)
    state = {"source_sha256": source_shas(sync), "settings_sha256": settings_sha(sync),
             "base_sha256": page["content_sha256"]}
    links = sorted(link_map(pages).items())

    work = WORK_ROOT / page["id"]
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    (work / "page.html").write_bytes(html)
    (work / "work.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    settings_note = (" This time the publishing prompt, sources list or deny list changed: go over the whole "
                     "page with the new settings." if state["settings_sha256"] != sync.get("settings_sha256") else "")
    brief = BRIEF.format(
        title=page["title"], page=work / "page.html", prompt=sync["prompt"],
        sources="\n".join(f"- `{Path(source).expanduser()}`" for source in sync["sources"]),
        settings_note=settings_note,
        links="\n- A link to one of these files goes to its published page instead:\n"
              + "\n".join(f"  - `{name}`: {url}" for name, url in links) if links else "",
        push=f"uv run {HERE / 'sync.py'} push {page['id']}")
    (work / "BRIEF.md").write_text(brief, encoding="utf-8")
    return work / "BRIEF.md"


# --- commands -----------------------------------------------------------------------


def cmd_scan(args: argparse.Namespace) -> int:
    pages = synced_pages()
    lines = []
    for page in pages:
        try:
            action, detail = needs(page)
            if action == "renew":
                upload(fetch(page), ["update", page["id"]], "--ttl", page["metadata"]["sync"]["ttl"])
                action = None
            elif action == "derive":
                detail += f"\n  brief: {prepare(page, pages)}"
        except (Failure, OSError) as error:
            action, detail = "error", str(error)
        if action:
            lines.append(f"{page['id']} 「{page['title']}」: {action}  {detail}")
    print("\n".join(lines) or "nothing to do")
    return 0


def cmd_push(args: argparse.Namespace) -> int:
    page, sync = page_sync(args.page_id)
    work = WORK_ROOT / args.page_id
    if not (work / "work.json").is_file():
        raise Failure(f"no workspace for {args.page_id}; the next scan prepares one")
    prepared = json.loads((work / "work.json").read_text(encoding="utf-8"))
    if prepared["base_sha256"] != page["content_sha256"]:
        shutil.rmtree(work, ignore_errors=True)
        raise Failure("the page changed on Glimlet after this workspace was prepared; the next scan prepares it again")
    html = (work / "page.html").read_bytes()
    check(html, sync["deny"])
    # Record what the agent derived from; anything that changed since then is derived on the next scan.
    result = upload(html, ["update", args.page_id], "--ttl", sync["ttl"],
                    "--metadata-json", metadata({**sync, **prepared}))
    shutil.rmtree(work, ignore_errors=True)
    print(f"「{page['title']}」: uploaded, expires {result['expires_at'][:10]}  {page['url']}")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    pages = [page_sync(args.page_id)[0]] if args.page_id else synced_pages()
    for page in pages:
        sync = page["metadata"]["sync"]
        print(f"{page['id']} 「{page['title']}」 {page['url']}  expires {page['expires_at'][:10]}")
        print("  sources: " + "; ".join(sync["sources"]))
        print(f"  ttl: {sync['ttl']}  deny: {', '.join(sync['deny']) or '-'}")
        print("  prompt:\n" + "\n".join("    " + line for line in sync["prompt"].splitlines()))
    if not pages:
        print(f"no synced pages for {HOST}")
    return 0


def cmd_create(args: argparse.Namespace) -> int:
    sync = {"host": HOST, "sources": [portable(source) for source in args.source], "deny": args.deny,
            "prompt": Path(args.prompt_file).read_text(encoding="utf-8").strip(), "ttl": args.ttl}
    sync.update(source_sha256=source_shas(sync), settings_sha256=settings_sha(sync))
    html = Path(args.page_html).read_bytes()
    check(html, sync["deny"])
    page = upload(html, ["publish"], "--title", args.title, "--ttl", args.ttl, "--metadata-json", metadata(sync))
    print(f"created {page['id']}: {page['url']}")
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    page, sync = page_sync(args.page_id)
    if args.source:
        sync["sources"] = [portable(source) for source in args.source]
        source_shas(sync)
    if args.prompt_file:
        sync["prompt"] = Path(args.prompt_file).read_text(encoding="utf-8").strip()
    if args.deny is not None:
        sync["deny"] = args.deny
    if args.ttl:
        sync["ttl"] = args.ttl
    # Glimlet stores metadata only with an upload, so the published page goes up again unchanged.
    title = ["--title", args.title] if args.title else []
    upload(fetch(page), ["update", args.page_id], *title, "--ttl", sync["ttl"], "--metadata-json", metadata(sync))
    print(f"updated the mapping of {args.page_id}; a changed prompt, sources or deny list is derived on the next scan")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Keep Glimlet pages in sync with local source files.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan", help="renew pages close to expiry; brief the pages to derive").set_defaults(func=cmd_scan)
    push = commands.add_parser("push", help="check and upload a derived page")
    push.add_argument("page_id")
    push.set_defaults(func=cmd_push)
    show = commands.add_parser("show", help="print the mapping of this host's pages")
    show.add_argument("page_id", nargs="?")
    show.set_defaults(func=cmd_show)
    create = commands.add_parser("create", help="publish a new synced page from a reviewed HTML file")
    create.add_argument("page_html", metavar="PAGE.html")
    create.add_argument("--title", required=True)
    create.add_argument("--source", nargs="+", required=True, metavar="FILE")
    create.add_argument("--prompt-file", required=True)
    create.add_argument("--deny", nargs="*", default=[], metavar="WORD")
    create.add_argument("--ttl", default="30d")
    create.set_defaults(func=cmd_create)
    set_parser = commands.add_parser("set", help="change a page's title, sources, prompt, deny list or TTL")
    set_parser.add_argument("page_id")
    set_parser.add_argument("--title")
    set_parser.add_argument("--source", nargs="+", metavar="FILE")
    set_parser.add_argument("--prompt-file")
    set_parser.add_argument("--deny", nargs="*", metavar="WORD")
    set_parser.add_argument("--ttl")
    set_parser.set_defaults(func=cmd_set)
    args = parser.parse_args()
    try:
        return args.func(args)
    except (Failure, OSError, UnicodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
