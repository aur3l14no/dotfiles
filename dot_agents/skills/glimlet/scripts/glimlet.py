#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Publish local HTML artifacts to Glimlet.

The CLI stays standard-library only so the skill can be copied around without
an install step.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
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


class CliError(Exception):
    pass


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = {} if getattr(args, "dry_run", False) and args.command in {"share", "publish", "update"} else load_config()
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
    parser.add_argument(
        "--title",
        required=require_title,
        help="Human-readable title shown in list/history views.",
    )
    parser.add_argument("--ttl", help="TTL such as 7d, 12h, or seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect local upload files without configuration or network access.")
    parser.add_argument("--metadata-json")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(include_default_ttl=include_default_ttl, require_title=require_title)


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
    if not args.new and (id_file(path).exists() or id_file(path).is_symlink()):
        args.args = [str(path)]
        return cmd_update(args, config)
    args.require_title = True
    return cmd_publish(args, config)


def save_marker(path: Path, response: Dict[str, Any]) -> Dict[str, Any]:
    try:
        marker = id_file(path)
        if marker.is_symlink():
            raise OSError("marker is a symbolic link")
        marker.write_text(f"{response['id']}\n", encoding="utf-8")
    except OSError as error:
        response["warning"] = (
            f"Upload succeeded, but could not save marker {id_file(path)}: {error}. "
            f"Keep URL {response['url']} and ID {response['id']}; "
            "use update PAGE_ID PATH to restore the association."
        )
    return response


def cmd_publish(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    path = artifact_path(args.path)
    response = upload(config, "POST", "/api/pages", path, args)
    return response if args.dry_run else save_marker(path, response)


def cmd_update(args: argparse.Namespace, config: Dict[str, Any]) -> Dict[str, Any]:
    if len(args.args) == 1:
        path = artifact_path(args.args[0])
        page_id = read_page_id(path)
    elif len(args.args) == 2:
        page_id = args.args[0]
        path = artifact_path(args.args[1])
    else:
        raise CliError("update expects PATH or PAGE_ID PATH.")

    response = upload(config, "PUT", f"/api/pages/{page_id}", path, args)
    return response if args.dry_run else save_marker(path, response)


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
    fields, files = artifact_payload(artifact)
    title = args.title.strip() if args.title else None
    if args.require_title and not title:
        raise CliError("--title is required.")
    if title:
        fields.append(("title", title))
    if args.metadata_json:
        try:
            json.loads(args.metadata_json)
        except json.JSONDecodeError as error:
            raise CliError(f"Invalid --metadata-json: {error.msg}")
        fields.append(("metadata_json", args.metadata_json))
    if args.ttl:
        fields.append(("ttl_seconds", str(duration(args.ttl))))
    elif args.include_default_ttl and not args.dry_run:
        fields.append(("ttl_seconds", str(config["default_ttl_seconds"])))

    if args.dry_run:
        return {
            "dry_run": True,
            "action": "created" if method == "POST" else "updated",
            "page_id": path.rsplit("/", 1)[-1] if method == "PUT" else None,
            "files": [{"path": name, "size_bytes": len(data)} for _, name, _, data in files],
            "size_bytes": sum(len(data) for _, _, _, data in files),
        }
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
    response["action"] = "created" if method == "POST" else "updated"
    return response


def artifact_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().absolute()
    if path.is_symlink():
        raise CliError(f"Symbolic links are not supported: {path}")
    if not path.exists() or not (path.is_file() or path.is_dir()):
        raise CliError(f"Path must point to a local web artifact: {path}")
    return path


def artifact_payload(path: Path) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str, str, bytes]]]:
    if path.is_file():
        if path.suffix.lower() not in {".html", ".htm"}:
            raise CliError("A single-file artifact must be .html or .htm.")
        data = path.read_bytes()
        check_size(len(data))
        return [], [("artifact", path.name, content_type(path), data)]

    if not (path / "index.html").is_file():
        raise CliError(f"Artifact directory must contain index.html: {path / 'index.html'}")

    files: List[Tuple[str, str, str, bytes]] = []
    manifest: List[Dict[str, str]] = []
    total_size = 0
    for index, file_path in enumerate(iter_files(path)):
        data = file_path.read_bytes()
        total_size += len(data)
        check_size(total_size)
        field = f"file_{index}"
        relative_path = file_path.relative_to(path).as_posix()
        mime = content_type(file_path)
        files.append((field, relative_path, mime, data))
        manifest.append({"field": field, "path": relative_path, "content_type": mime})

    return [("manifest_json", json.dumps(manifest, separators=(",", ":")))], files


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


def id_file(path: Path) -> Path:
    return path / ".glimlet_id" if path.is_dir() else path.with_name(f"{path.name}.glimlet_id")


def read_page_id(path: Path) -> str:
    marker = id_file(path)
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
    if args.json or result.get("dry_run") or args.command not in {"share", "publish", "update", "list"}:
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


def single_line(value: Any) -> str:
    return " ".join(str(value).split())


if __name__ == "__main__":
    raise SystemExit(main())
