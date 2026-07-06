# Quiet startup
set -g fish_greeting

# Path setup
set -l __paths
# User
set -a __paths "$HOME/.local/bin" "$HOME/.local/opt/npm-global/bin"
# Language
set -a __paths "$HOME/.cargo/bin" "$HOME/go/bin"
# Nix
set -a __paths "/etc/profiles/per-user/$USER/bin" /run/wrappers/bin /run/current-system/sw/bin

fish_add_path --move --prepend --global $__paths

# Editor/pager
set -gx EDITOR nvim
set -gx VISUAL nvim
set -gx PAGER less

# Aliases
alias l 'ls -alh --color=auto'
alias c clear
alias rm 'rm -i'
alias t 'tmux new -A -s'
alias rcp 'rsync -avhWP'
alias gg lazygit
alias vi nvim
alias pp 'source .venv/bin/activate.fish'
alias cs 'curl -x socks5h://127.0.0.1:3333'
alias cz chezmoi
alias nxc "nix copy --from 'https://chuck-lab.leo-jazz.ts.net:59700' --no-check-sigs"
alias nix-diff "nvd diff (ls -t1d /nix/var/nix/profiles/system-*-link | head -2 | tac)"
alias pwgen='pwgen -r "\'\"\\\\`\$;&|<>()[]{}"'

function u
    while not $argv
        sleep 5
    end
end

function __parse_envfile -a file
    test -f "$file"; or begin; echo "error: file not found: $file" >&2; return 1; end
    while read --line line
        string match -qr '^\s*(#|$)' -- $line; and continue
        set -l item (string split -m 1 '=' -- $line)
        set -l key $item[1]
        set -l value $item[2]
        if string match -qr '^".*"$' -- $value
            set value (string sub -s 2 -e -2 -- $value)
        else if string match -qr "^'.*'\$" -- $value
            set value (string sub -s 2 -e -2 -- $value)
        end
        echo "$key=$value"
    end <$file
end

function loadenv -a file -d "Export KEY=VALUE pairs from a file"
    for line in (__parse_envfile $file)
        set -l item (string split -m 1 '=' -- $line)
        set -gx $item[1] "$item[2]"
    end
end

function withenv -d "Run a command with temporary env vars from a file"
    set -l file $argv[1]
    set -l cmd $argv[2..-1]
    test (count $cmd) -gt 0; or begin; echo "usage: withenv <file> <command...>" >&2; return 1; end
    env (__parse_envfile $file) $cmd
end
complete -c withenv -n "__fish_is_nth_token 1" -F
complete -c withenv -n "not __fish_is_nth_token 1" -xa "(__fish_complete_subcommand --fcs-skip=2)"

function gitignore
    curl -sL https://www.gitignore.io/api/$argv
end

function dbx -w "distrobox enter"
    eval distrobox enter -n ubuntu $argv
end

function sshp -w ssh
    argparse --ignore-unknown h/help 'p/proxy=?!_validate_int' 'l/local=?' 'r/remote=?' -- $argv
    or return

    if set -ql _flag_help
        echo "sshp [-h|--help] [-p|--proxy=10001] [-l|--local=1234:59900] [-r|--remote=6152,6153] [ARGUMENT ...]"
        return 0
    end

    set -l opts ""

    if set -q _flag_p
        set opts "$opts -o \"ProxyCommand=nc -X 5 -x localhost:$_flag_p %h %p\""
    end

    if set -q _flag_l
        for port in (string split ',' $_flag_l)
            if string match -rq '(?<local>\d+):(?<remote>\d+)' $port
                set opts "$opts -L $local:localhost:$remote"
            else
                set opts "$opts -L $port:localhost:$port"
            end
        end
    end

    if set -q _flag_r
        for port in (string split ',' $_flag_r)
            if string match -rq '(?<local>\d+):(?<remote>\d+)' $port
                set opts "$opts -R $local:localhost:$remote"
            else
                set opts "$opts -R $port:localhost:$port"
            end
        end
    end

    eval ssh $opts $argv
end

function nr -w "nix run"
    set -l argc (count $argv)
    if test $argc = 0
        echo "nr PACKAGE [COMMAND]"
    else if test $argc = 1
        eval nix shell nixpkgs#$argv[1] -c $argv[1]
    else
        eval nix shell nixpkgs#$argv[1] -c $argv[2]
    end
end

function ns -w "nix shell"
    eval nix shell nixpkgs#$argv[1] $argv[2..-1]
end

function sc
    set -l driver ""
    if test (uname) = Linux
        set driver opengl
    else if test (uname) = Darwin
        set driver metal
    end
    adb connect $argv[1]
    nix run nixpkgs#scrcpy -- --render-driver=$driver --no-audio -s $argv[1]
end

function curl-timing -w curl
    curl -w "@$HOME/.config/curl_timing.txt" -so=/dev/null $argv[1..]
end

function set-proxy
    set -l socksPort 1099
    set -l httpPort 1099
    switch (count $argv)
        case 1
            set socksPort $argv[1]
            set httpPort $argv[1]
        case 2
            set socksPort $argv[1]
            set httpPort $argv[2]
    end
    set -gx all_proxy socks5://127.0.0.1:$socksPort
    set -gx http_proxy http://127.0.0.1:$httpPort
    set -gx https_proxy http://127.0.0.1:$httpPort
    echo "Proxy set to all=$socksPort http=$httpPort"
end

function unset-proxy
    set -e all_proxy http_proxy https_proxy
end

function open-ports
    if type -q ss
        sudo ss -tulnpa
    else if type -q lsof
        sudo lsof -PiTCP -sTCP:LISTEN
    else
        echo "Need ss or lsof"
    end
end

function __fish_help -d "--help | pager"
    set -l pager (__fish_anypager)
    or set -l pager less
    fish_commandline_append "--help &| $pager"
end
bind \eh __fish_help

# Keep Option/Alt-Left/Right/Backspace consistent across local macOS and remote Linux fish.
bind alt-left prevd-or-backward-word
bind alt-right nextd-or-forward-word
bind \e\[1\;9D prevd-or-backward-word
bind \e\[1\;9C nextd-or-forward-word
bind alt-backspace backward-kill-word
bind \e\x7f backward-kill-word

# Optional integrations when available
if status is-interactive
    type -q mise; and mise activate fish | source
    type -q fzf; and fzf --fish | source
    type -q zoxide; and zoxide init fish | source
    type -q starship; and starship init fish | source
    type -q direnv; and direnv hook fish | source
    type -q atuin; and atuin init fish --disable-up-arrow | source
end

# Local overrides (not tracked)
if test -f "$HOME/.config/fish/local.fish"
    source "$HOME/.config/fish/local.fish"
end
