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

mise use --global chezmoi@latest
~/.local/share/mise/shims/chezmoi init https://github.com/aur3l14no/dotfiles

# restart shell then install packages
mise use --global <pkg>@latest ...
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

## Recommended Packages

List lives in `mise-packages.txt` and is ignored by chezmoi (so it does not land in `$HOME`).

Install all:

``` sh
cat "$(chezmoi source-path)/mise-packages.txt" | xargs mise use --global
```
