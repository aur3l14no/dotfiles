# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Minimal Tencent Docs (docs.qq.com) client over its MCP HTTP endpoints.

The token is read from TENCENT_DOCS_TOKEN only; nothing is written to disk and
no MCP server is registered with any agent.

  tdocs [-s SERVICE] tools [--grep TEXT]   list tools
  tdocs [-s SERVICE] schema TOOL           description and input schema of TOOL
  tdocs [-s SERVICE] call TOOL [JSON | -]  call TOOL with JSON arguments (- reads stdin)

SERVICE defaults to docs, which carries every tool family with a prefix
(manage., sheet., doc., slide_, ...). sheet, doc and slide are the dedicated
services with unprefixed names and a few extra tools.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

SERVICES = {
    "docs": "https://docs.qq.com/openapi/mcp",
    "sheet": "https://docs.qq.com/api/v6/sheet/mcp",
    "doc": "https://docs.qq.com/api/v6/doc/mcp",
    "slide": "https://docs.qq.com/api/v6/slide/mcp",
}
PROTOCOL = "2025-06-18"


def die(msg: str, code: int = 1):
    print(f"tdocs: {msg}", file=sys.stderr)
    sys.exit(code)


class Session:
    def __init__(self, url: str, token: str):
        self.url, self.token, self.sid, self.next_id = url, token, None, 1

    def _post(self, payload: dict) -> dict | None:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": self.token,
            "MCP-Protocol-Version": PROTOCOL,
        }
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(self.url, json.dumps(payload).encode(), headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                self.sid = resp.headers.get("Mcp-Session-Id") or self.sid
                body = resp.read().decode()
                ctype = resp.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            die(f"HTTP {e.code} from {self.url}: {e.read().decode(errors='replace')[:500]}")
        except urllib.error.URLError as e:
            die(f"network error: {e.reason}")
        if "id" not in payload or not body.strip():
            return None
        if "text/event-stream" in ctype:
            for line in body.splitlines():
                if line.startswith("data:"):
                    msg = json.loads(line[5:].strip() or "null")
                    if isinstance(msg, dict) and msg.get("id") == payload["id"]:
                        return msg
            die("no matching response in event stream")
        return json.loads(body)

    def request(self, method: str, params: dict | None = None):
        payload = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        self.next_id += 1
        msg = self._post(payload)
        if msg is None:
            die(f"empty response to {method}")
        if "error" in msg:
            err = msg["error"]
            die(f"{method} failed: {err.get('code')} {err.get('message')}")
        return msg.get("result")

    def open(self):
        self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                    "clientInfo": {"name": "tdocs", "version": "0.1"}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def tools(self) -> list[dict]:
        tools, cursor = [], None
        while True:
            res = self.request("tools/list", {"cursor": cursor} if cursor else {})
            tools += res.get("tools", [])
            cursor = res.get("nextCursor")
            if not cursor:
                return tools


def session(service: str) -> Session:
    token = os.environ.get("TENCENT_DOCS_TOKEN")
    if not token:
        die("TENCENT_DOCS_TOKEN is not set", 2)
    return Session(SERVICES[service], token).open()


def print_result(res: dict) -> int:
    for item in res.get("content", []):
        if item.get("type") == "text":
            text = item["text"]
            try:
                print(json.dumps(json.loads(text), ensure_ascii=False, indent=2))
            except ValueError:
                print(text)
        else:
            print(json.dumps(item, ensure_ascii=False))
    if res.get("structuredContent") and not res.get("content"):
        print(json.dumps(res["structuredContent"], ensure_ascii=False, indent=2))
    return 1 if res.get("isError") else 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="tdocs", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-s", "--service", choices=sorted(SERVICES), default="docs")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tools").add_argument("--grep", default="")
    sub.add_parser("schema").add_argument("tool")
    p = sub.add_parser("call")
    p.add_argument("tool")
    p.add_argument("args", nargs="?", default="{}")
    a = ap.parse_args()

    if a.cmd == "tools":
        for t in session(a.service).tools():
            first = (t.get("description") or "").strip().splitlines()[0:1]
            line = f"{t['name']}  {first[0][:100] if first else ''}"
            if a.grep.lower() in line.lower():
                print(line)
        return 0
    if a.cmd == "schema":
        for t in session(a.service).tools():
            if t["name"] == a.tool:
                print(t.get("description", ""))
                print(json.dumps(t.get("inputSchema", {}), ensure_ascii=False, indent=2))
                return 0
        die(f"unknown tool {a.tool} in service {a.service}")
    raw = sys.stdin.read() if a.args == "-" else a.args
    try:
        args = json.loads(raw)
    except ValueError as e:
        die(f"arguments are not valid JSON: {e}")
    return print_result(session(a.service).request("tools/call", {"name": a.tool, "arguments": args}))


if __name__ == "__main__":
    sys.exit(main())
