# Shared Agent Rules

- Use `uv` to manage Python dependencies; do not run `pip install` directly.
- Run one-off Python scripts with dependencies using `uv run --with <package> python <script.py>`.
- When delegating to another agent, use the model and effort the user set or named; if that model fails, stop and ask instead of falling back to another, and don't turn on fast or priority tiers unless asked.
- Don't add safety machinery that a loud failure or a functional check already covers (integrity hashes, duplicate validation, extra gates, automatic backups or migrations), in your own work or in briefs to other agents; propose it if it seems needed.
- Skills and agent instructions state goals, constraints and the pitfalls a capable agent would miss, not command recipes.
- On macOS, don't touch `~/Desktop`, `~/Documents` or `~/Downloads` from a shell, not even `ls`: the privacy prompt blocks every later command until someone clicks it at the Mac.
- Files deployed by chezmoi (shared skills, `~/.ssh/config.d/`, wrappers in `~/.local/bin`) are overwritten on apply: change them in `~/.nix-config/chezmoi/`, and put host-only SSH aliases in `~/.ssh/config.local`.
