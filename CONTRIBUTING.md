# Maintenance

Edit the source in the nix-config checkout. `just push` there pushes nix-config
and refreshes the public dotfiles mirror, excluding the private SSH configuration.

## Rime

Track personal patches in [Library/Rime](Library/Rime), keeping generated runtime
state and vendored upstream data out of the source. New encrypted files use the
`*.age` convention so the shared ignore rule can skip them before age is configured.

The upstream archive and cache policy live in
[.chezmoiexternal.toml.tmpl](.chezmoiexternal.toml.tmpl). Force a refresh with:

```sh
chezmoi apply --refresh-externals=always
```

## SSH (nix-config only)

Host selection lives in `.chezmoiignore`; aliases live in `private_dot_ssh/`.
Local overrides belong in `~/.ssh/config.local`. Only `config.d/*.conf` is included.
Custom key filenames use kebab-case; standard OpenSSH filenames keep their spelling.
Private keys and `known_hosts` stay outside this source.

```sh
chezmoi apply ~/.ssh/config ~/.ssh/config.d
```
