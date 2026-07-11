#!/usr/bin/env python3
"""Mirror a local Git worktree into an initialized execution copy.

Contract:

* The local worktree is authoritative. Destination edits are not protected.
* Git-ignored destination extras are preserved.
* A local ``filter=lfs`` pointer is present logically but is not transferred.
  Its destination path must already exist as a file or symlink and is kept as-is.
* File/directory path blockers are errors; this script never removes them.
* The command is a dry-run unless ``-y`` is supplied.
"""

from __future__ import annotations

import argparse
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


SAFE_HOST = re.compile(r"^(?:[A-Za-z0-9_.-]+@)?[A-Za-z0-9_.-]+$")
SAFE_REMOTE_PATH = re.compile(r"^/[A-Za-z0-9_./+,@=-]+$")
LFS_VERSION = "version https://git-lfs.github.com/spec/v1"
LFS_OID = re.compile(r"oid sha256:[0-9a-f]{64}")
LFS_SIZE = re.compile(r"size [0-9]+")


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


def run_capture(
    args: list[str],
    *,
    cwd: Path | None = None,
    input_data: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(args, cwd=cwd, input=input_data, capture_output=True)
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
) -> subprocess.CompletedProcess[bytes]:
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
    )


def run_shell_at(
    endpoint: Endpoint,
    script: str,
    *,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if endpoint.remote:
        command = "cd " + shlex.quote(endpoint.path) + " && " + script
        return run_capture(
            ["ssh", "--", endpoint.host or "", command], input_data=input_data
        )
    return run_capture(
        ["bash", "-lc", script], cwd=Path(endpoint.path), input_data=input_data
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


def verify_git_root(endpoint: Endpoint) -> None:
    physical = run_at(endpoint, ["pwd", "-P"]).stdout.decode().strip()
    top = run_at(endpoint, ["git", "rev-parse", "--show-toplevel"]).stdout.decode().strip()
    if endpoint.remote:
        matches = str(PurePosixPath(physical)) == str(PurePosixPath(top))
    else:
        matches = Path(physical).resolve() == Path(top).resolve()
    if not matches:
        raise SystemExit(f"Endpoint is not an exact Git worktree root: {endpoint.raw}")


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
        candidates = git_paths(
            source, root, ["--cached", "--others", "--exclude-standard"]
        )
        deleted = git_paths(source, root, ["--deleted"])
        links = gitlinks(source, root)
        for rel in sorted(candidates - deleted):
            if rel.endswith("/"):
                raise SystemExit(
                    "Embedded or collapsed directory is unsupported: " + display(rel)
                )
            if rel in links:
                continue
            path = str(PurePosixPath(root) / rel) if root else rel
            if path in nested_roots:
                continue
            validate_relpath(path)
            files.add(path)
    return files


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
        stdin = b"\0".join(
            rel.encode("utf-8", "surrogateescape") for _, rel in entries
        ) + b"\0"
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


def is_lfs_pointer(path: Path) -> bool:
    try:
        if path.stat().st_size >= 1024:
            return False
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    if len(lines) < 3 or lines[0] != LFS_VERSION:
        return False
    return bool(LFS_OID.fullmatch(lines[-2]) and LFS_SIZE.fullmatch(lines[-1]))


def lfs_pointer_paths(
    source: Endpoint, logical: set[str], roots: list[str], source_regular: set[str]
) -> set[str]:
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
    return {
        path
        for path in logical & source_regular
        if filters.get(path) == "lfs" and is_lfs_pointer(Path(source.subpath(path)))
    }


def ignored_paths(
    paths: list[str], source: Endpoint, roots: list[str]
) -> set[str]:
    roots_descending = sorted(roots, key=len, reverse=True)
    by_root: dict[str, list[tuple[str, str]]] = {}
    for path in paths:
        root, rel = route_path(path, roots_descending)
        by_root.setdefault(root, []).append((path, rel))
    ignored: set[str] = set()
    for root, entries in by_root.items():
        stdin = b"\0".join(
            rel.encode("utf-8", "surrogateescape") for _, rel in entries
        ) + b"\0"
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


def write_files_from(paths: set[str]) -> str:
    handle = tempfile.NamedTemporaryFile("wb", delete=False)
    try:
        for path in sorted(paths):
            handle.write(path.encode("utf-8", "surrogateescape") + b"\0")
        return handle.name
    finally:
        handle.close()


def rsync_transfer(
    source: Endpoint, dest: Endpoint, files_from: str, *, dry_run: bool
) -> int:
    args = [
        "rsync",
        "-rzci",
        "--links",
        "--executability",
        "--delay-updates",
        "--from0",
        "--files-from",
        files_from,
    ]
    if dry_run:
        args.insert(1, "-n")
    args.extend(["--", source.rsync_arg(), dest.rsync_arg()])
    return subprocess.run(args).returncode


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
    print(f"\n{title} ({len(paths)})")
    for path in paths[:limit]:
        print("  " + display(path))
    if len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-y", "--yes", action="store_true", help="Apply the plan")
    parser.add_argument("paths", nargs="+", metavar="PATH", help="[SRC] DST")
    args = parser.parse_args(argv)
    if len(args.paths) == 1:
        source = parse_endpoint(".")
        dest = parse_endpoint(args.paths[0])
    elif len(args.paths) == 2:
        source = parse_endpoint(args.paths[0])
        dest = parse_endpoint(args.paths[1])
    else:
        parser.error("expected DST or SRC DST")
    if source.remote:
        raise SystemExit("v2 requires a local source worktree")
    if not dest.remote:
        source_path, dest_path = Path(source.path), Path(dest.path)
        if source_path == dest_path or source_path in dest_path.parents or dest_path in source_path.parents:
            raise SystemExit("Refusing overlapping local source and destination")

    verify_git_root(source)
    verify_git_root(dest)
    roots = list_git_roots(source)
    logical = source_files(source, roots)

    source_regular = find_paths(source, "-type f")
    source_links = find_paths(source, "-type l")
    source_special = find_paths(
        source, r"! \( -type f -o -type l -o -type d \)"
    )
    missing_or_bad_source = logical - source_regular - source_links
    if missing_or_bad_source:
        raise SystemExit(
            "Source paths are missing or unsupported: "
            + ", ".join(display(path) for path in sorted(missing_or_bad_source)[:8])
        )
    nonignored_source_special = source_special - ignored_paths(
        sorted(source_special), source, roots
    )
    if nonignored_source_special:
        raise SystemExit(
            "Non-ignored source special nodes are unsupported: "
            + ", ".join(display(path) for path in sorted(nonignored_source_special)[:8])
        )

    pointers = lfs_pointer_paths(source, logical, roots, source_regular)
    transfer = logical - pointers
    source_dirs = source_directories(logical)

    dest_files_links = find_paths(dest, r"\( -type f -o -type l \)")
    dest_dirs = find_paths(dest, "-type d")
    dest_special = find_paths(dest, r"! \( -type f -o -type l -o -type d \)")
    file_blockers = sorted((dest_files_links | dest_special) & source_dirs)
    dir_blockers = sorted(dest_dirs & logical)
    special_blockers = sorted(dest_special & logical)
    missing_lfs = sorted(pointers - dest_files_links)

    dest_leaves = dest_files_links | dest_special
    extras = sorted(dest_leaves - logical)
    ignored = ignored_paths(extras, source, roots)
    special_extras = sorted((dest_special - logical) - ignored)
    delete_candidates = sorted((dest_files_links - logical) - ignored)
    errors: list[str] = []
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

    print(f"SRC: {source.raw} (local)")
    print(f"DST: {dest.raw} ({'remote' if dest.remote else 'local'})")
    print(f"Logical source files: {len(logical)}")
    print(f"Transfer files: {len(transfer)}")
    print(f"Preserved LFS paths: {len(pointers)}")
    print(f"Destination delete files/links: {len(delete_candidates)}")
    print(f"Destination kept ignored files/links: {len(ignored)}")
    print_paths("Preserved LFS paths", sorted(pointers))
    print_paths("Destination file/special blockers", file_blockers)
    print_paths("Destination directory blockers", dir_blockers)
    print_paths("Missing/invalid destination LFS paths", missing_lfs)
    print_paths("Destination delete files/links", delete_candidates)
    if errors:
        print(f"\nErrors ({len(errors)})")
        for error in errors:
            print("  " + error)
        print("\nNo changes made.")
        return 2

    files_from = write_files_from(transfer)
    try:
        print("\nRsync transfer plan:" if not args.yes else "\nRsync transfer:")
        sys.stdout.flush()
        rc = rsync_transfer(source, dest, files_from, dry_run=not args.yes)
        if rc != 0:
            if args.yes:
                print("\nRsync failed; destination extras were not deleted.")
            return rc
        if not args.yes:
            print("\nDry run only. Re-run with -y to apply a freshly generated plan.")
            return 0
        verify_git_root(dest)
        delete_files(dest, delete_candidates)
        print(f"\nDeleted destination extras: {len(delete_candidates)}")
        return 0
    finally:
        try:
            Path(files_from).unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
