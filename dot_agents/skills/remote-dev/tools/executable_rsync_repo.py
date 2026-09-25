#!/usr/bin/env python3
"""Mirror a Git worktree between the current directory and another endpoint.

Contract:

* The selected source worktree is authoritative. ``push`` selects the current
  worktree; ``pull`` selects the other endpoint. Destination edits are not protected.
* Git-ignored destination extras are preserved.
* A source ``filter=lfs`` pointer is present logically but is not transferred.
  Its destination path must already exist as a file or symlink and is kept as-is.
* File/directory path blockers are errors; this script never removes them.
* Rsync transfers the final worktree, while Git transports the source HEAD and
  staged tree. The destination HEAD is detached at that commit and its staged
  tree mirrors the source.
  Named branches and branch/upstream configuration remain destination-local.
* Missing destination submodule worktrees are initialized on apply.
* Non-ignored destination Git roots absent from the source stop the sync.
* The command is a dry-run unless ``-y`` is supplied.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

SAFE_HOST = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9_.-]+$")
SAFE_REMOTE_PATH = re.compile(r"^/[A-Za-z0-9_./+,@=-]+$")
LFS_VERSION = "version https://git-lfs.github.com/spec/v1"
SYNC_HEAD = "refs/rsync-repo/head"
SYNC_INDEX = "refs/rsync-repo/index"


@dataclass(frozen=True)
class Endpoint:
    raw: str
    host: str | None
    path: str

    @property
    def remote(self) -> bool:
        return self.host is not None

    def subpath(self, rel: str = "") -> str:
        if not rel:
            return self.path
        validate_relpath(rel)
        if self.remote:
            return str(PurePosixPath(self.path) / PurePosixPath(rel))
        return str(Path(self.path) / rel)

    def rsync_arg(self) -> str:
        path = self.path.rstrip("/") + "/"
        return f"{self.host}:{path}" if self.remote else path

    def git_arg(self, rel: str = "") -> str:
        path = self.subpath(rel)
        return f"{self.host}:{path}" if self.remote else path


@dataclass(frozen=True)
class GitSnapshot:
    root: str
    head_oid: str
    index_tree: str


def run_capture(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_data: bytes | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=cwd, input=input_data, capture_output=True, env=env)
    if check and result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(result.returncode)
    return result


def run_at(
    endpoint: Endpoint,
    args: list[str],
    *,
    rel: str = "",
    input_data: bytes | None = None,
    check: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if env and endpoint.remote:
        raise ValueError("Remote command environments must be expressed in args")
    if endpoint.remote:
        command = "cd " + shlex.quote(endpoint.subpath(rel)) + " && " + shlex.join(args)
        return run_capture(
            ["ssh", "--", endpoint.host or "", command],
            input_data=input_data,
            check=check,
        )
    return run_capture(
        args,
        cwd=Path(endpoint.subpath(rel)),
        input_data=input_data,
        check=check,
        env=env,
    )


def run_shell_at(
    endpoint: Endpoint,
    script: str,
    *,
    rel: str = "",
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if endpoint.remote:
        command = "cd " + shlex.quote(endpoint.subpath(rel)) + " && " + script
        return run_capture(["ssh", "--", endpoint.host or "", command], input_data=input_data)
    return run_capture(
        ["bash", "-lc", script],
        cwd=Path(endpoint.subpath(rel)),
        input_data=input_data,
    )


def parse_endpoint(value: str) -> Endpoint:
    if any(character in value for character in ("\0", "\n", "\r")):
        raise SystemExit(f"Refusing unsafe endpoint: {value!r}")
    if ":" in value and not value.startswith(("/", "./", "../")):
        host, path = value.split(":", 1)
        if not SAFE_HOST.fullmatch(host) or host.startswith("-"):
            raise SystemExit(f"Refusing unsafe SSH host: {host!r}")
        posix = PurePosixPath(path)
        if not posix.is_absolute() or ".." in posix.parts:
            raise SystemExit("Remote endpoint must use a normalized absolute path")
        normalized = str(posix)
        if normalized == "/":
            raise SystemExit("Refusing to use the remote filesystem root")
        if not SAFE_REMOTE_PATH.fullmatch(normalized):
            raise SystemExit("Remote path contains unsupported characters")
        return Endpoint(value, host, normalized)

    path = Path(value).expanduser().resolve(strict=False)
    if path == Path("/"):
        raise SystemExit("Refusing to use the local filesystem root")
    return Endpoint(value, None, str(path))


def validate_relpath(path: str) -> None:
    if not path or any(character in path for character in ("\0", "\n", "\r")):
        raise SystemExit(f"Refusing unsafe relative path: {path!r}")
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        raise SystemExit(f"Refusing unsafe relative path: {path!r}")


def decode_path(raw: bytes) -> str:
    path = raw.decode("utf-8", "surrogateescape")
    validate_relpath(path)
    return path


def split_nul(data: bytes) -> list[str]:
    return [decode_path(raw) for raw in data.split(b"\0") if raw]


def display(path: str) -> str:
    return path.encode("utf-8", "backslashreplace").decode("utf-8", "replace")


def emit(message: str = "", *, stderr: bool = False) -> None:
    print(message, file=sys.stderr if stderr else sys.stdout, flush=True)


def is_exact_git_root(endpoint: Endpoint, rel: str = "", *, report_failure: bool = False) -> bool:
    result = run_at(
        endpoint,
        ["sh", "-c", "pwd -P && git rev-parse --show-toplevel"],
        rel=rel,
        check=False,
    )
    if result.returncode != 0:
        if report_failure:
            sys.stderr.write(result.stderr.decode("utf-8", "replace"))
            raw = endpoint.raw if not rel else f"{endpoint.raw}/{display(rel)}"
            raise SystemExit(f"Failed to inspect Git worktree: {raw}")
        return False
    paths = result.stdout.decode().splitlines()
    if len(paths) != 2:
        if report_failure:
            raise SystemExit("Invalid Git worktree inspection output")
        return False
    physical, top = paths
    if endpoint.remote:
        return str(PurePosixPath(physical)) == str(PurePosixPath(top))
    return Path(physical).resolve() == Path(top).resolve()


def verify_git_root(endpoint: Endpoint, rel: str = "") -> None:
    if not is_exact_git_root(endpoint, rel, report_failure=True):
        raw = endpoint.raw if not rel else f"{endpoint.raw}/{display(rel)}"
        raise SystemExit(f"Endpoint is not an exact Git worktree root: {raw}")


def destination_git_roots_to_initialize(dest: Endpoint, roots: list[str]) -> list[str]:
    verify_git_root(dest)
    pending: list[str] = []
    for root in roots:
        if not root or is_exact_git_root(dest, root):
            continue
        raw = f"{dest.raw}/{display(root)}"
        is_directory = run_at(dest, ["test", "-d", root], check=False).returncode == 0
        exists = run_at(dest, ["test", "-e", root], check=False).returncode == 0
        is_link = run_at(dest, ["test", "-L", root], check=False).returncode == 0
        if not is_directory and (exists or is_link):
            raise SystemExit(f"Destination Git root path is not a directory: {raw}")
        if is_directory:
            bare = run_at(
                dest,
                ["git", "rev-parse", "--is-bare-repository"],
                rel=root,
                check=False,
            )
            if bare.returncode == 0 and bare.stdout.strip() == b"true":
                raise SystemExit(
                    "Destination Git root is bare; remove it and rerun so it can be "
                    f"initialized as a worktree: {raw}"
                )
            marker = f"{root}/.git"
            marker_exists = run_at(dest, ["test", "-e", marker], check=False).returncode == 0
            marker_is_link = run_at(dest, ["test", "-L", marker], check=False).returncode == 0
            if marker_exists or marker_is_link:
                raise SystemExit(f"Destination Git worktree is invalid: {raw}")
        pending.append(root)
    return pending


def initialize_destination_git_roots(dest: Endpoint, roots: list[str]) -> None:
    for root in roots:
        run_at(dest, ["mkdir", "-p", "--", root])
        run_at(dest, ["git", "init", "-q"], rel=root)
        verify_git_root(dest, root)


def ensure_submodules_initialized(source: Endpoint) -> None:
    result = run_at(source, ["git", "submodule", "status", "--recursive"], check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(result.returncode)
    missing: list[str] = []
    for line in result.stdout.decode("utf-8", "surrogateescape").splitlines():
        if line.startswith("-"):
            fields = line[1:].strip().split()
            if len(fields) >= 2:
                validate_relpath(fields[1])
                missing.append(fields[1])
    if missing:
        raise SystemExit("Submodules are not initialized: " + ", ".join(missing))


def list_git_roots(source: Endpoint) -> list[str]:
    ensure_submodules_initialized(source)
    roots = {""}
    result = run_at(
        source,
        [
            "git",
            "submodule",
            "foreach",
            "--recursive",
            "-q",
            'printf "%s\\n" "$displaypath"',
        ],
    )
    for line in result.stdout.decode("utf-8", "surrogateescape").splitlines():
        root = line.strip("/")
        if root:
            validate_relpath(root)
            roots.add(root)
    return sorted(roots, key=lambda root: (root.count("/") if root else -1, root))


def git_paths(source: Endpoint, root: str, args: list[str]) -> set[str]:
    result = run_at(source, ["git", "ls-files", "-z", *args], rel=root)
    return set(split_nul(result.stdout))


def gitlinks(source: Endpoint, root: str) -> set[str]:
    result = run_at(source, ["git", "ls-files", "-z", "--stage"], rel=root)
    paths: set[str] = set()
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, _, raw_path = record.partition(b"\t")
        if metadata.startswith(b"160000 "):
            paths.add(decode_path(raw_path))
    return paths


def reject_sparse_checkout(source: Endpoint, root: str) -> None:
    result = run_at(source, ["git", "ls-files", "-z", "-t"], rel=root)
    skipped = [
        decode_path(record[2:])
        for record in result.stdout.split(b"\0")
        if record and record[:2].upper() == b"S "
    ]
    if skipped:
        sample = ", ".join(display(path) for path in skipped[:8])
        raise SystemExit(f"Sparse/skip-worktree entries are unsupported: {sample}")


def source_files(source: Endpoint, roots: list[str]) -> set[str]:
    files: set[str] = set()
    nested_roots = {root for root in roots if root}
    for root in roots:
        reject_sparse_checkout(source, root)
        unmerged = split_nul(
            run_at(
                source,
                ["git", "diff", "--name-only", "--diff-filter=U", "-z"],
                rel=root,
            ).stdout
        )
        if unmerged:
            sample = ", ".join(display(path) for path in unmerged[:8])
            raise SystemExit(f"Unresolved index entries are unsupported: {sample}")
        candidates = git_paths(source, root, ["--cached", "--others", "--exclude-standard"])
        deleted = git_paths(source, root, ["--deleted"])
        links = gitlinks(source, root)
        for rel in sorted(candidates - deleted):
            if rel.endswith("/"):
                raise SystemExit("Embedded or collapsed directory is unsupported: " + display(rel))
            if rel in links:
                continue
            path = str(PurePosixPath(root) / rel) if root else rel
            if path in nested_roots:
                continue
            validate_relpath(path)
            files.add(path)
    return files


def classify_source_paths(source: Endpoint, paths: set[str]) -> tuple[set[str], set[str]]:
    regular = paths & find_paths(source, "-type f")
    links = paths & find_paths(source, "-type l")
    return regular, paths - regular - links


def create_git_snapshot(source: Endpoint, root: str) -> GitSnapshot:
    head_oid = source_head(source, root)
    index_tree = run_at(source, ["git", "write-tree"], rel=root).stdout.decode().strip()
    return GitSnapshot(root=root, head_oid=head_oid, index_tree=index_tree)


def source_head(source: Endpoint, root: str) -> str:
    return (
        run_at(source, ["git", "rev-parse", "--verify", "HEAD^{commit}"], rel=root)
        .stdout.decode()
        .strip()
    )


def find_paths(endpoint: Endpoint, predicate: str) -> set[str]:
    command = (
        "find . -xdev -mindepth 1 "
        + r"\( -path './.git' -o -path './*/.git' \) -prune -o "
        + predicate
        + " -print0"
    )
    result = run_shell_at(endpoint, command)
    paths: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = raw[2:] if raw.startswith(b"./") else raw
        paths.add(decode_path(path))
    return paths


def find_destination_files_and_git_roots(
    dest: Endpoint,
) -> tuple[set[str], set[str]]:
    command = (
        "find . -xdev -mindepth 1 "
        + r"\( -path './.git' \) -prune -o "
        + r"\( -name .git \) -print0 -prune -o "
        + r"\( -type f -o -type l \) -print0"
    )
    result = run_shell_at(dest, command)
    files: set[str] = set()
    git_roots: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        raw_path = raw[2:] if raw.startswith(b"./") else raw
        path = decode_path(raw_path)
        marker = PurePosixPath(path)
        if marker.name == ".git":
            root = str(marker.parent)
            validate_relpath(root)
            git_roots.add(root)
        else:
            files.add(path)
    return files, git_roots


def source_directories(paths: set[str]) -> set[str]:
    directories: set[str] = set()
    for path in paths:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            directories.add(str(parent))
            parent = parent.parent
    return directories


def route_path(path: str, roots_descending: list[str]) -> tuple[str, str]:
    for root in roots_descending:
        if root and (path == root or path.startswith(root + "/")):
            return root, path[len(root) + 1 :]
    return "", path


def git_attribute_values(
    source: Endpoint, paths: set[str], roots: list[str], attribute: str
) -> dict[str, str]:
    roots_descending = sorted(roots, key=len, reverse=True)
    by_root: dict[str, list[tuple[str, str]]] = {}
    for path in paths:
        root, rel = route_path(path, roots_descending)
        by_root.setdefault(root, []).append((path, rel))

    values: dict[str, str] = {}
    for root, entries in by_root.items():
        stdin = b"\0".join(rel.encode("utf-8", "surrogateescape") for _, rel in entries) + b"\0"
        result = run_at(
            source,
            ["git", "check-attr", "-z", "--stdin", attribute],
            rel=root,
            input_data=stdin,
        )
        fields = result.stdout.split(b"\0")
        if fields and fields[-1] == b"":
            fields.pop()
        if len(fields) % 3:
            raise SystemExit("Invalid git check-attr output")
        rel_to_full = {rel: full for full, rel in entries}
        for offset in range(0, len(fields), 3):
            rel = decode_path(fields[offset])
            value = fields[offset + 2].decode("utf-8", "surrogateescape")
            values[rel_to_full[rel]] = value
    return values


def lfs_paths(source: Endpoint, logical: set[str], roots: list[str]) -> set[str]:
    filters = git_attribute_values(source, logical, roots, "filter")
    unknown = {
        path: value
        for path, value in filters.items()
        if value not in {"unspecified", "unset", "lfs"}
    }
    if unknown:
        sample = ", ".join(
            f"{display(path)}={value}" for path, value in sorted(unknown.items())[:8]
        )
        raise SystemExit("Unknown Git filters are unsupported: " + sample)
    return {path for path in logical if filters.get(path) == "lfs"}


def lfs_pointer_paths(source: Endpoint, lfs: set[str], source_regular: set[str]) -> set[str]:
    candidates = sorted(lfs & source_regular)
    if not candidates:
        return set()
    stdin = b"".join(path.encode("utf-8", "surrogateescape") + b"\0" for path in candidates)
    script = rf'''
for path do
    file="./$path"
    size=$(wc -c <"$file") || continue
    test "$size" -lt 1024 || continue
    if awk '
        {{ sub(/\r$/, "") }}
        NR == 1 {{ version = ($0 == "{LFS_VERSION}") }}
        {{ penultimate = last; last = $0; count += 1 }}
        END {{
            valid_oid = penultimate ~ /^oid sha256:[0-9a-f]+$/ && length(penultimate) == 75
            valid_size = last ~ /^size [0-9]+$/
            exit !(count >= 3 && version && valid_oid && valid_size)
        }}
    ' "$file"; then
        printf '%s\000' "$path"
    fi
done
'''
    result = run_at(
        source,
        ["xargs", "-0", "sh", "-c", script, "sh"],
        input_data=stdin,
    )
    return set(split_nul(result.stdout))


def ignored_paths(
    paths: list[str],
    source: Endpoint,
    roots: list[str],
    *,
    directories: bool = False,
) -> set[str]:
    roots_descending = sorted(roots, key=len, reverse=True)
    by_root: dict[str, list[tuple[str, str]]] = {}
    for path in paths:
        root, rel = route_path(path, roots_descending)
        query = rel.rstrip("/") + "/" if directories else rel
        by_root.setdefault(root, []).append((path, query))
    ignored: set[str] = set()
    for root, entries in by_root.items():
        stdin = b"\0".join(rel.encode("utf-8", "surrogateescape") for _, rel in entries) + b"\0"
        result = run_at(
            source,
            ["git", "check-ignore", "--no-index", "-z", "--stdin"],
            rel=root,
            input_data=stdin,
            check=False,
        )
        if result.returncode not in {0, 1}:
            sys.stderr.write(result.stderr.decode("utf-8", "replace"))
            raise SystemExit(result.returncode)
        ignored_rel = set(split_nul(result.stdout))
        for full, rel in entries:
            if rel in ignored_rel:
                ignored.add(full)
    return ignored


def transfer_git_snapshot(source: Endpoint, dest: Endpoint, snapshot: GitSnapshot) -> None:
    if dest.remote:
        run_at(
            source,
            [
                "git",
                "push",
                "--atomic",
                "--force",
                "--no-verify",
                dest.git_arg(snapshot.root),
                f"+{snapshot.head_oid}:{SYNC_HEAD}",
                f"+{snapshot.index_tree}:{SYNC_INDEX}",
            ],
            rel=snapshot.root,
        )
        return

    run_at(
        dest,
        [
            "git",
            "fetch",
            "--no-tags",
            "--force",
            source.git_arg(snapshot.root),
            f"+HEAD:{SYNC_HEAD}",
        ],
        rel=snapshot.root,
    )
    fetched = run_at(dest, ["git", "rev-parse", SYNC_HEAD], rel=snapshot.root).stdout
    if fetched.decode().strip() != snapshot.head_oid:
        raise SystemExit(f"Source HEAD changed during sync: {snapshot.root or '.'}")
    has_index = (
        run_at(
            dest,
            ["git", "cat-file", "-e", f"{snapshot.index_tree}^{{tree}}"],
            rel=snapshot.root,
            check=False,
        ).returncode
        == 0
    )
    if not has_index:
        revisions = f"{snapshot.index_tree}\n^{snapshot.head_oid}\n".encode()
        pack = run_at(
            source,
            ["git", "pack-objects", "--stdout", "--revs", "--thin"],
            rel=snapshot.root,
            input_data=revisions,
        ).stdout
        run_at(
            dest,
            ["git", "index-pack", "--stdin", "--fix-thin"],
            rel=snapshot.root,
            input_data=pack,
        )
    run_at(dest, ["git", "update-ref", SYNC_INDEX, snapshot.index_tree], rel=snapshot.root)


def apply_git_snapshot(dest: Endpoint, snapshot: GitSnapshot) -> None:
    update_head = shlex.join(["git", "update-ref", "--no-deref", "HEAD", snapshot.head_oid])
    restore_index = shlex.join(["git", "read-tree", SYNC_INDEX])
    run_shell_at(dest, update_head + " && " + restore_index, rel=snapshot.root)


def verify_git_snapshot(dest: Endpoint, snapshot: GitSnapshot) -> None:
    inspect = "git rev-parse HEAD && git write-tree"
    actual = run_shell_at(dest, inspect, rel=snapshot.root).stdout.decode().splitlines()
    if len(actual) != 2:
        raise SystemExit(f"Invalid Git verification output: {snapshot.root or '.'}")
    head_oid, index_tree = actual
    if head_oid != snapshot.head_oid:
        raise SystemExit(f"Git HEAD commit differs after sync: {snapshot.root or '.'}")
    if index_tree != snapshot.index_tree:
        raise SystemExit(f"Git index differs after sync: {snapshot.root or '.'}")


def rsync_transfer(source: Endpoint, dest: Endpoint, paths: set[str], *, dry_run: bool) -> int:
    args = [
        "rsync",
        "-rzci",
        "--links",
        "--executability",
        "--delay-updates",
        "--from0",
        "--files-from=-",
    ]
    if dry_run:
        args.insert(1, "-n")
    args.extend(["--", source.rsync_arg(), dest.rsync_arg()])
    stdin = b"".join(path.encode("utf-8", "surrogateescape") + b"\0" for path in sorted(paths))
    return subprocess.run(args, input=stdin).returncode


def delete_files(dest: Endpoint, paths: list[str]) -> None:
    if not paths:
        return
    stdin = b"\0".join(path.encode("utf-8", "surrogateescape") for path in paths) + b"\0"
    if dest.remote:
        command = "cd " + shlex.quote(dest.path) + " && xargs -0 rm -f --"
        run_capture(["ssh", "--", dest.host or "", command], input_data=stdin)
    else:
        run_capture(["xargs", "-0", "rm", "-f", "--"], cwd=Path(dest.path), input_data=stdin)


def print_paths(title: str, paths: list[str], limit: int = 80) -> None:
    if not paths:
        return
    emit(f"\n{title} ({len(paths)})")
    for path in paths[:limit]:
        emit("  " + display(path))
    if len(paths) > limit:
        emit(f"  ... {len(paths) - limit} more")


def endpoint_label(endpoint: Endpoint) -> str:
    return endpoint.raw if endpoint.remote else endpoint.path


def destination_head_updates(
    dest: Endpoint, source_heads: dict[str, str], roots_to_initialize: list[str]
) -> list[str]:
    pending = set(roots_to_initialize)
    updates: list[str] = []
    for root, head_oid in source_heads.items():
        label = root or "."
        if root in pending:
            current = "(new)"
        else:
            result = run_at(
                dest,
                ["git", "rev-parse", "--verify", "HEAD^{commit}"],
                rel=root,
                check=False,
            )
            current = result.stdout.decode().strip() if result.returncode == 0 else "(none)"
        if current != head_oid:
            before = current if current.startswith("(") else current[:12]
            updates.append(f"{label}: {before} -> {head_oid[:12]}")
    return updates


def sync_repository(source: Endpoint, dest: Endpoint, *, apply: bool) -> int:
    emit("\nPhase: inspect source and destination")
    verify_git_root(source)
    roots = list_git_roots(source)
    roots_to_initialize = destination_git_roots_to_initialize(dest, roots)
    logical = source_files(source, roots)
    source_heads = {root: source_head(source, root) for root in roots}

    source_regular, missing_or_bad_source = classify_source_paths(source, logical)
    if missing_or_bad_source:
        raise SystemExit(
            "Source paths are missing or unsupported: "
            + ", ".join(display(path) for path in sorted(missing_or_bad_source)[:8])
        )
    source_special = find_paths(source, r"! \( -type f -o -type l -o -type d \)")
    nonignored_source_special = source_special - ignored_paths(
        sorted(source_special), source, roots
    )
    if nonignored_source_special:
        raise SystemExit(
            "Non-ignored source special nodes are unsupported: "
            + ", ".join(display(path) for path in sorted(nonignored_source_special)[:8])
        )

    lfs = lfs_paths(source, logical, roots)
    pointers = lfs_pointer_paths(source, lfs, source_regular)
    transfer = logical - pointers
    source_dirs = source_directories(logical)

    dest_files_links, dest_git_roots = find_destination_files_and_git_roots(dest)
    dest_dirs = find_paths(dest, "-type d")
    dest_special = find_paths(dest, r"! \( -type f -o -type l -o -type d \)")
    extra_git_roots = dest_git_roots - set(roots)
    remote_only_git_roots = {
        root
        for root in extra_git_roots
        if root not in logical
        and root not in source_dirs
        and not any(current.startswith(root + "/") for current in roots if current)
    }
    ignored_git_roots = ignored_paths(
        sorted(remote_only_git_roots), source, roots, directories=True
    )
    stale_git_roots = sorted(extra_git_roots - ignored_git_roots)
    file_blockers = sorted((dest_files_links | dest_special) & source_dirs)
    dir_blockers = sorted(dest_dirs & logical)
    special_blockers = sorted(dest_special & logical)
    missing_lfs = sorted(pointers - dest_files_links)

    dest_leaves = dest_files_links | dest_special
    extras = sorted(dest_leaves - logical)
    ignored = ignored_paths(extras, source, roots)
    special_extras = sorted((dest_special - logical) - ignored)
    delete_candidates = sorted((dest_files_links - logical) - ignored)
    head_updates = destination_head_updates(dest, source_heads, roots_to_initialize)

    errors: list[str] = []
    if stale_git_roots:
        errors.append("Destination contains non-ignored stale Git roots")
    if file_blockers:
        errors.append("Destination files/special nodes block source directories")
    if dir_blockers:
        errors.append("Destination directories block source files")
    if special_blockers:
        errors.append("Destination special nodes block source files")
    if missing_lfs:
        errors.append("Destination LFS paths are missing or not files/symlinks")
    if special_extras:
        errors.append("Non-ignored destination special nodes cannot be deleted safely")

    emit("\nPlan summary")
    emit(f"  Git roots: {len(roots)}")
    emit(f"  Source files: {len(logical)}")
    emit(f"  Files eligible for transfer: {len(transfer)}")
    emit(f"  Preserved LFS paths: {len(pointers)}")
    emit(f"  Destination files/links to delete: {len(delete_candidates)}")
    emit(f"  Destination ignored files/links kept: {len(ignored)}")
    print_paths("Destination Git worktrees to initialize", roots_to_initialize)
    print_paths("Destination Git HEAD updates", head_updates)
    print_paths("Preserved LFS paths", sorted(pointers))
    print_paths("Destination stale Git roots", stale_git_roots)
    print_paths("Destination file/special blockers", file_blockers)
    print_paths("Destination directory blockers", dir_blockers)
    print_paths("Destination special-node blockers", special_blockers)
    print_paths("Missing/invalid destination LFS paths", missing_lfs)
    print_paths("Non-ignored destination special nodes", special_extras)
    print_paths("Destination files/links to delete", delete_candidates)
    if errors:
        emit(f"\nErrors ({len(errors)})")
        for error in errors:
            emit("  " + error)
        emit("\nNo changes made.")
        return 2

    if not apply:
        emit("\nPhase: preview final worktree changes")
        rc = rsync_transfer(source, dest, transfer, dry_run=True)
        if rc != 0:
            emit("\nDry-run transfer check failed. No changes made.")
            return rc
        emit("\nGit object transfer size is not estimated in dry-run.")
        emit("Dry run only. Re-run with -y to apply a freshly generated plan.")
        return 0

    snapshots = [create_git_snapshot(source, root) for root in roots]
    try:
        emit("\nPhase: initialize destination Git worktrees")
        initialize_destination_git_roots(dest, roots_to_initialize)

        emit("\nPhase: transfer source Git HEAD and staged-tree objects")
        for snapshot in snapshots:
            transfer_git_snapshot(source, dest, snapshot)

        emit("\nPhase: transfer final worktree")
        rc = rsync_transfer(source, dest, transfer, dry_run=False)
        if rc != 0:
            raise SystemExit(rc)

        emit("\nPhase: delete extras and apply Git state")
        verify_git_root(dest)
        delete_files(dest, delete_candidates)
        deepest_first = sorted(
            snapshots,
            key=lambda snapshot: snapshot.root.count("/") + 1 if snapshot.root else 0,
            reverse=True,
        )
        for snapshot in deepest_first:
            apply_git_snapshot(dest, snapshot)
        for snapshot in deepest_first:
            verify_git_snapshot(dest, snapshot)
    except BaseException:
        emit(
            "\nApply failed after destination mutation began; Git refs, worktree files, "
            "or extras may be partially updated.",
            stderr=True,
        )
        raise

    emit("\nSync applied successfully.")
    emit(f"Deleted destination extras: {len(delete_candidates)}")
    emit(f"Verified Git roots: {len(snapshots)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror a Git worktree; the selected source is authoritative."
    )
    parser.add_argument(
        "direction",
        choices=("push", "pull"),
        help="push from the current worktree or pull from ENDPOINT",
    )
    parser.add_argument("-y", "--yes", action="store_true", help="apply the generated plan")
    parser.add_argument("endpoint", metavar="ENDPOINT", help="HOST:/absolute/path or local path")
    raw_args = sys.argv[1:] if argv is None else argv
    first_positional = next(
        (argument for argument in raw_args if argument not in {"-y", "--yes"}), None
    )
    if not any(argument in {"-h", "--help"} for argument in raw_args) and first_positional not in {
        "push",
        "pull",
    }:
        parser.error("missing direction; use 'push [-y] ENDPOINT' or 'pull [-y] ENDPOINT'")
    args = parser.parse_args(raw_args)

    local = parse_endpoint(".")
    other = parse_endpoint(args.endpoint)
    source, dest = (local, other) if args.direction == "push" else (other, local)
    if not source.remote and not dest.remote:
        source_path, dest_path = Path(source.path), Path(dest.path)
        if (
            source_path == dest_path
            or source_path in dest_path.parents
            or dest_path in source_path.parents
        ):
            raise SystemExit("Refusing overlapping local source and destination")

    emit(f"MODE: {'APPLY' if args.yes else 'DRY RUN'}")
    emit(f"DIRECTION: {args.direction.upper()}")
    emit(f"AUTHORITY: {endpoint_label(source)}")
    emit(f"DESTINATION: {endpoint_label(dest)}")
    if args.yes:
        emit("WARNING: destination files and Git state may be overwritten or deleted.")
    return sync_repository(source, dest, apply=args.yes)


if __name__ == "__main__":
    raise SystemExit(main())
