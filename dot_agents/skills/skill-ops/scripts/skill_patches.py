# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Keep local adaptations of APM-managed skills as replayable patches.

Each patched skill stores, in the chezmoi source tree:
  <store>/<skill>/base.json      upstream host, repo, path, deployed files and the commit the patch is against
  <store>/<skill>/changes.patch  diff from that clean upstream to the adapted skill

Commands:
  status [SKILL...]   compare deployed skills with the locked upstream and stored patches
  capture SKILL...    record deployed SKILL as a patch against the locked upstream
  apply [SKILL...]    replay patches after `apm install` / `apm update` (three-way merge on
                      upstream changes); conflicts go to a work dir and the deployment is
                      left untouched
"""

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

HOME = Path.home()
LOCK = Path(os.environ.get("SKILL_PATCHES_LOCK", HOME / ".apm/apm.lock.yaml"))
DEPLOY = Path(os.environ.get("SKILL_PATCHES_DEPLOY", HOME / ".agents/skills"))
STORE = Path(os.environ.get("SKILL_PATCHES_DIR", HOME / ".nix-config/chezmoi/dot_apm/patches"))
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "skill-patches"
APM_MODULES = LOCK.parent / "apm_modules"
IGNORED = {".DS_Store"}
MD_LINK = re.compile(rb"\]\(([^)\s#]+)")

Tree = dict[str, bytes]


def git(*args, cwd=None, check=True, input=None) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tempfile.gettempdir()).resolve())}
    return subprocess.run(["git", *args], cwd=cwd, check=check, input=input, capture_output=True, env=env)


# --- lockfile -----------------------------------------------------------------


def locked_skills() -> dict[str, dict]:
    """Map deployed skill name -> {host, repo, commit, vpath, files}."""
    skills: dict[str, dict] = {}
    for dep in yaml.safe_load(LOCK.read_text())["dependencies"]:
        for key in dep.get("deployed_file_hashes") or {}:
            parts = key.split("/", 3)  # .agents / skills / <name> / <rest>
            if parts[:2] != [".agents", "skills"] or len(parts) < 4:
                continue
            s = skills.setdefault(parts[2], {
                "host": dep.get("host", "github.com"),
                "repo": dep["repo_url"],
                "commit": dep["resolved_commit"],
                "vpath": dep.get("virtual_path"),
                "files": set(),
            })
            s["files"].add(parts[3])
    return skills


# --- upstream source ----------------------------------------------------------


def repo_cache(host: str, repo: str, commit: str) -> Path:
    path = CACHE / "git" / host / f"{repo}.git"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "--bare", str(path))
    if git("cat-file", "-e", f"{commit}^{{commit}}", cwd=path, check=False).returncode:
        git("fetch", "-q", "--depth", "1", f"https://{host}/{repo}.git", commit, cwd=path)
    return path


def source_path(name: str, host: str, repo: str, commit: str, vpath: str | None) -> str:
    """Directory of skill `name` inside the upstream repo ('' for the repo root)."""
    if vpath:
        return vpath.strip("/")
    files = git("ls-tree", "-r", "--name-only", commit, cwd=repo_cache(host, repo, commit)).stdout.decode().splitlines()
    if "SKILL.md" in files and repo.rsplit("/", 1)[-1] == name:
        return ""
    if f"skills/{name}/SKILL.md" in files:
        return f"skills/{name}"
    hits = sorted(f[: -len("/SKILL.md")] for f in files if f.endswith(f"/{name}/SKILL.md"))
    if len(hits) != 1:
        sys.exit(f"{name}: cannot locate skill in {repo}@{commit[:8]} (candidates: {hits})")
    return hits[0]


def upstream_tree(host: str, repo: str, commit: str, path: str, only: set[str] | None = None) -> Tree:
    cache = repo_cache(host, repo, commit)
    spec = [path] if path else []
    data = git("archive", "--format=tar", commit, *spec, cwd=cache).stdout
    prefix = f"{path}/" if path else ""
    tree: Tree = {}
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar:
            if m.isfile() and m.name.startswith(prefix):
                rel = m.name[len(prefix):]
                if only is None or rel in only:
                    tree[rel] = tar.extractfile(m).read()
    return tree


# --- trees and patches --------------------------------------------------------


def read_tree(root: Path) -> Tree:
    tree: Tree = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and p.name not in IGNORED and ".git" not in p.relative_to(root).parts:
            tree[rel] = p.read_bytes()
    return tree


def write_tree(root: Path, tree: Tree) -> None:
    for rel, data in tree.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


def make_patch(base: Tree, work: Tree) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        write_tree(Path(tmp, "base"), base)
        write_tree(Path(tmp, "work"), work)
        Path(tmp, "base").mkdir(exist_ok=True)
        Path(tmp, "work").mkdir(exist_ok=True)
        r = git("diff", "--no-index", "--binary", "--no-prefix", "base", "work", cwd=tmp, check=False)
        if r.returncode > 1:
            sys.exit(r.stderr.decode())
        return r.stdout


def apply_patch(base: Tree, patch: bytes) -> Tree:
    if not patch.strip():
        return dict(base)
    with tempfile.TemporaryDirectory() as tmp:
        write_tree(Path(tmp), base)
        r = git("apply", "-p1", "--whitespace=nowarn", "-", cwd=tmp, check=False, input=patch)
        if r.returncode:
            raise RuntimeError(r.stderr.decode().strip())
        return read_tree(Path(tmp))


def merge3(old: Tree, ours: Tree, new: Tree) -> tuple[Tree, list[str]]:
    result: Tree = {}
    conflicts: list[str] = []
    for rel in sorted(old.keys() | ours.keys() | new.keys()):
        o, a, b = old.get(rel), ours.get(rel), new.get(rel)
        if a == o:
            res = b
        elif b == o or a == b:
            res = a
        elif None not in (o, a, b):
            with tempfile.TemporaryDirectory() as tmp:
                for n, d in (("ours", a), ("base", o), ("theirs", b)):
                    Path(tmp, n).write_bytes(d)
                r = subprocess.run(
                    ["git", "merge-file", "-p", "-L", "local", "-L", "old-upstream", "-L", "new-upstream",
                     "ours", "base", "theirs"], cwd=tmp, capture_output=True)
                res = r.stdout
                if r.returncode:
                    conflicts.append(rel)
        else:
            conflicts.append(rel)
            res = a if a is not None else b
        if res is not None:
            result[rel] = res
    return result, conflicts


def changed(a: Tree, b: Tree) -> list[str]:
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))


# --- stored patches -----------------------------------------------------------


def load_patch(name: str) -> tuple[dict, bytes] | None:
    d = STORE / name
    if not (d / "base.json").exists():
        return None
    return json.loads((d / "base.json").read_text()), (d / "changes.patch").read_bytes()


def save_patch(name: str, meta: dict, patch: bytes) -> None:
    d = STORE / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "base.json").write_text(json.dumps(meta, indent=2) + "\n")
    (d / "changes.patch").write_bytes(patch)


def replace_deployed(name: str, meta: dict, tree: Tree) -> None:
    root = DEPLOY / name
    for rel in read_tree(root).keys() - tree.keys():
        (root / rel).unlink()
    write_tree(root, rewrite_links(name, meta, tree))


# --- commands -----------------------------------------------------------------


def resolve(name: str, lock: dict) -> tuple[dict, Tree, Tree]:
    s = lock.get(name)
    if s is None:
        sys.exit(f"{name}: not an APM-managed skill in {LOCK}")
    meta = {"host": s["host"], "repo": s["repo"], "commit": s["commit"],
            "path": source_path(name, s["host"], s["repo"], s["commit"], s["vpath"]),
            "files": sorted(s["files"])}
    base = upstream_tree(meta["host"], meta["repo"], meta["commit"], meta["path"], s["files"])
    return meta, base, unrewrite_links(name, meta, read_tree(DEPLOY / name))


def _map_links(tree: Tree, fn) -> Tree:
    out: Tree = {}
    for rel, data in tree.items():
        if rel.endswith(".md"):
            def sub(m: re.Match) -> bytes:
                link = m.group(1).decode()
                if "://" in link or link.startswith(("/", "mailto:")):
                    return m.group(0)
                new = fn(rel, link)
                return m.group(0) if new is None else b"](" + new.encode()
            data = MD_LINK.sub(sub, data)
        out[rel] = data
    return out


def rewrite_links(name: str, meta: dict, tree: Tree) -> Tree:
    """Apply APM's deploy-time rewrite: links leaving the skill bundle point into apm_modules."""
    source = APM_MODULES / meta["repo"] / meta["path"]

    def fn(rel: str, link: str) -> str | None:
        target = os.path.normpath((source / rel).parent / link)
        if target.startswith(f"{source}/"):
            return None
        return os.path.relpath(target, (DEPLOY / name / rel).parent)
    return _map_links(tree, fn)


def unrewrite_links(name: str, meta: dict, tree: Tree) -> Tree:
    """Inverse of rewrite_links, so deployments compare and patch against plain upstream."""
    source = APM_MODULES / meta["repo"] / meta["path"]

    def fn(rel: str, link: str) -> str | None:
        target = os.path.normpath(DEPLOY / name / Path(rel).parent / link)
        if not target.startswith(f"{APM_MODULES}/"):
            return None
        return os.path.relpath(target, (source / rel).parent)
    return _map_links(tree, fn)


def cmd_status(names: list[str]) -> int:
    lock = locked_skills()
    stored = {p.name for p in STORE.iterdir()} if STORE.exists() else set()
    for live, src in ((LOCK.parent / "apm.yml", STORE.parent / "apm.yml"),
                      (LOCK, STORE.parent / "private_apm.lock.yaml")):
        if src.exists() and live.read_bytes() != src.read_bytes():
            print(f"unsynced    {live}  (chezmoi re-add {live})")
    for name in names or sorted(lock.keys() | stored):
        if name not in lock:
            print(f"orphan      {name}  (patch stored, skill no longer in lock)")
            continue
        if not (DEPLOY / name).is_dir():
            print(f"missing     {name}  (in lock but not deployed)")
            continue
        meta, base, deployed = resolve(name, lock)
        record = load_patch(name)
        if record is None:
            state = "unreviewed" + ("" if deployed == base else f"  ({len(changed(base, deployed))} files differ from upstream)")
        elif record[0]["commit"] != meta["commit"]:
            state = f"rebase      (patch on {record[0]['commit'][:8]}, locked {meta['commit'][:8]})"
        else:
            try:
                ours = apply_patch(base, record[1])
            except RuntimeError:
                ours = None
            if deployed == ours:
                state = "captured" + ("" if record[1].strip() else "  (no changes needed)")
            elif deployed == base:
                state = "pending     (fresh upstream; run apply)"
            else:
                state = "uncaptured  (deployed differs from stored patch)"
        head, _, rest = state.partition(" ")
        print(f"{head:<11} {name}  {rest.strip()}".rstrip())
    return 0


def cmd_capture(names: list[str]) -> int:
    lock = locked_skills()
    for name in names:
        meta, base, deployed = resolve(name, lock)
        patch = make_patch(base, deployed)
        if apply_patch(base, patch) != deployed:
            sys.exit(f"{name}: patch does not reproduce the deployed skill; not saved")
        save_patch(name, meta, patch)
        files = changed(base, deployed)
        print(f"captured {name}: {len(files)} files vs {meta['repo']}@{meta['commit'][:8]}" if files
              else f"captured {name}: no changes needed")
    return 0


def cmd_apply(names: list[str], force: bool) -> int:
    lock = locked_skills()
    names = names or sorted(p.name for p in STORE.iterdir() if (p / "base.json").exists())
    failed = 0
    for name in names:
        stored = load_patch(name)
        if stored is None:
            print(f"skip     {name}: no stored patch")
            continue
        old_meta, patch = stored
        meta, new, deployed = resolve(name, lock)
        if old_meta["commit"] == meta["commit"]:
            ours = apply_patch(new, patch)
            if deployed not in (new, ours) and not force:
                print(f"refuse   {name}: deployed has uncaptured edits; capture or redeploy first")
                failed += 1
                continue
            replace_deployed(name, meta, ours)
            print(f"applied  {name}")
            continue
        old = upstream_tree(old_meta["host"], old_meta["repo"], old_meta["commit"], old_meta["path"], set(old_meta["files"]))
        if deployed != new and not force:
            print(f"refuse   {name}: deployed is not the fresh upstream {meta['commit'][:8]}; redeploy first")
            failed += 1
            continue
        ours = apply_patch(old, patch)
        merged, conflicts = merge3(old, ours, new)
        delta = changed(old, new)
        if conflicts:
            work = CACHE / "work" / name
            shutil.rmtree(work, ignore_errors=True)
            write_tree(work, merged)
            print(f"conflict {name}: {', '.join(conflicts)}; merged tree with markers in {work}")
            failed += 1
            continue
        replace_deployed(name, meta, merged)
        save_patch(name, meta, make_patch(new, merged))
        print(f"merged   {name}: {old_meta['commit'][:8]} -> {meta['commit'][:8]}; review upstream delta: {', '.join(delta) or 'none'}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").add_argument("skills", nargs="*")
    sub.add_parser("capture").add_argument("skills", nargs="+")
    p = sub.add_parser("apply")
    p.add_argument("skills", nargs="*")
    p.add_argument("--force", action="store_true", help="overwrite a deployment that is not clean upstream")
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status(a.skills)
    if a.cmd == "capture":
        return cmd_capture(a.skills)
    return cmd_apply(a.skills, a.force)


if __name__ == "__main__":
    sys.exit(main())
