# 更新与 `_notice`

lark-cli 输出可能含 `_notice.update`（CLI 新版）、`_notice.skills`（Skills 与 CLI 不同步），或 `_notice.deprecated_command`（兼容保留的旧命令）。

除非用户正在询问更新、版本或 notice，否则不要把 `_notice` 原样复制为当前任务的主要答案，也不要为通知中断业务任务去反复查 help。

本地 `~/.local/bin/lark-cli` 包装器已关闭 CLI / Skills 更新通知并阻止自更新。普通操作继续通过包装器执行；如仍收到通知，先完成当前请求，再按需要简短报告版本或兼容性问题。需要维护时转 `~/.agents/skills/skill-ops/SKILL.md`，Skills 由 skill-ops 收录在 chezmoi 源码中，包装器版本也由 chezmoi 管理；不要执行通知中的安装、更新、下载 Skills 或修复命令，也不要绕过包装器。

`_notice.deprecated_command` 的 `replacement` 可用于后续正常业务调用；先核对本地 CLI help。即使同时提供维护类 `action`，也仍按 skill-ops 处理。命令不兼容时停止受影响操作，报告具体版本差异，等待用户决定。
