# Dotfiles

My shell, Git, editor, and agent configuration for macOS and Linux, managed with
[chezmoi](https://www.chezmoi.io/). Usable without Nix.

## Use

With chezmoi and uv installed, initialize the source, review the changes, and apply:

```sh
chezmoi init https://github.com/aur3l14no/dotfiles
chezmoi diff
chezmoi apply
```

Run `chezmoi diff` and `chezmoi apply` again after changing the source. On my
Nix-managed hosts, Home Manager applies it during activation.

## Install

With Homebrew:

```sh
brew install chezmoi uv
```

Or use [mise](https://mise.jdx.dev/installing-mise.html) on macOS or Linux.
Run these commands in bash or zsh, then follow the usage above:

```sh
curl https://mise.run | sh
~/.local/bin/mise use --global chezmoi@latest uv@latest
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"
```

`uv` is required to deploy the shared agent skills. Applications configured by
these dotfiles are installed separately.

## Customize

Set Git identity in `~/.config/chezmoi/chezmoi.toml` before applying:

```toml
[data.git]
name = "Your Name"
email = "you@example.com"
signingKey = "ssh-ed25519 AAAA..."
```

All three fields are optional; setting `signingKey` enables SSH commit signing.
Local Git overrides belong in `~/.config/git/config.local`.

Encrypted files are skipped unless chezmoi uses `encryption = "age"`. Configure
a usable age identity before enabling it.

For shell PATH behavior, temporary tool overrides, and machine-local settings,
see [Shell environment](docs/shell.md).

## Optional tools

Install the command-line tools in [mise-packages.txt](mise-packages.txt):

```sh
xargs mise use --global < "$(chezmoi source-path)/mise-packages.txt"
```

On macOS, the Rime configuration uses [Squirrel](https://formulae.brew.sh/cask/squirrel-app):

```sh
brew install --cask squirrel-app
chezmoi apply
```

After applying, redeploy Rime from Squirrel's menu.

## Maintenance

The source lives in `chezmoi/` in nix-config and is mirrored to the dotfiles repo.
See [maintenance notes](CONTRIBUTING.md) for shared changes and
[Skill Ops](dot_agents/skills/skill-ops/SKILL.md) for agent skills and their tools.
