#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["pytest"]
# ///
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("rsync_repo.py")

spec = importlib.util.spec_from_file_location("rsync_repo", SCRIPT)
assert spec and spec.loader
rsync_repo = importlib.util.module_from_spec(spec)
sys.modules["rsync_repo"] = rsync_repo
spec.loader.exec_module(rsync_repo)


def run(
    args: list[str], *, cwd: Path | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=repo)


def init_repo(repo: Path) -> None:
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", message)


def test_recursive_submodules_use_root_relative_paths(tmp_path: Path) -> None:
    grand = tmp_path / "grand-src"
    child = tmp_path / "child-src"
    root = tmp_path / "root"

    init_repo(grand)
    (grand / "grand.txt").write_text("grand\n")
    commit_all(grand, "grand")

    init_repo(child)
    (child / "child.txt").write_text("child\n")
    commit_all(child, "child")
    git(
        child,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(grand),
        "grand",
    )
    commit_all(child, "add grand")

    init_repo(root)
    (root / "root.txt").write_text("root\n")
    commit_all(root, "root")
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(child),
        "child",
    )
    commit_all(root, "add child")
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "update",
        "--init",
        "--recursive",
    )

    source = rsync_repo.parse_endpoint(str(root))
    roots = rsync_repo.list_git_roots(source)
    assert roots == ["", "child", "child/grand"]

    files = rsync_repo.source_files(source, roots)
    assert "root.txt" in files
    assert "child/child.txt" in files
    assert "child/grand/grand.txt" in files


def test_uninitialized_submodule_is_rejected(tmp_path: Path) -> None:
    child = tmp_path / "child-src"
    root = tmp_path / "root"

    init_repo(child)
    (child / "child.txt").write_text("child\n")
    commit_all(child, "child")

    init_repo(root)
    git(
        root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        str(child),
        "child",
    )
    commit_all(root, "add child")
    git(root, "submodule", "deinit", "-f", "child")

    source = rsync_repo.parse_endpoint(str(root))
    with pytest.raises(SystemExit, match="Submodules are not initialized: child"):
        rsync_repo.list_git_roots(source)


def test_apply_deletes_only_non_ignored_extra_files(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"

    init_repo(source)
    (source / ".gitignore").write_text("ignored/\n*.log\n")
    (source / "tracked.txt").write_text("fresh\n")
    (source / "dir").mkdir()
    (source / "dir" / "untracked name.txt").write_text("copy me\n")
    git(source, "add", ".gitignore", "tracked.txt")

    dest.mkdir()
    (dest / "old file.txt").write_text("stale\n")
    (dest / "semi;colon.txt").write_text("stale\n")
    (dest / "quote'file.txt").write_text("stale\n")
    (dest / "ignored").mkdir()
    (dest / "ignored" / "cache.bin").write_text("keep\n")
    (dest / "debug.log").write_text("keep\n")
    (dest / "empty-old").mkdir()

    dry = run([sys.executable, str(SCRIPT), str(source), str(dest)])
    assert "Dry run only" in dry.stdout
    assert (dest / "old file.txt").exists()

    applied = run([sys.executable, str(SCRIPT), "-y", str(source), str(dest)])
    assert "Deleted destination extras: 3" in applied.stdout

    assert (dest / "tracked.txt").read_text() == "fresh\n"
    assert (dest / "dir" / "untracked name.txt").read_text() == "copy me\n"
    assert not (dest / "old file.txt").exists()
    assert not (dest / "semi;colon.txt").exists()
    assert not (dest / "quote'file.txt").exists()
    assert (dest / "ignored" / "cache.bin").read_text() == "keep\n"
    assert (dest / "debug.log").read_text() == "keep\n"
    assert (dest / "empty-old").is_dir()
    assert "path-blocking directories" in applied.stdout


def test_apply_removes_path_blockers_before_transfer(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"

    init_repo(source)
    (source / "file-now").write_text("source file\n")
    (source / "dir-now").mkdir()
    (source / "dir-now" / "nested.txt").write_text("source nested\n")
    git(source, "add", ".")

    dest.mkdir()
    (dest / "file-now").mkdir()
    (dest / "file-now" / "old.txt").write_text("stale\n")
    (dest / "dir-now").write_text("stale file\n")

    dry = run([sys.executable, str(SCRIPT), str(source), str(dest)])
    assert "Destination directory blockers (source files at these paths) (1)" in dry.stdout
    assert "Destination file/link blockers (source directories at these paths) (1)" in dry.stdout
    assert "Rsync source transfer plan skipped until path blockers are removed." in dry.stdout
    assert (dest / "file-now" / "old.txt").exists()
    assert (dest / "dir-now").is_file()

    applied = run([sys.executable, str(SCRIPT), "-y", str(source), str(dest)])
    assert (dest / "file-now").read_text() == "source file\n"
    assert (dest / "dir-now" / "nested.txt").read_text() == "source nested\n"
    assert "Deleted destination extras: 1" in applied.stdout
    assert "Deleted destination directory blockers: 1" in applied.stdout


def test_remote_to_remote_is_rejected_before_planning() -> None:
    source = rsync_repo.Endpoint("host:/src", "host", "/src")
    dest = rsync_repo.Endpoint("host:/dst", "host", "/dst")

    with pytest.raises(SystemExit, match="SRC and DST cannot both be remote"):
        rsync_repo.ensure_supported_pair(source, dest)


if __name__ == "__main__":
    raise SystemExit(pytest.main(["-p", "no:cacheprovider", __file__]))
