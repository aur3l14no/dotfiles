# Cua Driver agent skill

This cross-agent skill teaches an AI agent to operate native applications on
macOS, Windows, and Linux with the
[`cua-driver`](https://github.com/trycua/cua/tree/main/libs/cua-driver/rust)
CLI or MCP server.

It covers the canonical snapshot-action-verify loop, exact window addressing,
accessibility and pixel actions, background/foreground delivery, typed browser
automation, optional visual-region parsing, session recording, and
platform-specific limitations. The skill
defaults to background delivery and requires structured refusal or observed
failure before a caller escalates to foreground input.

## Managed dependency and maintenance

Skill text is vendored through skill-ops; installation, updates, removal, source builds,
and repair must use [skill-ops](../skill-ops/SKILL.md). Do not use upstream skill
installers or overwrite the adapted bundle with the driver's skill commands.
The macOS dependency is official CuaDriver.app release 0.37.0 at
`/Applications/CuaDriver.app`, exposed by `~/.local/bin/cua-driver`.
The maintenance source is the official Cua Driver release distribution; the
app and skill revisions must be checked for compatibility during updates.
The pack version does not identify the running daemon; inspect the live tool
schema when versions differ. Launching a raw binary is not a substitute for the
stable app identity that owns macOS TCC grants.

Start the service through LaunchServices and verify the current host:

```bash
open -n -g -a /Applications/CuaDriver.app --args serve
cua-driver status
cua-driver permissions status --json
cua-driver doctor
```

On macOS, Accessibility and Screen Recording belong to `com.trycua.driver`;
`MACOS.md` explains how they are granted, including through an MDM profile or,
when the owner authorizes it, an agent. On Windows, use an interactive user
desktop rather than Session 0. On Linux, the daemon must share the graphical
session and AT-SPI session bus. Missing runtime dependencies must be surfaced
through skill-ops before affected use.

## Reading order

- `SKILL.md`: lean entrypoint, mandatory safety rules, and task-based routing.
- `WORKFLOW.md`: exact targets, bounded snapshots, coordinates, action semantics,
  verification, filesystem and clipboard proof.
- `RUNTIME.md`: preflight, transport/session ownership, authorization, cursor,
  and cleanup.
- `MACOS.md`, `WINDOWS.md`, or `LINUX.md`: host-specific launch, capture,
  accessibility, input delivery, permissions, and refusal boundaries.
- `BROWSER.md`: exact browser-window binding, explicit profile preparation,
  page refs, trust-classified click/type/navigation, and native fallbacks.
- `VISUAL.md`: optional model-neutral parsing of one retained screenshot into
  capture-bound text and icon regions.
- `RECORDING.md`: trajectory evidence, MP4 capture, and replay.
- `EMBEDDING.md`: embedding the driver into another host application.

The agent loads `SKILL.md`, then only the linked guide needed for its next
step. Every reference ships in the pack; no separate skill installation or
repository checkout is required. The installer keeps the flat Markdown layout.

## Browser model

Browser work starts from the same native `(pid, window_id)` selection as every
other app. `get_browser_state` binds that exact window to a session-scoped
target and tab, then returns short-lived page refs for `browser_click`,
`browser_type`, and `browser_navigate`.

Setup is never a hidden read side effect. `browser_prepare` requires explicit
approval before launching a driver-managed profile or attaching to an existing
authenticated profile. Trusted pointer input and synthetic DOM clicks are
reported as different routes; the driver refuses instead of silently changing
trust class or foregrounding a standalone browser.

See `BROWSER.md` for the supported surface and exact recovery rules.

## Recording

Session recording captures before/after state, screenshots, action metadata,
and optional MP4 video. macOS uses ScreenCaptureKit. Windows uses ffmpeg with
`gdigrab`. Linux uses compositor-specific capture or ffmpeg with `x11grab`.
Availability is reported honestly when a host dependency or portal grant is
missing. See `RECORDING.md`.

## License

Repository source files are MIT licensed. Copies published through ClawHub are
distributed under MIT-0, as required for ClawHub skills.
