# Shell environment

The base environment appends existing directories missing from PATH, preserving
inherited entries and their priority. Same-named tools already on PATH keep
precedence. Interactive integrations such as `mise activate` may change it later.

## Local overrides

Use `~/.config/shell/local.sh` for bash/zsh or `~/.config/fish/local.fish` for fish.
These optional files are unmanaged and run after the shared defaults. They also
load in non-interactive shells: keep environment setup silent, lightweight, and
safe to repeat. In `local.sh`, use syntax compatible with both bash and zsh.

Put prompts and interactive integrations in `.bashrc` / `.zshrc`, behind an
interactive check; in `local.fish`, guard them with `if status is-interactive`.
Local overrides may explicitly change PATH priority. Keep managed defaults out of
persistent `fish_user_paths`.

For a temporary tool directory in the current session:

```sh
# bash / zsh
export PATH="$HOME/test-bin:$PATH"
```

```fish
fish_add_path --path --prepend --move "$HOME/test-bin"
```

## Shared defaults

Edit [shell-paths.yaml](../.chezmoitemplates/shell-paths.yaml) to add a shared
fallback directory. Chezmoi renders this list into native shell code at apply
time; there is no YAML parser at shell startup.

| Shell | Startup path |
| --- | --- |
| bash | `.bashrc` sources `~/.config/shell/env.sh`; `.bash_profile` loads `.bashrc`. |
| zsh | `.zshenv` sources `~/.config/shell/env.sh`. |
| fish | `conf.d/zz-path.fish` runs after Home Manager's `hm-session-vars.fish`. |

Plain `bash -c` inherits PATH without loading this setup. Services declare their
own PATH. Home Manager session variables are imported before fallback paths are
added when its session-variable file is present.
