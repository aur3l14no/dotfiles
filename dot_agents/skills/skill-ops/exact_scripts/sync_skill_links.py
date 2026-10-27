# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Expose shared skills to Claude without sharing either client's private root."""

import argparse
import os
from pathlib import Path


def link_target(path: Path) -> Path | None:
    if path.is_symlink():
        return Path(os.path.abspath(path.parent / path.readlink()))
    return None


def sync_skills(home: Path, dry_run: bool = False) -> None:
    shared = home / ".agents/skills"
    claude = home / ".claude/skills"
    # Migrate the old whole-directory link left behind by chezmoi.
    migrate = link_target(claude) == shared
    if migrate:
        print(f"unlink {claude}")
        if not dry_run:
            claude.unlink()
    for private in (claude, home / ".codex/skills"):
        if private.is_symlink() and not (migrate and private == claude):
            raise SystemExit(f"Expected an independent directory: {private}")
    if not shared.is_dir():
        raise SystemExit(f"Shared skills directory is missing: {shared}")

    # A skills-directory plugin has no SKILL.md of its own; Claude loads it from its manifest.
    skills = {
        path.name: path
        for path in shared.iterdir()
        if not path.name.startswith(".")
        and path.name.lower() != "synced"
        and ((path / "SKILL.md").is_file() or (path / ".claude-plugin/plugin.json").is_file())
    }
    missing = []
    for name, source in sorted(skills.items()):
        target = claude / name
        if link_target(target) == source:
            continue
        if migrate:
            missing.append((target, source))
            continue
        if target.exists() or target.is_symlink():
            raise SystemExit(f"Refusing to replace a private skill: {target}")
        missing.append((target, source))

    stale = [
        path for path in claude.iterdir()
        if path.name not in skills and link_target(path) == shared / path.name
    ] if claude.is_dir() and not migrate else []
    if not dry_run:
        claude.mkdir(parents=True, exist_ok=True)
    for target in sorted(stale):
        print(f"unlink {target}")
        if not dry_run:
            target.unlink()
    for target, source in missing:
        print(f"link {target} -> {source}")
        if not dry_run:
            target.symlink_to(os.path.relpath(source, target.parent))
    print(f"{len(skills)} shared skills; {len(missing)} links added, {len(stale)} stale links removed"
          + (" (dry run)" if dry_run else ""))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sync_skills(Path.home(), args.dry_run)
