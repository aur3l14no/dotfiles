# Dotfiles

This is a subtree of nix-config repo (`chezmoi/`).

I use it on non-nix systems.

## Use with homebrew

1. Install homebrew
2. `brew install chezmoi`
3. `chezmoi init https://github.com/aur3l14no/dotfiles`
4. brew install ...

## Use with mise

Why mise? Single-user, works everywhere, relatively good repo.

``` sh
# install mise
curl https://mise.run | sh

~/.local/bin/mise use --global chezmoi@latest
~/.local/share/mise/shims/chezmoi init https://github.com/aur3l14no/dotfiles
```

## Chezmoi data

Create `~/.config/chezmoi/chezmoi.toml` to set git identity:

``` toml
[data.git]
name = "Your Name"
email = "you@example.com"
signingKey = "ssh-ed25519 AAAA..."
```

If `data.git` is omitted, `~/.config/git/config` is still generated but without name/email/signing key.

Entries stored as `*.age` are ignored unless your local `chezmoi` config sets
`encryption = "age"`. This keeps `chezmoi init --apply` working on machines
without an age identity while still enabling the encrypted files once age is
configured. New encrypted files should follow the same `*.age` convention.

## SSH

The SSH client configuration is managed on `groves`, `john-macbook`, and
`fusco-thinkbook`. Shared aliases live in `private_dot_ssh/private_config.d/`;
templates retain the few device-specific settings and service identities.

`~/.ssh/config.local` is an optional, unmanaged file for local overrides and
additional aliases. Only `config.d/*.conf` is included automatically, so editor
backups and old extensionless files do not affect connections.

Custom key filenames use kebab-case, for example `keys/fishnet-vps`,
`keys/sjn-lab`, and `keys/hzhs-admin`. Standard OpenSSH
filenames such as `id_ed25519`, `id_rsa`, and `ssh_host_*` retain their standard
spelling. Private keys and `known_hosts` are not stored in this subtree.

All `sjn-*` aliases use only `keys/sjn-lab`. `pty-screen` uses `pty-wrt-ts`
as its jump host on all three workstations; `pty-screen-b` jumps through
`pty-screen`. The default server-alive policy is six unanswered probes at
20-second intervals. Legacy `ssh-rsa` signatures are enabled only for `pty-hsf`.

Apply just the SSH configuration with:

``` sh
chezmoi apply ~/.ssh/config ~/.ssh/config.d
```

## Rime

`Library/Rime` is the macOS Squirrel Rime overlay. Chezmoi pulls upstream
rime-ice with `.chezmoiexternal.toml.tmpl`, then applies personal patches and
the encrypted double-pinyin custom phrase table on top.

Runtime state and vendored upstream data are intentionally not tracked:
`build/`, `sync/`, `*.userdb/`, `installation.yaml`, `user.yaml`, schema
snapshots, dictionaries, Lua helpers, OpenCC tables, and the unused full-pinyin
`custom_phrase.txt`.

### New macOS Setup

Install Squirrel first. The current Homebrew cask is:

``` sh
brew install --cask squirrel-app
```

Then run `chezmoi apply`; on Nix-managed macOS hosts, `darwin-rebuild switch`
already does that. Chezmoi caches the rime-ice archive and refreshes it weekly;
force a refresh with `chezmoi apply --refresh-externals=always`.

After Rime files change, use Squirrel's menu to redeploy Rime.

## Recommended Packages

List lives in `mise-packages.txt` and is ignored by chezmoi (so it does not land in `$HOME`).

``` sh
cat "$(chezmoi source-path)/mise-packages.txt" | xargs ~/.local/bin/mise use --global
```

## Agent Skills

All agent skills live under `dot_agents/skills/` and deploy to the shared
`~/.agents/skills/` directory used by the agent clients. Third-party skills are
vendored there as `exact_<name>/` with their local adaptations;
`dot_agents/skills/.upstream.toml` records each one's upstream and the commit
it is based on. Other hosts need only `chezmoi apply`.

Maintain skills through `~/.agents/skills/skill-ops/SKILL.md`. Its
`skill_upstream.py` merges upstream updates into the vendored copies, and it
delegates documentation adaptation to a sub-agent. Do not install skills with
APM, `npx skills`, or a CLI's own skill installer: they bypass the vendored
copies.

Check vendored skills and preview upstream updates without changing anything:

``` sh
uv run ~/.agents/skills/skill-ops/scripts/skill_upstream.py status
uv run ~/.agents/skills/skill-ops/scripts/skill_upstream.py update --dry-run
```

`lark-cli` is separate from its skills. Its chezmoi-owned wrapper pins the npm
package version and runs it through npm's cache; Node.js and npm must already
be available. First use fetches the package into the cache. Update its pin
through Skill Ops after checking compatibility with the skill text.

Do not run `lark-cli update`: that command also invokes `npx skills` and would
bypass Skill Ops. The wrapper permits `update --check`, blocks the mutating update
command, and suppresses update notifications.

After an update, Skill Ops waits for the patch sub-agent's handoff,
resolves executable prerequisites and user decisions, and completes any
remaining adaptation. No lifecycle hook, dedicated runner, or report file is
required.
