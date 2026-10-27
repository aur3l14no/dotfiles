# Skill

For writing or changing a skill or a rules file, including lessons from past sessions.

1. Write only what a strong model would not do unprompted: the user's preferences, and pitfalls you can see in a session with a cause you can name. One-off accidents (a network error, a reboot, a rate limit) don't count. A pitfall earns a line once it has happened twice.
2. Prefer structure to text: a type, a lint, a test or a script beats a sentence. When the user corrects the same thing twice, run the **correct** skill.
3. When mining sessions, read the user's own messages first; they carry the corrections. Count occurrences before writing a rule.
4. First drafts have always come out too long. Cut before showing.
5. Placement: what belongs to one project (its machines, its product's tools) goes in that project's `.agents/skills/`. General engineering goes in this plugin.
6. Layout: each skill at `skills/<name>/SKILL.md`, because Claude Code finds nothing deeper; supporting files may nest. Explicit-only in both harnesses: `disable-model-invocation: true` in the frontmatter, and `agents/openai.yaml` with `allow_implicit_invocation: false` under `policy`. The manifest is `plugin.json` on the agent-plugins schema; `.claude-plugin/plugin.json` is an identical copy for Claude Code. Files adapted from another plugin are listed in `upstream.json` with the upstream commit and what was changed.
7. Budget: the plugin's markdown stays under 60,000 characters (`find <plugin> -name '*.md' -exec cat {} + | wc -m`). When over, cut before adding.
