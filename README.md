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

Remote agent skills are resolved and locked by APM. The global manifest and
lock are managed by chezmoi under `~/.apm/`; APM deploys skills to the shared
`~/.agents/skills/` directory used by the agent clients.

Only locally maintained skills belong under `chezmoi/dot_agents/skills/`.
Do not add APM-deployed skills back to chezmoi: `~/.apm/apm_modules/` is APM's
runtime store, and `apm install` recreates both that store and the deployed
skill directories from the checked-in manifest and lock.

Initialize through `~/.agents/skills/skill-ops/SKILL.md`. Establish uv/Python
and APM before restoring locked skills. Skill Ops delegates documentation
adaptation to a sub-agent using `skill-patcher` after installation or updates;
direct APM commands do not automatically patch skills.

``` sh
chezmoi apply
apm install --global --frozen
```

Check for upstream changes without installing them:

``` sh
apm outdated --global
```

Preview and apply compatible stable skill updates, then save the regenerated
lock back to chezmoi:

``` sh
apm update --global --dry-run --target agent-skills larksuite/cli
apm update --global --yes --target agent-skills larksuite/cli
chezmoi re-add "$HOME/.apm/apm.lock.yaml"
```

`lark-cli` is separate from its skills. Its chezmoi-owned wrapper pins the npm
package version and runs it through npm's cache; Node.js and npm must already
be available. First use fetches the package into the cache. Update its pin
through Skill Ops after checking compatibility with the skill text.

Do not run `lark-cli update`: that command also invokes `npx skills` and would
bypass APM. The wrapper permits `update --check`, blocks the mutating update
command, and suppresses update notifications.

After install/update, Skill Ops waits for the patch sub-agent's handoff,
resolves executable prerequisites and user decisions, and completes any
remaining adaptation. No lifecycle hook, dedicated runner, or report file is
required.
