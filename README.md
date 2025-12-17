# Dotfiles

This is a subtree of nix-config repo (`chezmoi/`).

I use it on non-nix systems.

## Use with mise

``` sh
# install mise
curl https://mise.run | sh

mise use --global chezmoi@latest
~/.local/share/mise/shim/chezmoi init https://github.com/aur3l14no/dotfiles

# restart shell
mise use --global atuin@latest direnv@latest fd@latest fzf@latest lazygit@latest neovim@latest ripgrep@latest starship@latest yazi@latest zoxide@latest
```
