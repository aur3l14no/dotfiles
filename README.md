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
~/.local/share/mise/shim/chezmoi init https://github.com/aur3l14no/dotfiles

# restart shell then install packages
mise use --global <pkg>@latest ...
```

## Recommended Packages

```
atuin
direnv
fd
fzf
lazygit
neovim
ripgrep
starship
yazi
zoxide
```
