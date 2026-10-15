---
name: tencent-docs
description: Read, search, and edit the user's personal Tencent Docs at docs.qq.com — sheets, docs, smart canvases, slides, smart sheets — through the `tdocs` CLI. Use when the user gives a docs.qq.com link or asks about their Tencent Docs. Not for WeCom documents (doc.weixin.qq.com).
---

# Tencent Docs

`tdocs` calls Tencent Docs' MCP HTTP endpoints directly; no MCP server is registered with any agent. It reads the token from `TENCENT_DOCS_TOKEN`, a credential with full access to the user's account: provide it only in the command's environment and never print it.

If the token is unavailable, or a call fails with 400006 or HTTP 401 (invalid or expired token), stop and ask the user for a fresh token from https://docs.qq.com/scenario/open-claw.html. 400007 means the operation needs Tencent Docs VIP.

## Commands

- `tdocs tools [--grep TEXT]` — list tools; family prefixes include `manage.`, `sheet.`, `doc.`, `smartcanvas.`, `smartsheet.`, `slide_`.
- `tdocs schema TOOL` — read a tool's description and argument schema before the first call.
- `tdocs call TOOL '<json>'` (or `-` for stdin) — prints the result; exit 1 on a tool error.

`-s sheet|doc|slide` before the command targets a dedicated service instead; its tool names drop the family prefix and it has a few extra tools.

## Reading

The path segment after the type in a link works as `file_id` (`https://docs.qq.com/sheet/DRU5VYW96Z1RXTHRy` → `DRU5VYW96Z1RXTHRy`). Without a link, use `manage.search_file`.

1. `manage.query_file_info` gives title, type and owner.
2. `get_content` reads any type as text. For sheets, `sheet.get_sheet_info` lists sub-sheets, then `sheet.get_cell_data` with `return_csv: true` reads a range.

## Writing

Use the tool family matching the document type; a mismatch returns 400016.
