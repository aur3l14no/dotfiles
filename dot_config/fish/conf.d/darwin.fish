alias nproc 'sysctl -n hw.logicalcpu'
alias kill_coreservicesuiagent 'pkill -9 CoreServicesUIAgent'
alias flush_dns 'sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder'
alias xattr-q 'xattr -d com.apple.quarantine'
alias xattr-c 'xattr -cr'

fish_add_path --move --prepend /opt/homebrew/bin
fish_add_path --move --prepend /opt/homebrew/sbin

alias tailscale '/Applications/Tailscale.app/Contents/MacOS/Tailscale'
alias ssh-bwagent "ssh -o ForwardAgent=$HOME/Library/Containers/com.bitwarden.desktop/Data/.bitwarden-ssh-agent.sock"
