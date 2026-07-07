#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


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
        path = self.path_with_trailing_slash()
        if self.remote:
            return f"{self.host}:{path}"
        return path

    def path_with_trailing_slash(self) -> str:
        path = str(PurePosixPath(self.path)) if self.remote else self.path.rstrip("/")
        return "/" if path == "/" else path.rstrip("/") + "/"


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
        cmd = "cd " + shlex.quote(endpoint.subpath(rel)) + " && " + shlex.join(args)
        return run_capture(
            ["ssh", endpoint.host or "", cmd], input_data=input_data, check=check
        )
    return run_capture(
        args, cwd=Path(endpoint.subpath(rel)), input_data=input_data, check=check
    )


def run_shell_at(
    endpoint: Endpoint,
    script: str,
    *,
    input_data: bytes | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[bytes]:
    if endpoint.remote:
        cmd = "cd " + shlex.quote(endpoint.path) + " && " + script
        return run_capture(
            ["ssh", endpoint.host or "", cmd], input_data=input_data, check=check
        )
    return run_capture(
        ["bash", "-lc", script],
        cwd=Path(endpoint.path),
        input_data=input_data,
        check=check,
    )


def parse_endpoint(value: str) -> Endpoint:
    if "\0" in value or "\n" in value:
        raise SystemExit(f"Refusing unsafe endpoint: {value!r}")
    if ":" in value and not value.startswith(("/", "./", "../")):
        host, path = value.split(":", 1)
        remote_path = PurePosixPath(path)
        if host and remote_path.is_absolute():
            return Endpoint(value, host, str(remote_path))
        raise SystemExit("Remote endpoints must look like host:/absolute/path")

    path = Path(value).expanduser().resolve(strict=False)
    return Endpoint(value, None, str(path))


def validate_relpath(path: str) -> None:
    if not path or "\0" in path or "\n" in path:
        raise SystemExit(f"Refusing unsafe relative path: {path!r}")
    rel = PurePosixPath(path)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise SystemExit(f"Refusing unsafe relative path: {path!r}")


def decode_path(raw: bytes) -> str:
    path = raw.decode("utf-8", "surrogateescape")
    validate_relpath(path)
    return path


def split_nul(data: bytes) -> list[str]:
    return [decode_path(raw) for raw in data.split(b"\0") if raw]


def ensure_submodules_initialized(source: Endpoint) -> None:
    result = run_at(source, ["git", "submodule", "status", "--recursive"], check=False)
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(result.returncode)

    missing: list[str] = []
    for line in result.stdout.decode("utf-8", "surrogateescape").splitlines():
        if not line or line[0] != "-":
            continue
        parts = line[1:].strip().split()
        if len(parts) >= 2:
            validate_relpath(parts[1])
            missing.append(parts[1])

    if missing:
        raise SystemExit("Submodules are not initialized: " + ", ".join(missing))


def list_git_roots(source: Endpoint) -> list[str]:
    ensure_submodules_initialized(source)
    roots_by_prefix: set[str] = {""}
    result = run_at(
        source,
        [
            "git",
            "submodule",
            "foreach",
            "--recursive",
            "-q",
            'printf "%s\n" "$displaypath"',
        ],
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr.decode("utf-8", "replace"))
        raise SystemExit(result.returncode)

    for line in result.stdout.decode("utf-8", "surrogateescape").splitlines():
        prefix = line.strip("/")
        if prefix:
            validate_relpath(prefix)
            roots_by_prefix.add(prefix)

    return sorted(
        roots_by_prefix,
        key=lambda prefix: (prefix.count("/") if prefix else -1, prefix),
    )


def git_ls_files(source: Endpoint, root: str, args: list[str]) -> set[str]:
    result = run_at(source, ["git", "ls-files", "-z", *args], rel=root)
    return set(split_nul(result.stdout))


def gitlink_paths(source: Endpoint, root: str) -> set[str]:
    result = run_at(source, ["git", "ls-files", "-z", "--stage"], rel=root)
    paths: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        meta, _, path = raw.partition(b"\t")
        if meta.startswith(b"160000 "):
            paths.add(decode_path(path))
    return paths


def source_files(source: Endpoint, roots: list[str]) -> set[str]:
    files: set[str] = set()
    nested_prefixes = {root for root in roots if root}

    for root in roots:
        candidates = git_ls_files(
            source, root, ["--cached", "--others", "--exclude-standard"]
        )
        deleted = git_ls_files(source, root, ["--deleted"])
        gitlinks = gitlink_paths(source, root)
        for rel in sorted(candidates - deleted):
            if rel.endswith("/") or rel in gitlinks:
                continue
            path = str(PurePosixPath(root) / rel) if root else rel
            # Parent repositories record submodule roots as entries. Their
            # worktrees are handled by their own Git roots below.
            if path in nested_prefixes:
                continue
            validate_relpath(path)
            files.add(path)

    return files


def find_paths(endpoint: Endpoint, predicate: str) -> set[str]:
    if not endpoint.remote and not Path(endpoint.path).exists():
        return set()

    find_cmd = (
        "find . -mindepth 1 "
        + r"\( -path './.git' -o -path './*/.git' \) -prune -o "
        + predicate
        + " -print0"
    )
    result = run_shell_at(endpoint, find_cmd)
    paths: set[str] = set()
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = raw.decode("utf-8", "surrogateescape")
        if path.startswith("./"):
            path = path[2:]
        validate_relpath(path)
        paths.add(path)
    return paths


def source_dirs(paths: set[str]) -> set[str]:
    dirs: set[str] = set()
    for path in paths:
        parent = PurePosixPath(path).parent
        while str(parent) != ".":
            dirs.add(str(parent))
            parent = parent.parent
    return dirs


def route_path(path: str, roots_desc: list[str]) -> tuple[str, str]:
    for root in roots_desc:
        if root and (path == root or path.startswith(root + "/")):
            return root, path[len(root) + 1 :]
    return roots_desc[-1], path


def ignored_paths(paths: list[str], source: Endpoint, roots: list[str]) -> set[str]:
    roots_desc = sorted(roots, key=len, reverse=True)

    by_root: dict[str, list[tuple[str, str]]] = {}
    for path in paths:
        root, rel = route_path(path, roots_desc)
        if rel:
            by_root.setdefault(root, []).append((path, rel))

    ignored: set[str] = set()
    for root, entries in by_root.items():
        stdin = (
            b"\0".join(rel.encode("utf-8", "surrogateescape") for _, rel in entries)
            + b"\0"
        )
        result = run_at(
            source,
            ["git", "check-ignore", "-z", "--stdin"],
            rel=root,
            input_data=stdin,
            check=False,
        )
        if result.returncode not in (0, 1):
            sys.stderr.write(result.stderr.decode("utf-8", "replace"))
            raise SystemExit(result.returncode)
        ignored_rel = set(split_nul(result.stdout))
        for full, rel in entries:
            if rel in ignored_rel:
                ignored.add(full)

    return ignored


def write_files_from(paths: set[str]) -> str:
    handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
    try:
        for path in sorted(paths):
            validate_relpath(path)
            handle.write(path + "\n")
        return handle.name
    finally:
        handle.close()


def rsync_transfer(
    source: Endpoint, dest: Endpoint, files_from: str, *, dry_run: bool
) -> int:
    args = ["rsync", "-rzci", "--links", "--executability", "--files-from", files_from]
    if dry_run:
        args.insert(1, "-n")
    args.extend([source.rsync_arg(), dest.rsync_arg()])
    return subprocess.run(args).returncode


def delete_dest_paths(dest: Endpoint, paths: list[str], *, recursive: bool) -> None:
    if not paths:
        return
    for rel in paths:
        validate_relpath(rel)
    stdin = b"\0".join(rel.encode("utf-8", "surrogateescape") for rel in paths) + b"\0"
    rm_flag = "-rf" if recursive else "-f"

    if dest.remote:
        cmd = "cd " + shlex.quote(dest.path) + " && xargs -0 rm " + rm_flag + " --"
        run_capture(["ssh", dest.host or "", cmd], input_data=stdin)
        return

    run_capture(
        ["xargs", "-0", "rm", rm_flag, "--"], cwd=Path(dest.path), input_data=stdin
    )


def ensure_supported_pair(source: Endpoint, dest: Endpoint) -> None:
    # Remote-to-remote needs a separate transport path for the generated
    # files-from list. Keep the planner honest until that path is actually
    # needed and tested.
    if source.remote and dest.remote:
        raise SystemExit("SRC and DST cannot both be remote")

    if source.remote or dest.remote:
        return

    # A local destination inside the source, or vice versa, makes the planner's
    # source and destination sets overlap. Refuse that before rsync can copy a
    # tree into itself or deletion can target source files.
    src = Path(source.path)
    dst = Path(dest.path)
    try:
        src.relative_to(dst)
        overlaps = True
    except ValueError:
        try:
            dst.relative_to(src)
            overlaps = True
        except ValueError:
            overlaps = False
    if overlaps:
        raise SystemExit("Refusing local sync where SRC and DST overlap")


def print_list(title: str, paths: list[str], *, limit: int | None = None) -> None:
    print(f"\n{title} ({len(paths)})")
    shown = paths if limit is None else paths[:limit]
    for path in shown:
        print(f"  {path}")
    if limit is not None and len(paths) > limit:
        print(f"  ... {len(paths) - limit} more")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rsync a Git source tree using Git's ignore policy."
    )
    parser.add_argument(
        "-y", "--yes", action="store_true", help="Apply the displayed plan"
    )
    parser.add_argument("paths", nargs="+", metavar="PATH", help="[SRC] DST")
    args = parser.parse_args()

    if len(args.paths) == 1:
        source = parse_endpoint(".")
        dest = parse_endpoint(args.paths[0])
    elif len(args.paths) == 2:
        source = parse_endpoint(args.paths[0])
        dest = parse_endpoint(args.paths[1])
    else:
        parser.error("expected DST or SRC DST")

    ensure_supported_pair(source, dest)

    roots = list_git_roots(source)
    source_set = source_files(source, roots)
    dest_set = find_paths(dest, r"\( -type f -o -type l \)")
    dest_dir_set = find_paths(dest, "-type d")
    source_dir_set = source_dirs(source_set)
    file_blockers = sorted(dest_set & source_dir_set)
    dir_blockers = sorted(dest_dir_set & source_set)
    dir_blocker_set = set(dir_blockers)
    covered_by_dir_blockers = {
        path
        for path in dest_set
        if any(path.startswith(d + "/") for d in dir_blocker_set)
    }
    dest_extra = sorted((dest_set - source_set) - covered_by_dir_blockers)
    ignored_extra = ignored_paths(
        [path for path in dest_extra if path not in file_blockers], source, roots
    )
    keep_ignored = sorted(ignored_extra)
    delete_candidates = sorted((set(dest_extra) - ignored_extra) | set(file_blockers))
    post_transfer_deletes = sorted(set(delete_candidates) - set(file_blockers))

    print(f"SRC: {source.raw} ({'remote' if source.remote else 'local'})")
    print(f"DST: {dest.raw} ({'remote' if dest.remote else 'local'})")
    print(f"Source files: {len(source_set)}")
    print(f"Destination files/links: {len(dest_set)}")
    print(
        "Planner scope: files/symlinks plus path-blocking directories; "
        "other extra directories are left untouched."
    )
    print_list("Destination directory blockers (source files at these paths)", dir_blockers)
    print_list(
        "Destination file/link blockers (source directories at these paths)",
        file_blockers,
    )
    print_list("Destination delete candidates (non-ignored extras)", delete_candidates)
    print_list("Destination kept extras (ignored by Git)", keep_ignored, limit=80)
    sys.stdout.flush()

    files_from = write_files_from(source_set)
    try:
        if args.yes:
            delete_dest_paths(dest, dir_blockers, recursive=True)
            delete_dest_paths(dest, file_blockers, recursive=False)
            print("\nRsync source transfer:")
            sys.stdout.flush()
            rc = rsync_transfer(source, dest, files_from, dry_run=False)
            if rc != 0:
                return rc
            delete_dest_paths(dest, post_transfer_deletes, recursive=False)
            print(f"\nDeleted destination extras: {len(delete_candidates)}")
            if dir_blockers:
                print(f"Deleted destination directory blockers: {len(dir_blockers)}")
        else:
            if dir_blockers or file_blockers:
                print(
                    "\nRsync source transfer plan skipped until path blockers are removed."
                )
            else:
                print("\nRsync source transfer plan:")
                sys.stdout.flush()
                rc = rsync_transfer(source, dest, files_from, dry_run=True)
                if rc != 0:
                    return rc
            print(
                "\nDry run only. Re-run with -y to transfer source and delete candidates."
            )
    finally:
        try:
            Path(files_from).unlink()
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
