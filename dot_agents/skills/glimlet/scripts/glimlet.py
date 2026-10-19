#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Publish local HTML artifacts and Markdown documents to Glimlet.

The CLI stays standard-library only so the skill can be copied around without
an install step.
"""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CONFIG_PATH = Path.home() / ".config" / "glimlet" / "config.toml"
DEFAULT_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
# Content going public must not carry these (#3); private uploads are not checked.
LOCAL_PATHS = ["/Users/", "/home/", "~/", "file://"]
DATA_TYPES = {".json": "application/json", ".md": "text/markdown", ".txt": "text/plain"}
ALIAS_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
# A private block is a top-level Obsidian callout, `> [!private]`, through its last `>` line (#10).
PRIVATE_BLOCK = re.compile(r" {0,3}>[ \t]*\[!private\]", re.IGNORECASE)
PRIVATE_MARKER = re.compile(r">[ \t]*\[!private\]", re.IGNORECASE)
QUOTE_LINE = re.compile(r" {0,3}>")
FRONTMATTER = re.compile(r"---\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|$)", re.S)
# A Markdown page (#8) is this stub plus the document as ./data, rendered by the built-in viewer.
VIEWER_STUB = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' https: data:; connect-src 'self'; base-uri 'none'; form-action 'none'">
<title>{title}</title>
<link rel="stylesheet" href="/_v/markdown/v1/viewer.css">
<script type="module" src="/_v/markdown/v1/viewer.js"></script>
</head>
<body><main id="doc"><noscript>This page needs JavaScript.</noscript></main></body>
</html>
"""


class CliError(Exception):
    pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        local = args.command == "strip" or (getattr(args, "dry_run", False) and args.command in {"share", "publish", "update"})
        config = {} if local else load_config()
        result = args.func(args, config)
        print_result(result, args)
        return 0
    except (CliError, OSError, UnicodeError) as error:
        if getattr(args, "json", False):
            print(json.dumps({"error": {"message": str(error)}}))
        else:
            print(f"error: {error}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="glimlet", description="Publish local artifacts to Glimlet.")
    sub = parser.add_subparsers(dest="command", required=True)

    share = sub.add_parser("share", help="Create or update using the local page marker.")
    share.add_argument("path", metavar="PATH")
    share.add_argument("--new", action="store_true", help="Create a separate page.")
    add_upload_flags(share)
    share.set_defaults(func=cmd_share)

    publish = sub.add_parser("publish", help="Create a page from a local web artifact.")
    publish.add_argument("path", metavar="PATH")
    add_upload_flags(publish, require_title=True)
    publish.set_defaults(func=cmd_publish)

    update = sub.add_parser("update", help="Update a page. Usage: update PATH or update PAGE_ID PATH.")
    update.add_argument("args", nargs="+", metavar="ARG")
    add_upload_flags(update)
    update.set_defaults(func=cmd_update)

    list_cmd = sub.add_parser("list", help="List pages with titles.")
    list_cmd.add_argument("--limit", type=int, default=20)
    list_cmd.add_argument("--cursor")
    list_cmd.add_argument("--json", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    set_cmd = sub.add_parser("set", help="Change a page's title, metadata or settings without uploading.")
    set_cmd.add_argument("page_id")
    set_cmd.add_argument("--title")
    set_cmd.add_argument("--metadata-json", help="Replaces all metadata; null clears it.")
    set_cmd.add_argument("--private", action="store_true", help="Make the page private. To publish it, upload it again with --public.")
    set_cmd.add_argument("--expect-every", help="How often the page is written, such as 1h; enables freshness alerts.")
    set_cmd.add_argument("--grace", help="Extra time before a late page counts as lost (default 15m).")
    set_cmd.add_argument("--no-expect", action="store_true", help="Turn freshness alerts off.")
    set_cmd.add_argument("--json", action="store_true")
    set_cmd.set_defaults(func=cmd_set)

    data = sub.add_parser("data", help="Replace a directory page's data document (.json, .md or .txt).")
    data.add_argument("page_id")
    data.add_argument("file")
    data.add_argument("--ttl", help="Keep the page live at least this long, such as 7d.")
    data.add_argument("--strip", action="store_true", help="Upload a .md file without its > [!private] blocks.")
    add_check_flags(data)
    data.add_argument("--json", action="store_true")
    data.set_defaults(func=cmd_data)

    strip = sub.add_parser("strip", help="Print a Markdown file without its > [!private] blocks.")
    strip.add_argument("file")
    strip.add_argument("--json", action="store_true")
    strip.set_defaults(func=lambda a, c: {"text": strip_markdown(markdown_text(artifact_path(a.file)), a.file)})

    alias = sub.add_parser("alias", help="Point a stable name at a page: /a/NAME/.")
    alias_sub = alias.add_subparsers(dest="alias_command", required=True)
    alias_set = alias_sub.add_parser("set", help="Point NAME at PAGE_ID. The name resolves on the public host only with --public.")
    alias_set.add_argument("name")
    alias_set.add_argument("page_id")
    scope = alias_set.add_mutually_exclusive_group()
    scope.add_argument("--public", action="store_true", help="Also resolve the name on the public host.")
    scope.add_argument("--private", action="store_true", help="Resolve the name only behind Access again.")
    alias_rm = alias_sub.add_parser("rm", help="Remove a name; the page stays.")
    alias_rm.add_argument("name")
    alias_list = alias_sub.add_parser("list", help="List names and their pages.")
    for command in (alias_set, alias_rm, alias_list):
        command.add_argument("--json", action="store_true")
    alias.set_defaults(func=cmd_alias)

    info = sub.add_parser("info", help="Show page metadata.")
    info.add_argument("page_id")
    info.add_argument("--json", action="store_true")
    info.set_defaults(func=lambda a, c: api(c, "GET", f"/api/pages/{a.page_id}"))

    expire = sub.add_parser("expire", help="Expire a page immediately.")
    expire.add_argument("page_id")
    expire.add_argument("--yes", action="store_true")
    expire.add_argument("--json", action="store_true")
    expire.set_defaults(func=cmd_expire)

    prune = sub.add_parser("prune", help="Prune old or large content while keeping metadata.")
    prune.add_argument("--expired-older-than")
    prune.add_argument("--larger-than")
    prune.add_argument("--include-active", action="store_true")
    prune.add_argument("--dry-run", action="store_true")
    prune.add_argument("--yes", action="store_true")
    prune.add_argument("--json", action="store_true")
    prune.set_defaults(func=cmd_prune)
    return parser


def add_upload_flags(
    parser: argparse.ArgumentParser,
    include_default_ttl: bool = True,
    require_title: bool = False,
) -> None:
    parser.add_argument("--title", help="Human-readable title shown in list/history views. A Markdown document can supply its own.")
    parser.add_argument("--ttl", help="TTL such as 7d, 12h, or seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect local upload files without configuration or network access.")
    parser.add_argument("--metadata-json")
    visibility = parser.add_mutually_exclusive_group()
    visibility.add_argument("--private", action="store_true", help="Only readers who pass Access can open it.")
    visibility.add_argument("--public", action="store_true", help="Publish a private page; runs the checks.")
    parser.add_argument("--expect-every", help="How often the page is written, such as 1h; enables freshness alerts.")
    parser.add_argument("--grace", help="Extra time before a late page counts as lost (default 15m).")
    parser.add_argument("--alias", metavar="NAME", help="Point this permalink at the page after uploading.")
    parser.add_argument("--session-url", help="Record the agent session or thread that made the page.")
    parser.add_argument("--strip", action="store_true", help="Drop > [!private] blocks from the Markdown being uploaded; keeps its own marker.")
    add_check_flags(parser)
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(include_default_ttl=include_default_ttl, require_title=require_title)


def add_check_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--deny", action="append", default=[], metavar="WORD", help="Refuse to publish content containing WORD.")
    parser.add_argument("--skip-checks", action="store_true", help="Publish despite matches. Only for a person who has looked at them.")


def load_config() -> Dict[str, Any]:
    config = read_toml(CONFIG_PATH)
    base_url = os.environ.get("GLIMLET_BASE_URL") or str(config.get("base_url", "")).strip()
    token = os.environ.get("GLIMLET_ADMIN_TOKEN") or str(config.get("admin_token", "")).strip()
    default_ttl = os.environ.get("GLIMLET_DEFAULT_TTL_SECONDS") or config.get("default_ttl_seconds", DEFAULT_TTL_SECONDS)

    if not base_url:
        raise CliError(f"Missing GLIMLET_BASE_URL or {CONFIG_PATH}")
    if not token:
        raise CliError(f"Missing GLIMLET_ADMIN_TOKEN or admin_token in {CONFIG_PATH}")
    try:
        ttl_seconds = int(default_ttl)
    except (TypeError, ValueError):
        raise CliError("default_ttl_seconds must be an integer.")

    return {
        "base_url": base_url.rstrip("/"),
        "admin_token": token,
        "default_ttl_seconds": ttl_seconds,
    }


def read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except tomllib.TOMLDecodeError:
        raise CliError(f"Invalid TOML configuration: {path}")


def cmd_share(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    path = artifact_path(args.path)
    marker = id_file(path, args.strip)
    if not args.new and (marker.exists() or marker.is_symlink()):
        args.args = [str(path)]
        return cmd_update(args, config)
    args.require_title = True
    return cmd_publish(args, config)


def save_marker(path: Path, response: Dict[str, Any], strip: bool = False) -> Dict[str, Any]:
    marker = id_file(path, strip)
    try:
        if marker.is_symlink():
            raise OSError("marker is a symbolic link")
        marker.write_text(f"{response['id']}\n", encoding="utf-8")
    except OSError as error:
        add_warning(response,
            f"Upload succeeded, but could not save marker {marker}: {error}. "
            f"Keep URL {response['url']} and ID {response['id']}; "
            "use update PAGE_ID PATH to restore the association.")
    return response


def add_warning(response: Dict[str, Any], warning: str) -> None:
    response["warning"] = f"{response['warning']} {warning}" if response.get("warning") else warning


def cmd_publish(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    path = artifact_path(args.path)
    response = upload(config, "POST", "/api/pages", path, args)
    return response if args.dry_run else save_marker(path, response, args.strip)


def cmd_update(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    if len(args.args) == 1:
        path = artifact_path(args.args[0])
        page_id = read_page_id(path, args.strip)
    elif len(args.args) == 2:
        page_id = args.args[0]
        path = artifact_path(args.args[1])
    else:
        raise CliError("update expects PATH or PAGE_ID PATH.")

    response = upload(config, "PUT", f"/api/pages/{page_id}", path, args)
    return response if args.dry_run else save_marker(path, response, args.strip)


def cmd_set(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    body: Dict[str, Any] = {}
    if args.title is not None:
        body["title"] = args.title
    if args.metadata_json is not None:
        body["metadata"] = parse_json(args.metadata_json, "--metadata-json")
    if args.private:
        body["visibility"] = "private"
    if args.no_expect:
        body["freshness"] = None
    elif args.expect_every:
        body["freshness"] = freshness_settings(args)
    elif args.grace:
        raise CliError("--grace needs --expect-every.")
    if not body:
        raise CliError("Nothing to change.")
    return api(config, "PATCH", f"/api/pages/{args.page_id}", body=body)


def cmd_data(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    path = artifact_path(args.file)
    kind = DATA_TYPES.get(path.suffix.lower())
    if not path.is_file() or not kind:
        raise CliError("Data must be a .json, .md or .txt file.")
    if args.strip and kind != "text/markdown":
        raise CliError("Only Markdown has private blocks; write the public version of other data yourself.")
    data = strip_markdown(markdown_text(path), path.name).encode("utf-8") if args.strip else path.read_bytes()
    check_size(len(data))
    if kind == "application/json":
        parse_json(data, str(path))
    if is_public(config, args.page_id):
        run_checks([(path.name, data)], args)
    ttl = duration(args.ttl) if args.ttl else config["default_ttl_seconds"]
    return api(config, "PUT", f"/api/pages/{args.page_id}/data", query={"ttl_seconds": str(ttl)}, data=data, content_type=kind)


def cmd_alias(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    if args.alias_command == "list":
        return api(config, "GET", "/api/aliases")
    name = urllib.parse.quote(args.name, safe="")
    if args.alias_command == "rm":
        return api(config, "DELETE", f"/api/aliases/{name}")
    body: Dict[str, Any] = {"page_id": args.page_id}
    if args.public or args.private:
        body["public"] = args.public
    return api(config, "PUT", f"/api/aliases/{name}", body=body)


def cmd_list(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    query = {"limit": str(args.limit)}
    if args.cursor:
        query["cursor"] = args.cursor
    return api(config, "GET", "/api/pages", query=query)


def cmd_expire(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    if not args.yes:
        raise CliError("expire requires --yes.")
    return api(config, "POST", f"/api/pages/{args.page_id}/expire")


def cmd_prune(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    body: Dict[str, Any] = {"dry_run": args.dry_run or not args.yes}
    if args.expired_older_than:
        body["expired_older_than_seconds"] = duration(args.expired_older_than)
    if args.larger_than:
        body["min_size_bytes"] = size_bytes(args.larger_than)
    if args.include_active:
        if not args.larger_than:
            raise CliError("--include-active requires --larger-than.")
        if not args.yes:
            raise CliError("--include-active requires --yes.")
        body["include_active"] = True
    return api(config, "POST", "/api/prune", body=body)


def upload(config: Dict[str, Any], method: str, path: str, artifact: Path, args: argparse.Namespace) -> Dict[str, Any]:
    title = args.title.strip() if args.title else None
    markdown = artifact.is_file() and artifact.suffix.lower() == ".md"
    if markdown and not title and method == "POST":
        title = markdown_title(markdown_text(artifact))
    fields, files = artifact_payload(artifact, args.strip, title)
    if args.require_title and not title:
        raise CliError("--title is required" + (", or a frontmatter title or # heading in the document." if markdown else "."))
    if args.alias and not ALIAS_NAME.fullmatch(args.alias):
        raise CliError("--alias takes lowercase letters, digits and hyphens, starting with a letter or digit (at most 63).")
    if title:
        fields.append(("title", title))
    if args.private or args.public:
        fields.append(("visibility", "private" if args.private else "public"))
    if args.expect_every:
        fields += [(key, str(value)) for key, value in freshness_settings(args).items()]
    elif args.grace:
        raise CliError("--grace needs --expect-every.")
    if args.metadata_json:
        try:
            metadata = json.loads(args.metadata_json)
        except json.JSONDecodeError as error:
            raise CliError(f"Invalid --metadata-json: {error.msg}")
    source = source_pointer(artifact, args.session_url)
    if args.ttl:
        fields.append(("ttl_seconds", str(duration(args.ttl))))
    elif args.include_default_ttl and not args.dry_run:
        fields.append(("ttl_seconds", str(config["default_ttl_seconds"])))

    if args.dry_run:
        return {
            "dry_run": True,
            "action": "created" if method == "POST" else "updated",
            "page_id": path.rsplit("/", 1)[-1] if method == "PUT" else None,
            "title": title,
            "files": [{"path": name, "size_bytes": len(data)} for _, name, _, data in files],
            "size_bytes": sum(len(data) for _, _, _, data in files),
            "check_findings": find_problems([(name, data) for _, name, _, data in files], args.deny),
            "source": source or None,
        }
    needs_page = method == "PUT" and (not (args.public or args.private) or (source and not args.metadata_json))
    page = api(config, "GET", path) if needs_page else {}
    if args.metadata_json:
        fields.append(("metadata_json", json.dumps({"source": source, **metadata}) if source and isinstance(metadata, dict) else args.metadata_json))
    elif source and isinstance(page.get("metadata") or {}, dict):
        # Merge, so recording the source never drops the page's other metadata.
        fields.append(("metadata_json", json.dumps({**(page.get("metadata") or {}), "source": source})))
    going_public = args.public or (not args.private and (method == "POST" or page.get("visibility") != "private"))
    if going_public:
        run_checks([(name, data) for _, name, _, data in files], args)
    content_type, data = multipart(fields, files)
    response = api(config, method, path, data=data, content_type=content_type)
    page_id = response.get("id")
    url = response.get("url")
    try:
        parsed_url = urllib.parse.urlsplit(url) if isinstance(url, str) else None
        valid_url = parsed_url and parsed_url.scheme in {"https", "http"} and parsed_url.netloc
    except ValueError:
        valid_url = False
    if not isinstance(page_id, str) or not page_id.strip() or not valid_url:
        raise CliError("Upload response lacks a valid page ID or URL; the server may have saved the page. Check list before retrying.")
    if method == "PUT" and page_id != path.rsplit("/", 1)[-1]:
        raise CliError("Upload response page ID does not match the update target. Check list before retrying.")
    if args.private and response.get("visibility") != "private":
        raise CliError(f"The server did not confirm --private, so {url} may be public. Expire it with: expire {page_id} --yes")
    response["action"] = "created" if method == "POST" else "updated"
    if args.alias:
        try:
            response["alias"] = api(config, "PUT", f"/api/aliases/{args.alias}", body={"page_id": page_id})
        except CliError as error:
            add_warning(response, f"Upload succeeded, but alias {args.alias} was not moved: {error}. "
                                  f"Run: alias set {args.alias} {page_id}")
    return response


def artifact_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().absolute()
    if path.is_symlink():
        raise CliError(f"Symbolic links are not supported: {path}")
    if not path.exists() or not (path.is_file() or path.is_dir()):
        raise CliError(f"Path must point to a local web artifact: {path}")
    return path


def artifact_payload(
    path: Path, strip: bool = False, title: Optional[str] = None,
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str, bytes]]]:
    if path.is_file() and path.suffix.lower() == ".md":
        return markdown_payload(path, strip, title)
    if path.is_file():
        if path.suffix.lower() not in {".html", ".htm"}:
            raise CliError("A single-file artifact must be .html, .htm or .md.")
        if strip:
            raise CliError("HTML has no private blocks; write its public version separately.")
        data = path.read_bytes()
        check_size(len(data))
        return [], [("artifact", path.name, content_type(path), data)]

    if not (path / "index.html").is_file():
        raise CliError(f"Artifact directory must contain index.html: {path / 'index.html'}")

    files: List[Tuple[str, str, str, bytes]] = []
    manifest: List[Dict[str, str]] = []
    total_size = 0
    stripped = 0
    for index, file_path in enumerate(iter_files(path)):
        if strip and file_path.suffix.lower() == ".md":
            data = strip_markdown(markdown_text(file_path), file_path.relative_to(path).as_posix()).encode("utf-8")
            stripped += 1
        else:
            data = file_path.read_bytes()
        total_size += len(data)
        check_size(total_size)
        field = f"file_{index}"
        relative_path = file_path.relative_to(path).as_posix()
        mime = content_type(file_path)
        files.append((field, relative_path, mime, data))
        manifest.append({"field": field, "path": relative_path, "content_type": mime})

    if strip and not stripped:
        raise CliError(f"--strip found no .md files in {path}; only Markdown has private blocks.")
    return [("manifest_json", json.dumps(manifest, separators=(",", ":")))], files


def markdown_payload(path: Path, strip: bool, title: Optional[str]) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str, bytes]]]:
    text = markdown_text(path)
    data = (strip_markdown(text, path.name) if strip else text).encode("utf-8")
    stub = VIEWER_STUB.format(title=html.escape(title or markdown_title(text) or path.stem)).encode("utf-8")
    check_size(len(stub) + len(data))
    files = [("file_0", "index.html", "text/html; charset=utf-8", stub), ("file_1", "data", "text/markdown; charset=utf-8", data)]
    manifest = [{"field": field, "path": name, "content_type": mime} for field, name, mime, _ in files]
    return [("manifest_json", json.dumps(manifest, separators=(",", ":")))], files


def markdown_title(text: str) -> Optional[str]:
    """A frontmatter `title`, else the first `# ` heading."""
    front = FRONTMATTER.match(text)
    found = front and re.search(r"^title:[ \t]*(.+?)[ \t]*$", front.group(1), re.M)
    if found and found.group(1).strip("\"'"):
        return found.group(1).strip("\"'")
    heading = re.search(r"^#[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", text[front.end() if front else 0:], re.M)
    return heading.group(1) if heading else None


def markdown_text(path: Path) -> str:
    if path.suffix.lower() != ".md" or not path.is_file():
        raise CliError(f"Only .md files have private blocks: {path}")
    return path.read_text(encoding="utf-8")


def strip_markdown(text: str, name: str) -> str:
    """Drop every top-level `> [!private]` block, or refuse when one cannot be dropped exactly.

    Markdown carries a quote on to a following line that lacks `>`, so a block must end at a blank
    line. Markers count inside code blocks too: guessing wrong about code would publish a block.
    """
    lines = text.splitlines(keepends=True)
    kept: List[str] = []
    index = 0
    while index < len(lines):
        line, index = lines[index], index + 1
        if PRIVATE_BLOCK.match(line):
            if kept and QUOTE_LINE.match(kept[-1]):
                raise CliError(f"{name}:{index}: a private block must start its own quote; add a blank line before it.")
            while index < len(lines) and QUOTE_LINE.match(lines[index]):
                index += 1
            if index < len(lines) and lines[index].strip():
                raise CliError(f"{name}:{index + 1}: add a blank line before this line; Markdown would keep it in the private block above.")
        elif PRIVATE_MARKER.search(re.sub(r"(`+).*?\1", "", line)):
            raise CliError(f"{name}:{index}: a nested or indented [!private] block cannot be stripped; move it to the top level.")
        else:
            kept.append(line)
    return "".join(kept)


def source_pointer(path: Path, session_url: Optional[str]) -> Dict[str, Any]:
    """Where an upload came from (#11): git facts when PATH is in a work tree, never a local path."""
    source: Dict[str, Any] = {"session_url": session_url} if session_url else {}
    root = git(path if path.is_dir() else path.parent, "rev-parse", "--show-toplevel")
    if root is None:
        return source
    relative = Path(os.path.relpath(path.resolve(), Path(root).resolve())).as_posix()
    source["repo"] = normalize_remote(git(Path(root), "remote", "get-url", "origin") or "") or Path(root).name
    source["path"] = relative
    commit = git(Path(root), "rev-parse", "--verify", "--quiet", "HEAD")
    if commit:
        source["commit"] = commit
    # Markers change after every first upload, so they never count as changes.
    changes = git(Path(root), "status", "--porcelain", "--", relative, ":!*.glimlet_id")
    tracked = git(Path(root), "ls-files", "--", relative)
    if changes is not None and tracked is not None:
        source["dirty"] = bool(changes) or not tracked
    return source


def normalize_remote(url: str) -> Optional[str]:
    """The https form of a git remote, without credentials or .git; None for a local remote."""
    scp = re.fullmatch(r"(?:[^@/]+@)?([^:/]+):(?!/)(.+)", url)
    if scp and "://" not in url:
        host, path = scp.groups()
    else:
        try:
            parts = urllib.parse.urlsplit(url)
            host, path = parts.hostname, parts.path
        except ValueError:
            return None
        if parts.scheme not in {"https", "http", "ssh", "git", "git+ssh"} or not host:
            return None
    path = path.strip("/").removesuffix(".git")
    return f"https://{host}/{path}" if path else None


def git(cwd: Path, *args: str) -> Optional[str]:
    try:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def find_problems(files: List[Tuple[str, bytes]], deny: List[str]) -> List[str]:
    problems = []
    for name, data in files:
        text = data.decode("utf-8", errors="ignore")
        problems += [f"{name}: contains {term!r}" for term in LOCAL_PATHS if term in text]
        problems += [f"{name}: contains denied {word!r}" for word in deny if word and word.lower() in text.lower()]
    return problems


def run_checks(files: List[Tuple[str, bytes]], args: argparse.Namespace) -> None:
    problems = find_problems(files, args.deny)
    if problems and not args.skip_checks:
        raise CliError("Checks failed, nothing uploaded. Fix the content; never work around a check:\n"
                       + "\n".join(f"  - {problem}" for problem in problems))


def is_public(config: Dict[str, Any], page_id: str) -> bool:
    return api(config, "GET", f"/api/pages/{page_id}").get("visibility") != "private"


def freshness_settings(args: argparse.Namespace) -> Dict[str, int]:
    settings = {"interval_seconds": duration(args.expect_every)}
    if args.grace:
        settings["grace_seconds"] = duration(args.grace)
    return settings


def parse_json(value: Any, label: str) -> Any:
    try:
        return json.loads(value)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise CliError(f"Invalid JSON in {label}: {error}")


def iter_files(root: Path) -> Iterable[Path]:
    def walk_error(error: OSError) -> None:
        raise error

    for current_root, dirnames, filenames in os.walk(root, onerror=walk_error):
        for name in dirnames + filenames:
            if not excluded(name) and (Path(current_root) / name).is_symlink():
                raise CliError(f"Symbolic links are not supported: {Path(current_root) / name}")
        dirnames[:] = sorted(name for name in dirnames if not excluded(name))
        for filename in sorted(filenames):
            if not excluded(filename):
                yield Path(current_root) / filename


def excluded(name: str) -> bool:
    return (
        name in {".git", "__pycache__", ".DS_Store", ".env", ".glimlet_id"}
        or name.startswith(".env.")
        or name.endswith(".glimlet_id")
        or name.endswith("~")
    )


def check_size(size: int) -> None:
    if size > MAX_UPLOAD_BYTES:
        raise CliError(f"Artifact exceeds 5 MiB limit ({size} bytes).")


def id_file(path: Path, strip: bool = False) -> Path:
    name = ".strip.glimlet_id" if strip else ".glimlet_id"
    return path / name if path.is_dir() else path.with_name(f"{path.name}{name}")


def read_page_id(path: Path, strip: bool = False) -> str:
    marker = id_file(path, strip)
    if marker.is_symlink():
        raise CliError(f"Symbolic links are not supported: {marker}")
    if not marker.exists():
        raise CliError(f"Missing Glimlet id file: {marker}")
    page_id = marker.read_text(encoding="utf-8").strip()
    if not page_id:
        raise CliError(f"Glimlet id file is empty: {marker}")
    return page_id


def content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    if not guessed and path.suffix.lower() in {".js", ".mjs"}:
        guessed = "text/javascript"
    if guessed and guessed.startswith("text/"):
        return f"{guessed}; charset=utf-8"
    return guessed or "application/octet-stream"


def api(
    config: Dict[str, Any],
    method: str,
    path: str,
    body: Optional[Dict[str, Any]] = None,
    query: Optional[Dict[str, str]] = None,
    data: Optional[bytes] = None,
    content_type: Optional[str] = None,
) -> Dict[str, Any]:
    headers = {
        "authorization": f"Bearer {config['admin_token']}",
        "user-agent": "glimlet-cli/0.1",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        content_type = "application/json"
    if content_type:
        headers["content-type"] = content_type

    url = f"{config['base_url']}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
            detail = body.get("error") if isinstance(body, dict) else None
            message = detail.get("message") if isinstance(detail, dict) else None
            message = message or raw
        except json.JSONDecodeError:
            message = raw or error.reason
        raise CliError(f"HTTP {error.code}: {message}")
    except urllib.error.URLError as error:
        raise CliError(f"Network error: {error.reason}")

    try:
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise CliError("Expected a JSON object response.")
        return result
    except json.JSONDecodeError:
        raise CliError(f"Expected JSON response, got: {raw[:200]}")


def multipart(fields: List[Tuple[str, str]], files: List[Tuple[str, str, str, bytes]]) -> Tuple[str, bytes]:
    boundary = f"----glimlet-{secrets.token_hex(16)}"
    parts: List[bytes] = []

    for name, value in fields:
        parts += [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{header(name)}"\r\n\r\n'.encode(),
            value.encode("utf-8"),
            b"\r\n",
        ]
    for field, filename, mime, data in files:
        parts += [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{header(field)}"; filename="{header(filename)}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            data,
            b"\r\n",
        ]

    parts.append(f"--{boundary}--\r\n".encode())
    return f"multipart/form-data; boundary={boundary}", b"".join(parts)


def header(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def duration(value: str) -> int:
    text = value.strip().lower()
    if text.isdigit():
        return int(text)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    if text[-1:] not in multipliers or not text[:-1].isdigit():
        raise CliError(f"Invalid duration: {value}")
    return int(text[:-1]) * multipliers[text[-1]]


def size_bytes(value: str) -> int:
    text = value.strip().lower()
    if text.isdigit():
        return int(text)
    units = {"mb": 1024 * 1024, "kb": 1024, "m": 1024 * 1024, "k": 1024, "b": 1}
    for suffix, multiplier in units.items():
        if text.endswith(suffix) and text[:-len(suffix)].isdigit():
            return int(text[:-len(suffix)]) * multiplier
    raise CliError(f"Invalid size: {value}")


def print_result(result: Dict[str, Any], args: argparse.Namespace) -> None:
    if args.command == "strip" and not args.json:
        sys.stdout.write(result["text"])
    elif args.json or result.get("dry_run") or args.command not in {"share", "publish", "update", "list"}:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.command == "list":
        for page in result.get("pages", []):
            title = single_line(page.get("title") or "(untitled)")
            print("\t".join([
                title,
                str(page.get("status")),
                str(page.get("updated_at")),
                str(page.get("id")),
                str(page.get("url")),
            ]))
        if result.get("next_cursor"):
            print(f"next_cursor: {result['next_cursor']}")
    else:
        print(f"action: {result.get('action')}")
        if result.get("warning"):
            print(f"warning: {result['warning']}", file=sys.stderr)
        print(f"url: {result.get('url')}")
        print(f"id: {result.get('id')}")
        if result.get("title"):
            print(f"title: {result.get('title')}")
        if result.get("expires_at"):
            print(f"expires_at: {result.get('expires_at')}")
        if result.get("alias"):
            print(f"alias: {result['alias'].get('url') or result['alias'].get('name')}")


def single_line(value: Any) -> str:
    return " ".join(str(value).split())


if __name__ == "__main__":
    raise SystemExit(main())
