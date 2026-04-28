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
