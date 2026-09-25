#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("rsync_repo.py")
if not SCRIPT.exists():
    SCRIPT = Path(__file__).with_name("executable_rsync_repo.py")
spec = importlib.util.spec_from_file_location("rsync_repo", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def run(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_data: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_data,
        text=True,
        capture_output=True,
        check=check,
    )


def git(repo: Path, *args: str) -> None:
    run(["git", *args], cwd=repo)


def init_repo(repo: Path) -> None:
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test User")


def commit_all(repo: Path) -> None:
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "commit")


def clone_repo(source: Path, dest: Path) -> None:
    env = os.environ.copy()
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    run(["git", "clone", "-q", "--no-local", str(source), str(dest)], env=env)


def invoke(
    source: Path,
    dest: Path,
    *options: str,
    direction: str = "push",
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    cwd, endpoint = (source, dest) if direction == "push" else (dest, source)
    return run(
        [sys.executable, str(SCRIPT), direction, *options, str(endpoint)],
        cwd=cwd,
        env=env,
        check=False,
    )


def pointer(payload: bytes) -> bytes:
    return (
        "version https://git-lfs.github.com/spec/v1\n"
        f"oid sha256:{hashlib.sha256(payload).hexdigest()}\n"
        f"size {len(payload)}\n"
    ).encode()


class SyncRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rsync-repo-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def fake_ssh_env(self, *, fail: bool = False) -> dict[str, str]:
        fake_bin = self.root / ("broken-ssh-bin" if fail else "ssh-bin")
        fake_bin.mkdir(exist_ok=True)
        fake_ssh = fake_bin / "ssh"
        if fail:
            fake_ssh.write_text("#!/bin/sh\necho 'simulated SSH failure' >&2\nexit 255\n")
        else:
            fake_ssh.write_text(
                "#!/bin/sh\n"
                'while test "$#" -gt 0; do\n'
                '  case "$1" in\n'
                "    --) shift; break ;;\n"
                "    -o|-p|-l|-i|-F|-J) shift 2 ;;\n"
                "    -*) shift ;;\n"
                "    *) break ;;\n"
                "  esac\n"
                "done\n"
                "shift\n"
                'if test "$#" -eq 1; then exec sh -c "$1"; fi\n'
                'exec "$@"\n'
            )
        fake_ssh.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        return env

    def basic_pair(self) -> tuple[Path, Path]:
        source = self.root / "source"
        dest = self.root / "dest"
        init_repo(source)
        (source / ".gitignore").write_text("ignored/\n")
        (source / "tracked.txt").write_text("base\n")
        commit_all(source)
        clone_repo(source, dest)
        return source, dest

    def lfs_pair(self) -> tuple[Path, Path, bytes]:
        source = self.root / "source"
        dest = self.root / "dest"
        init_repo(source)
        payload = b"payload used only for pointer metadata"
        raw_pointer = pointer(payload)
        (source / ".gitattributes").write_text("*.bin filter=lfs -text\n")
        (source / "asset.bin").write_bytes(raw_pointer)
        (source / "normal.txt").write_text("base\n")
        commit_all(source)
        clone_repo(source, dest)
        return source, dest, raw_pointer

    def source_with_submodule(self) -> Path:
        child = self.root / "child"
        init_repo(child)
        (child / "child.txt").write_text("child\n")
        commit_all(child)

        source = self.root / "source"
        init_repo(source)
        (source / "root.txt").write_text("root\n")
        commit_all(source)
        run(
            [
                "git",
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "-q",
                str(child),
                "module",
            ],
            cwd=source,
        )
        commit_all(source)
        return source

    def test_local_is_authoritative_and_ignored_extras_are_kept(self) -> None:
        source, dest = self.basic_pair()
        (source / "tracked.txt").write_text("local\n")
        (source / "new file.txt").write_text("new\n")
        (dest / "tracked.txt").write_text("remote edit\n")
        (dest / "delete.txt").write_text("delete\n")
        (dest / "ignored").mkdir()
        (dest / "ignored" / "cache.bin").write_bytes(b"keep")

        dry = invoke(source, dest)
        self.assertEqual(dry.returncode, 0, dry.stderr + dry.stdout)
        self.assertIn("MODE: DRY RUN", dry.stdout)
        self.assertIn("DIRECTION: PUSH", dry.stdout)
        self.assertIn("tracked.txt", dry.stdout)
        self.assertEqual((dest / "tracked.txt").read_text(), "remote edit\n")

        applied = invoke(source, dest, "-y")
        self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
        self.assertEqual((dest / "tracked.txt").read_text(), "local\n")
        self.assertEqual((dest / "new file.txt").read_text(), "new\n")
        self.assertFalse((dest / "delete.txt").exists())
        self.assertEqual((dest / "ignored" / "cache.bin").read_bytes(), b"keep")

    def test_pull_from_remote_endpoint_uses_remote_as_authority(self) -> None:
        source, dest = self.basic_pair()
        (source / "tracked.txt").write_text("remote source\n")
        (source / "new.txt").write_text("new\n")
        git(source, "add", "new.txt")
        (dest / "tracked.txt").write_text("local edit\n")
        (dest / "delete.txt").write_text("delete\n")
        (dest / "ignored").mkdir()
        (dest / "ignored" / "cache.bin").write_bytes(b"keep")

        dry = run(
            [sys.executable, str(SCRIPT), "pull", f"fake:{source}"],
            cwd=dest,
            env=self.fake_ssh_env(),
            check=False,
        )
        self.assertEqual(dry.returncode, 0, dry.stderr + dry.stdout)
        self.assertIn("MODE: DRY RUN", dry.stdout)
        self.assertIn("DIRECTION: PULL", dry.stdout)
        self.assertIn(f"AUTHORITY: fake:{source}", dry.stdout)
        self.assertEqual((dest / "tracked.txt").read_text(), "local edit\n")
        self.assertFalse((dest / "new.txt").exists())
        self.assertTrue((dest / "delete.txt").exists())

        result = run(
            [sys.executable, str(SCRIPT), "pull", "-y", f"fake:{source}"],
            cwd=dest,
            env=self.fake_ssh_env(),
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("DIRECTION: PULL", result.stdout)
        self.assertIn(f"AUTHORITY: fake:{source}", result.stdout)
        self.assertEqual((dest / "tracked.txt").read_text(), "remote source\n")
        self.assertEqual((dest / "new.txt").read_text(), "new\n")
        self.assertFalse((dest / "delete.txt").exists())
        self.assertEqual((dest / "ignored" / "cache.bin").read_bytes(), b"keep")
        self.assertEqual(
            run(["git", "write-tree"], cwd=dest).stdout,
            run(["git", "write-tree"], cwd=source).stdout,
        )

    def test_pull_detects_remote_lfs_pointer_and_keeps_local_asset(self) -> None:
        source, dest, _ = self.lfs_pair()
        local_asset = b"local hydrated asset"
        (dest / "asset.bin").write_bytes(local_asset)

        result = run(
            [sys.executable, str(SCRIPT), "pull", "-y", f"fake:{source}"],
            cwd=dest,
            env=self.fake_ssh_env(),
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((dest / "asset.bin").read_bytes(), local_asset)

    def test_branch_switch_syncs_head_staged_tree_and_worktree(self) -> None:
        source, dest = self.basic_pair()
        git(source, "switch", "-q", "-c", "deployment")
        (source / "tracked.txt").write_text("branch commit\n")
        commit_all(source)
        (source / "staged.txt").write_text("staged\n")
        git(source, "add", "staged.txt")
        (source / "untracked.txt").write_text("untracked\n")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(
            run(["git", "rev-parse", "HEAD"], cwd=dest).stdout,
            run(["git", "rev-parse", "HEAD"], cwd=source).stdout,
        )
        self.assertEqual(
            run(["git", "write-tree"], cwd=dest).stdout,
            run(["git", "write-tree"], cwd=source).stdout,
        )
        self.assertEqual(
            run(["git", "symbolic-ref", "-q", "HEAD"], cwd=dest, check=False).returncode,
            1,
        )
        self.assertNotEqual(
            run(
                ["git", "show-ref", "--verify", "refs/heads/deployment"],
                cwd=dest,
                check=False,
            ).returncode,
            0,
        )
        self.assertEqual((dest / "tracked.txt").read_text(), "branch commit\n")
        self.assertEqual((dest / "staged.txt").read_text(), "staged\n")
        self.assertEqual((dest / "untracked.txt").read_text(), "untracked\n")

    def test_staged_deletion_syncs_worktree_and_staged_tree(self) -> None:
        source = self.root / "source"
        dest = self.root / "dest"
        init_repo(source)
        (source / "only.txt").write_text("only\n")
        commit_all(source)
        clone_repo(source, dest)
        (source / "only.txt").unlink()
        git(source, "add", "-u")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse((dest / "only.txt").exists())
        self.assertEqual(
            run(["git", "write-tree"], cwd=dest).stdout,
            run(["git", "write-tree"], cwd=source).stdout,
        )

    def test_untracked_source_symlink_is_transferred(self) -> None:
        source, dest = self.basic_pair()
        (source / "shortcut").symlink_to("tracked.txt")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((dest / "shortcut").is_symlink())
        self.assertEqual(os.readlink(dest / "shortcut"), "tracked.txt")

    def test_destination_branches_and_config_are_not_modified(self) -> None:
        source, dest = self.basic_pair()
        git(dest, "branch", "remote-only")
        git(dest, "config", "branch.remote-only.remote", "keep")
        git(dest, "update-ref", "refs/remotes/cache/main", "HEAD")
        git(dest, "update-ref", "refs/rsync-repo/heads/legacy", "HEAD")
        git(dest, "update-ref", "refs/rsync-repo/upstreams/cache/main", "HEAD")
        refs_before = run(
            [
                "git",
                "for-each-ref",
                "--format=%(refname) %(objectname)",
                "refs/heads",
                "refs/remotes",
                "refs/rsync-repo/heads",
                "refs/rsync-repo/upstreams",
            ],
            cwd=dest,
        ).stdout
        config_before = (dest / ".git" / "config").read_bytes()
        (source / "tracked.txt").write_text("local\n")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(
            run(
                [
                    "git",
                    "for-each-ref",
                    "--format=%(refname) %(objectname)",
                    "refs/heads",
                    "refs/remotes",
                    "refs/rsync-repo/heads",
                    "refs/rsync-repo/upstreams",
                ],
                cwd=dest,
            ).stdout,
            refs_before,
        )
        self.assertEqual((dest / ".git" / "config").read_bytes(), config_before)

    def test_ignored_destination_git_worktree_is_kept(self) -> None:
        source, dest = self.basic_pair()
        ignored_repo = dest / "ignored"
        init_repo(ignored_repo)
        payload = ignored_repo / "payload.bin"
        payload.write_bytes(b"keep")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((ignored_repo / ".git").is_dir())
        self.assertEqual(payload.read_bytes(), b"keep")

    def test_ignore_rule_does_not_hide_git_root_inside_managed_directory(self) -> None:
        source, dest = self.basic_pair()
        managed = source / "ignored" / "repo" / "managed.txt"
        managed.parent.mkdir(parents=True)
        managed.write_text("managed\n")
        git(source, "add", "-f", "ignored/repo/managed.txt")
        commit_all(source)
        stale_repo = dest / "ignored" / "repo"
        stale_repo.parent.mkdir()
        init_repo(stale_repo)

        result = invoke(source, dest)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Destination stale Git roots", result.stdout)

    def test_stale_destination_submodule_git_root_is_rejected(self) -> None:
        source = self.source_with_submodule()
        dest = self.root / "dest"
        clone_repo(source, dest)
        first = invoke(source, dest, "-y")
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

        git(source, "rm", "-q", "-f", "module")
        (source / "module").mkdir()
        (source / "module" / "ordinary.txt").write_text("ordinary\n")
        commit_all(source)

        result = invoke(source, dest)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Destination stale Git roots", result.stdout)
        self.assertTrue((dest / "module" / ".git").exists())

    def test_stale_destination_git_file_and_symlink_are_rejected(self) -> None:
        source, dest = self.basic_pair()
        stale_file = dest / "stale-file"
        stale_file.mkdir()
        (stale_file / ".git").write_text("gitdir: ../missing\n")
        stale_link = dest / "stale-link"
        stale_link.mkdir()
        (stale_link / ".git").symlink_to(dest / ".git")

        result = invoke(source, dest)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("stale-file", result.stdout)
        self.assertIn("stale-link", result.stdout)

    def test_lfs_pointer_preserves_any_existing_destination_file(self) -> None:
        source, dest, _ = self.lfs_pair()
        arbitrary_remote_bytes = b"not checked by design"
        (dest / "asset.bin").write_bytes(arbitrary_remote_bytes)
        before = (dest / "asset.bin").stat()
        (source / "normal.txt").write_text("changed\n")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((dest / "asset.bin").read_bytes(), arbitrary_remote_bytes)
        after = (dest / "asset.bin").stat()
        self.assertEqual(before.st_ino, after.st_ino)
        self.assertEqual(before.st_mtime_ns, after.st_mtime_ns)
        self.assertEqual((dest / "normal.txt").read_text(), "changed\n")

    def test_lfs_pointer_preserves_existing_destination_symlink(self) -> None:
        source, dest, _ = self.lfs_pair()
        (dest / "asset.bin").unlink()
        (dest / "asset.bin").symlink_to("/remote/cache/asset.bin")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue((dest / "asset.bin").is_symlink())
        self.assertEqual(os.readlink(dest / "asset.bin"), "/remote/cache/asset.bin")

    def test_missing_destination_lfs_path_aborts_everything(self) -> None:
        source, dest, _ = self.lfs_pair()
        (dest / "asset.bin").unlink()
        (source / "normal.txt").write_text("would transfer\n")
        (dest / "delete.txt").write_text("must remain\n")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Missing/invalid destination LFS paths", result.stdout)
        self.assertEqual((dest / "normal.txt").read_text(), "base\n")
        self.assertTrue((dest / "delete.txt").exists())

    def test_hydrated_local_lfs_file_transfers_normally(self) -> None:
        source, dest, _ = self.lfs_pair()
        local_payload = b"local payload bytes"
        (source / "asset.bin").write_bytes(local_payload)

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((dest / "asset.bin").read_bytes(), local_payload)

    def test_directory_blocker_aborts_without_deleting_it(self) -> None:
        source, dest = self.basic_pair()
        (source / "asset").write_text("file\n")
        (dest / "asset").mkdir()
        (dest / "asset" / "remote.bin").write_bytes(b"keep")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual((dest / "asset" / "remote.bin").read_bytes(), b"keep")

    def test_file_blocker_aborts_without_deleting_it(self) -> None:
        source, dest = self.basic_pair()
        (source / "pkg").mkdir()
        (source / "pkg" / "module.py").write_text("x = 1\n")
        (dest / "pkg").write_text("keep\n")

        result = invoke(source, dest, "-y")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertEqual((dest / "pkg").read_text(), "keep\n")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires mkfifo")
    def test_special_destination_blocker_reports_its_path(self) -> None:
        source, dest = self.basic_pair()
        (source / "asset").write_text("file\n")
        os.mkfifo(dest / "asset")

        result = invoke(source, dest)

        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("Destination special-node blockers (1)", result.stdout)
        self.assertIn("  asset", result.stdout)

    def test_destination_must_be_exact_git_root(self) -> None:
        source, _ = self.basic_pair()
        outside = self.root / "outside"
        outside.mkdir()
        valuable = outside / "valuable.bin"
        valuable.write_bytes(b"keep")

        result = invoke(source, outside, "-y")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(valuable.read_bytes(), b"keep")

    def test_missing_destination_submodule_is_initialized_only_on_apply(self) -> None:
        source = self.source_with_submodule()
        dest = self.root / "dest"
        clone_repo(source, dest)

        dry = invoke(source, dest)
        self.assertEqual(dry.returncode, 0, dry.stderr + dry.stdout)
        self.assertIn("Destination Git worktrees to initialize (1)", dry.stdout)
        self.assertFalse((dest / "module" / ".git").exists())

        applied = invoke(source, dest, "-y")
        self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
        self.assertEqual((dest / "module" / "child.txt").read_text(), "child\n")
        self.assertEqual(
            Path(
                run(["git", "rev-parse", "--show-toplevel"], cwd=dest / "module").stdout.strip()
            ).resolve(),
            (dest / "module").resolve(),
        )
        self.assertEqual(
            run(["git", "rev-parse", "HEAD"], cwd=dest / "module").stdout,
            run(["git", "rev-parse", "HEAD"], cwd=source / "module").stdout,
        )
        self.assertEqual(
            run(["git", "write-tree"], cwd=dest / "module").stdout,
            run(["git", "write-tree"], cwd=source / "module").stdout,
        )
        self.assertEqual(
            run(
                ["git", "symbolic-ref", "-q", "HEAD"],
                cwd=dest / "module",
                check=False,
            ).returncode,
            1,
        )

    def test_bare_destination_submodule_is_rejected(self) -> None:
        source = self.source_with_submodule()
        dest = self.root / "dest"
        clone_repo(source, dest)
        run(["git", "init", "--bare", "-q", str(dest / "module")])

        result = invoke(source, dest)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Destination Git root is bare", result.stderr + result.stdout)

    def test_unknown_git_filter_is_rejected(self) -> None:
        source = self.root / "source"
        dest = self.root / "dest"
        init_repo(source)
        (source / ".gitattributes").write_text("*.dat filter=custom\n")
        (source / "asset.dat").write_text("placeholder\n")
        commit_all(source)
        clone_repo(source, dest)

        result = invoke(source, dest, "-y")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown Git filters", result.stderr + result.stdout)

    def test_rsync_failure_before_first_write_keeps_checkout_and_extras(self) -> None:
        source, dest = self.basic_pair()
        (source / "tracked.txt").write_text("new\n")
        commit_all(source)
        extra = dest / "extra.txt"
        extra.write_text("keep\n")
        head_before = run(["git", "rev-parse", "HEAD"], cwd=dest).stdout
        index_before = run(["git", "write-tree"], cwd=dest).stdout
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_rsync = fake_bin / "rsync"
        fake_rsync.write_text("#!/bin/sh\nexit 37\n")
        fake_rsync.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

        result = invoke(source, dest, "-y", env=env)
        self.assertEqual(result.returncode, 37, result.stderr + result.stdout)
        self.assertEqual(extra.read_text(), "keep\n")
        self.assertEqual((dest / "tracked.txt").read_text(), "base\n")
        self.assertEqual(run(["git", "rev-parse", "HEAD"], cwd=dest).stdout, head_before)
        self.assertEqual(run(["git", "write-tree"], cwd=dest).stdout, index_before)
        self.assertEqual(
            run(["git", "rev-parse", "refs/rsync-repo/head"], cwd=dest).stdout,
            run(["git", "rev-parse", "HEAD"], cwd=source).stdout,
        )
        self.assertIn("destination mutation began", result.stderr)

    @unittest.skipUnless(shutil.which("rsync"), "requires rsync")
    def test_phase_heading_is_flushed_before_rsync_output(self) -> None:
        source, dest = self.basic_pair()
        fake_bin = self.root / "ordered-rsync-bin"
        fake_bin.mkdir()
        fake_rsync = fake_bin / "rsync"
        real_rsync = shutil.which("rsync")
        assert real_rsync
        fake_rsync.write_text(
            "#!/bin/sh\n"
            f"real={shlex.quote(real_rsync)}\n"
            'for arg do test "$arg" = --server && exec "$real" "$@"; done\n'
            "echo RSYNC-START\n"
            'exec "$real" "$@"\n'
        )
        fake_rsync.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

        result = invoke(source, dest, env=env)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertLess(
            result.stdout.index("Phase: preview final worktree changes"),
            result.stdout.index("RSYNC-START"),
        )

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires mkfifo")
    def test_nonignored_special_source_node_is_rejected(self) -> None:
        source, dest = self.basic_pair()
        os.mkfifo(source / "runtime.pipe")
        (dest / "runtime.pipe").write_text("must remain\n")

        result = invoke(source, dest, "-y")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((dest / "runtime.pipe").read_text(), "must remain\n")

    def test_sparse_checkout_is_rejected(self) -> None:
        source = self.root / "source"
        dest = self.root / "dest"
        init_repo(source)
        (source / "keep").mkdir()
        (source / "keep" / "a.txt").write_text("a\n")
        (source / "drop").mkdir()
        (source / "drop" / "b.txt").write_text("b\n")
        commit_all(source)
        clone_repo(source, dest)
        git(source, "sparse-checkout", "init", "--cone")
        git(source, "sparse-checkout", "set", "keep")

        result = invoke(source, dest, "-y")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Sparse/skip-worktree", result.stderr + result.stdout)

    def test_unresolved_index_entries_are_rejected_with_their_path(self) -> None:
        source, dest = self.basic_pair()
        (source / "ours.txt").write_text("ours\n")
        (source / "theirs.txt").write_text("theirs\n")
        base = run(["git", "rev-parse", "HEAD:tracked.txt"], cwd=source).stdout.strip()
        ours = run(["git", "hash-object", "-w", "ours.txt"], cwd=source).stdout.strip()
        theirs = run(["git", "hash-object", "-w", "theirs.txt"], cwd=source).stdout.strip()
        git(source, "rm", "--cached", "-q", "tracked.txt")
        run(
            ["git", "update-index", "--index-info"],
            cwd=source,
            input_data=(
                f"100644 {base} 1\ttracked.txt\n"
                f"100644 {ours} 2\ttracked.txt\n"
                f"100644 {theirs} 3\ttracked.txt\n"
            ),
        )

        result = invoke(source, dest)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unresolved index entries are unsupported: tracked.txt", result.stderr)
        self.assertEqual((dest / "tracked.txt").read_text(), "base\n")

    @unittest.skipUnless(shutil.which("git"), "requires git")
    def test_dry_run_does_not_materialize_the_source_index_tree(self) -> None:
        source, dest = self.basic_pair()
        (source / "new.txt").write_text("new\n")
        git(source, "add", "new.txt")
        marker = self.root / "write-tree-called"
        fake_bin = self.root / "observed-git-bin"
        fake_bin.mkdir()
        fake_git = fake_bin / "git"
        real_git = shutil.which("git")
        assert real_git
        fake_git.write_text(
            "#!/bin/sh\n"
            f'test "$1" != write-tree || touch {shlex.quote(str(marker))}\n'
            f'exec {shlex.quote(real_git)} "$@"\n'
        )
        fake_git.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")

        result = invoke(source, dest, env=env)

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(marker.exists())

    def test_ssh_option_injection_is_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            module.parse_endpoint("-oProxyCommand=bad:/tmp/repo")

    def test_old_cli_shape_reports_the_direction_migration(self) -> None:
        source, dest = self.basic_pair()

        result = run(
            [sys.executable, str(SCRIPT), "-y", str(dest)],
            cwd=source,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("missing direction", result.stderr)
        self.assertIn("push [-y] ENDPOINT", result.stderr)

    def test_ssh_failure_is_not_misreported_as_a_git_root_problem(self) -> None:
        source, _ = self.basic_pair()

        result = run(
            [sys.executable, str(SCRIPT), "push", "broken:/repo"],
            cwd=source,
            env=self.fake_ssh_env(fail=True),
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("simulated SSH failure", result.stderr)
        self.assertIn("Failed to inspect Git worktree", result.stderr)
        self.assertNotIn("not an exact Git worktree root", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
