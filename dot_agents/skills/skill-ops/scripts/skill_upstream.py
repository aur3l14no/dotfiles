# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit>=0.13"]
# ///
"""Vendor third-party skills into the chezmoi source and merge upstream updates into them.

Third-party skills sit in the chezmoi source next to self-owned ones, already adapted, as
`exact_<name>/` directories that chezmoi deploys. The manifest `.upstream.toml` beside them
(chezmoi ignores dotfiles in the source) records where each comes from:

  [[source]]
  repo = "larksuite/cli"               # GitHub owner/name
  ref = "^1.0.0"                       # ^ or ~ range over semver tags, a branch, a tag or a commit
  commit = "ac81f50..."                # written by `update`: the upstream the vendored copies are based on
  skills = ["skills/lark-doc", "..."]  # skill dirs in the repo; "." is the repo root

Commands:
  status [SKILL...]          vendored copies against upstream at `commit`
  update [--dry-run] [SKILL...]
                             move each source to the newest commit its ref allows and vendor
                             missing skills; local adaptations are merged three-way, conflicts are
                             left as markers in the source; naming a skill selects its whole source
  diff SKILL                 local adaptation as a diff against upstream at `commit`
  upstream SKILL DIR         write clean upstream at `commit` to DIR, e.g. for a full adaptation pass
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import tomlkit

HOME = Path.home()
CACHE = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "skill-upstream"
DEPLOY = HOME / ".agents/skills"
IGNORED = {".DS_Store"}
MD_LINK = re.compile(rb"\]\(([^)\s#]+)")
MARKER = b"<<<<<<< local"
# Invisible characters that can hide instructions from a reviewer: zero-width, bidi controls, tag characters.
HIDDEN = re.compile("[​‌‍⁠-⁤‪-‮⁦-⁩\U000e0000-\U000e007f]")
# chezmoi source-state attributes; upstream names that start or end with one are escaped.
PREFIXES = ("after_", "before_", "create_", "dot_", "empty_", "encrypted_", "exact_", "executable_",
            "external_", "literal_", "modify_", "once_", "onchange_", "private_", "readonly_",
            "remove_", "run_", "symlink_")
SUFFIXES = (".tmpl", ".literal", ".age", ".asc")
SEMVER = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")
# A release tag, possibly prefixed as in monorepos: v1.2.3, cua-driver-rs-v0.36.0.
RELEASE = re.compile(r"(.*?)(\d+)\.(\d+)\.(\d+)")

Tree = dict[str, bytes]


def source_root() -> Path:
    if root := os.environ.get("SKILL_UPSTREAM_SOURCE"):
        return Path(root)
    out = subprocess.run(["chezmoi", "source-path"], capture_output=True, text=True, check=True)
    return Path(out.stdout.strip())


SKILLS = source_root() / "dot_agents/skills"
MANIFEST = SKILLS / ".upstream.toml"


def git(*args, cwd=None, check=True) -> subprocess.CompletedProcess:
    env = {**os.environ, "GIT_CEILING_DIRECTORIES": str(Path(tempfile.gettempdir()).resolve())}
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, env=env)
    if check and r.returncode:
        sys.exit(f"git {' '.join(args)}: {r.stderr.decode().strip()}")
    return r


# --- manifest -----------------------------------------------------------------


def load_manifest() -> tuple[tomlkit.TOMLDocument, dict[str, tuple[dict, str]]]:
    """Return the document and skill name -> (source table, path in repo)."""
    doc = tomlkit.parse(MANIFEST.read_text())
    skills: dict[str, tuple[dict, str]] = {}
    for src in doc.get("source", []):
        for path in src["skills"]:
            name = src["repo"].rsplit("/", 1)[-1] if path == "." else path.rstrip("/").rsplit("/", 1)[-1]
            if name in skills or (SKILLS / name).exists():
                sys.exit(f"{MANIFEST}: skill {name} listed twice or also self-owned")
            skills[name] = (src, "" if path == "." else path.strip("/"))
    return doc, skills


def selected_sources(doc, skills, names: list[str]) -> list[dict]:
    for n in names:
        if n not in skills:
            sys.exit(f"{n}: not in {MANIFEST}")
    wanted = {id(skills[n][0]) for n in names}
    return [s for s in doc.get("source", []) if not names or id(s) in wanted]


def skills_of(src, skills) -> list[tuple[str, str]]:
    return [(n, p) for n, (s, p) in skills.items() if s is src]


# --- upstream -----------------------------------------------------------------


def repo_cache(repo: str, commit: str) -> Path:
    path = CACHE / "git" / f"{repo.lower()}.git"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        git("init", "-q", "--bare", str(path))
    if git("cat-file", "-e", f"{commit}^{{commit}}", cwd=path, check=False).returncode:
        git("fetch", "-q", "--depth", "1", f"https://github.com/{repo}.git", commit, cwd=path)
    return path


def upstream_tree(repo: str, commit: str, path: str) -> tuple[Tree, set[str]]:
    """Files of `path` at `commit`, and which of them are executable."""
    data = git("archive", "--format=tar", commit, *([path] if path else []), cwd=repo_cache(repo, commit)).stdout
    prefix = f"{path}/" if path else ""
    tree: Tree = {}
    execs: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        for m in tar:
            rel = m.name[len(prefix):]
            if m.isfile() and m.name.startswith(prefix) and rel.rsplit("/", 1)[-1] not in IGNORED:
                tree[rel] = tar.extractfile(m).read()
                if m.mode & 0o111:
                    execs.add(rel)
    return tree, execs


def subtree_id(repo: str, commit: str, path: str) -> str:
    """Git tree id of a skill dir, to tell whether it changed between commits."""
    spec = f"{commit}:{path}" if path else f"{commit}^{{tree}}"
    return git("rev-parse", "-q", "--verify", spec, cwd=repo_cache(repo, commit), check=False).stdout.decode().strip()


def has_skill(repo: str, commit: str, path: str) -> bool:
    spec = f"{commit}:{path}/SKILL.md" if path else f"{commit}:SKILL.md"
    return not git("cat-file", "-e", spec, cwd=repo_cache(repo, commit), check=False).returncode


_refs: dict[str, dict[str, str]] = {}


def remote_refs(repo: str) -> dict[str, str]:
    if repo not in _refs:
        out = git("ls-remote", "--symref", f"https://github.com/{repo}.git", "HEAD", "refs/heads/*", "refs/tags/*")
        refs: dict[str, str] = {}
        for line in out.stdout.decode().splitlines():
            if line.startswith("ref: "):
                refs["HEAD-branch"] = line.split()[1]
                continue
            sha, ref = line.split("\t")
            refs[ref.removesuffix("^{}")] = sha  # a peeled tag line follows its tag and wins
        _refs[repo] = refs
    return _refs[repo]


def semver_tags(repo: str, prefixes=("", "v")) -> list[tuple[tuple[int, int, int], str, str]]:
    tags = []
    for ref, sha in remote_refs(repo).items():
        name = ref.removeprefix("refs/tags/")
        if ref.startswith("refs/tags/") and (m := RELEASE.fullmatch(name)) and m[1] in prefixes:
            tags.append((tuple(map(int, m.groups()[1:])), name, sha))
    return sorted(tags)


def resolve(src) -> tuple[str, str | None, bool]:
    """(commit, tag or None, moving) for the source's ref; moving refs follow upstream on update."""
    repo, ref = src["repo"], str(src["ref"])
    if ref[:1] in "^~":
        low = tuple(map(int, SEMVER.fullmatch(ref[1:]).groups()))
        if ref[0] == "~":
            high = (low[0], low[1] + 1, 0)
        else:
            i = next((i for i, v in enumerate(low) if v), 2)  # ^0.8.0 stays below 0.9.0
            high = tuple(v + 1 if j == i else (v if j < i else 0) for j, v in enumerate(low))
        hits = [(v, t, s) for v, t, s in semver_tags(repo) if low <= v < high]
        if not hits:
            sys.exit(f"{repo}: no tag matches {ref}")
        return hits[-1][2], hits[-1][1], True
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return ref, None, False
    refs = remote_refs(repo)
    if f"refs/tags/{ref}" in refs:
        return refs[f"refs/tags/{ref}"], ref, False
    if f"refs/heads/{ref}" in refs:
        return refs[f"refs/heads/{ref}"], None, True
    sys.exit(f"{repo}: ref {ref} not found")


def newer_than_pin(src) -> tuple[str, str] | None:
    """For a pinned ref, what upstream has moved on to: the latest release with the same prefix for a
    release tag, the default branch head for a commit."""
    repo, ref = src["repo"], str(src["ref"])
    refs = remote_refs(repo)
    if f"refs/tags/{ref}" in refs and (m := RELEASE.fullmatch(ref)):
        tags = semver_tags(repo, (m[1],))
        return (tags[-1][1], tags[-1][2]) if tags[-1][1] != ref else None
    branch = refs.get("HEAD-branch", "")
    if branch in refs and refs[branch] != src["commit"]:
        return branch.removeprefix("refs/heads/"), refs[branch]
    return None


# --- vendored copies ----------------------------------------------------------


def encode(rel: str, executable: bool) -> str:
    parts = []
    for i, p in enumerate(rel.split("/")):
        if p.startswith("."):
            p = "dot_" + p[1:]
        elif p.startswith(PREFIXES):
            p = "literal_" + p
        if i == rel.count("/"):
            if executable:
                p = "executable_" + p
            if p.endswith(SUFFIXES):
                p += ".literal"
        parts.append(p)
    return "/".join(parts)


def decode(rel: str) -> str:
    parts = []
    for i, p in enumerate(rel.split("/")):
        if i == rel.count("/"):
            p = p.removesuffix(".literal").removeprefix("executable_")
        if p.startswith("literal_"):
            p = p[len("literal_"):]
        elif p.startswith("dot_"):
            p = "." + p[len("dot_"):]
        parts.append(p)
    return "/".join(parts)


def vendored_dir(name: str) -> Path:
    return SKILLS / f"exact_{name}"


def read_tree(root: Path, source: bool) -> Tree:
    tree: Tree = {}
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in IGNORED:
            rel = p.relative_to(root).as_posix()
            tree[decode(rel) if source else rel] = p.read_bytes()
    return tree


def write_vendored(name: str, tree: Tree, execs: set[str]) -> None:
    root = vendored_dir(name)
    shutil.rmtree(root, ignore_errors=True)
    for rel, data in tree.items():
        p = root / encode(rel, rel in execs)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)


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
        else:  # edited on one side, deleted on the other: keep the edit, let the reviewer decide
            conflicts.append(f"{rel} (deleted {'upstream' if b is None else 'locally'})")
            res = a if a is not None else b
        if res is not None:
            result[rel] = res
    return result, conflicts


def changed(a: Tree, b: Tree) -> list[str]:
    return sorted(k for k in a.keys() | b.keys() if a.get(k) != b.get(k))


def hidden(tree: Tree, only: list[str] | None = None) -> list[str]:
    hits = []
    for rel in only if only is not None else sorted(tree):
        for n, line in enumerate(tree.get(rel, b"").decode("utf-8", "ignore").splitlines(), 1):
            for m in HIDDEN.finditer(line):
                hits.append(f"{rel}:{n} U+{ord(m.group()):04X}")
    return hits


def missing_links(name: str, tree: Tree) -> list[str]:
    """Markdown links out of the skill whose target is not deployed, e.g. sibling skills not installed."""
    out = set()
    for rel, data in tree.items():
        if rel.endswith(".md"):
            for m in MD_LINK.finditer(data):
                link = m.group(1).decode()
                if "://" in link or link.startswith(("/", "mailto:")):
                    continue
                target = os.path.normpath(DEPLOY / name / Path(rel).parent / link)
                if not target.startswith(f"{DEPLOY / name}/") and not Path(target).exists():
                    out.add(os.path.relpath(target, DEPLOY))
    return sorted(out)


# --- commands -----------------------------------------------------------------


def cmd_status(names: list[str]) -> int:
    doc, skills = load_manifest()
    for name in names or sorted(skills):
        if name not in skills:
            sys.exit(f"{name}: not in {MANIFEST}")
        src, path = skills[name]
        if "commit" not in src or not vendored_dir(name).is_dir():
            print(f"{'missing':<10} {name}  (run update)")
            continue
        ours = read_tree(vendored_dir(name), source=True)
        base, _ = upstream_tree(src["repo"], src["commit"], path)
        diff = changed(base, ours)
        marked = [r for r, d in ours.items() if MARKER in d]
        state = "conflict" if marked else "adapted" if diff else "clean"
        notes = [f"{len(diff)} files differ from {src['repo']}@{src['commit'][:8]}"] if diff else []
        if marked:
            notes.append(f"markers in {', '.join(marked)}")
        if DEPLOY.joinpath(name).is_dir() and read_tree(DEPLOY / name, source=False) != ours:
            notes.append("not applied")
        print(f"{state:<10} {name}  {'; '.join(notes)}".rstrip())
        for label, items in (("hidden", hidden(ours)), ("links to missing", missing_links(name, ours))):
            if items:
                print(f"{'':<10}   {label}: {', '.join(items)}")
    if not names:
        for p in sorted(SKILLS.glob("exact_*")):
            if p.name[len("exact_"):] not in skills:
                print(f"{'orphan':<10} {p.name[len('exact_'):]}  (vendored but not in the manifest)")
    return 0


def cmd_update(names: list[str], dry_run: bool) -> int:
    doc, skills = load_manifest()
    failed = 0
    for src in selected_sources(doc, skills, names):
        repo, current = src["repo"], src.get("commit")
        target, tag, moving = resolve(src)
        label = f"{repo} {src['ref']}"
        todo = [(n, p) for n, p in skills_of(src, skills) if target != current or not vendored_dir(n).is_dir()]
        if current is None and any(vendored_dir(n).is_dir() for n, _ in todo):
            sys.exit(f"{label}: vendored skills exist but the manifest has no commit to merge from")
        if not moving and target == current and (hint := newer_than_pin(src)):
            touched = [n for n, p in skills_of(src, skills) if subtree_id(repo, current, p) != subtree_id(repo, hint[1], p)]
            if touched:
                print(f"pinned   {label}: {hint[0]} changes {', '.join(touched)}; edit ref to move")
        if not todo:
            continue
        version = tag or target[:8]
        if lost := [n for n, p in todo if not has_skill(repo, target, p)]:
            failed += 1
            print(f"moved    {label}: no SKILL.md for {', '.join(lost)} at {version}; fix their paths in the manifest")
            continue
        if dry_run:
            moved = [n for n, p in todo if not current or not vendored_dir(n).is_dir()
                     or subtree_id(repo, current, p) != subtree_id(repo, target, p)]
            print(f"would    {label}: {(current or 'none')[:8]} -> {version}; skills: {', '.join(moved) or 'none changed'}")
            continue
        for name, path in todo:
            new, execs = upstream_tree(repo, target, path)
            incoming = changed({}, new)
            if not vendored_dir(name).is_dir():
                write_vendored(name, new, execs)
                print(f"added    {name}: clean upstream {version}; adapt and review before committing")
            else:
                old, _ = upstream_tree(repo, current, path)
                incoming = changed(old, new)
                merged, conflicts = merge3(old, read_tree(vendored_dir(name), source=True), new)
                write_vendored(name, merged, execs)
                if conflicts:
                    failed += 1
                    print(f"conflict {name}: {', '.join(conflicts)}")
                else:
                    print(f"merged   {name}: {current[:8]} -> {version}; upstream delta: {', '.join(incoming) or 'none'}")
            if hits := hidden(new, [r for r in incoming if r in new]):
                failed += 1
                print(f"hidden   {name}: {', '.join(hits)}")
        src["commit"] = tomlkit.string(target)
        if tag:
            src["commit"].comment(tag)
        MANIFEST.write_text(tomlkit.dumps(doc))
    return 1 if failed else 0


def recorded_upstream(name: str) -> Tree:
    _, skills = load_manifest()
    if name not in skills or "commit" not in skills[name][0]:
        sys.exit(f"{name}: not vendored from {MANIFEST}")
    src, path = skills[name]
    return upstream_tree(src["repo"], src["commit"], path)[0]


def write_plain(root: Path, tree: Tree) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in tree.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)


def cmd_diff(name: str) -> int:
    base = recorded_upstream(name)
    with tempfile.TemporaryDirectory() as tmp:
        write_plain(Path(tmp, "upstream"), base)
        write_plain(Path(tmp, "local"), read_tree(vendored_dir(name), source=True))
        return subprocess.run(["git", "diff", "--no-index", "upstream", "local"], cwd=tmp).returncode


def cmd_upstream(name: str, dest: Path) -> int:
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"{dest}: not empty")
    write_plain(dest, recorded_upstream(name))
    print(f"clean upstream of {name} written to {dest}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status").add_argument("skills", nargs="*")
    p = sub.add_parser("update")
    p.add_argument("skills", nargs="*")
    p.add_argument("--dry-run", action="store_true")
    sub.add_parser("diff").add_argument("skill")
    p = sub.add_parser("upstream")
    p.add_argument("skill")
    p.add_argument("dest", type=Path)
    a = ap.parse_args()
    if a.cmd == "status":
        return cmd_status(a.skills)
    if a.cmd == "update":
        return cmd_update(a.skills, a.dry_run)
    if a.cmd == "upstream":
        return cmd_upstream(a.skill, a.dest)
    return 1 if cmd_diff(a.skill) > 1 else 0


if __name__ == "__main__":
    sys.exit(main())
