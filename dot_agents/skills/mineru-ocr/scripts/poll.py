#!/usr/bin/env python3
"""Poll a MinerU v4 task or batch, saving its latest response."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["task", "batch"])
    parser.add_argument("id")
    parser.add_argument("--timeout", type=float, default=900, help="deadline in seconds")
    parser.add_argument("--output", default="status.json")
    args = parser.parse_args()
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mineru/curl.conf"
    endpoint = "extract/task" if args.kind == "task" else "extract-results/batch"
    deadline = time.monotonic() + args.timeout
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Polling deadline reached; resume with the same task/batch id.")
        response = subprocess.run(
            ["curl", "--disable", "--config", str(config), "--fail-with-body", "--silent",
             "--show-error", "--max-time", str(min(30, remaining)),
             f"https://mineru.net/api/v4/{endpoint}/{args.id}"],
            capture_output=True, text=True,
        )
        Path(args.output).write_text(response.stdout)
        response.check_returncode()
        result = json.loads(response.stdout)
        if result.get("code") != 0:
            raise ValueError(f"MinerU API error: {result.get('msgCode', result.get('code'))}; see {args.output}")
        data = result["data"]
        items = [data] if args.kind == "task" else data["extract_result"]
        if not items or any(not item.get("state") for item in items):
            raise ValueError(f"Missing result state; see {args.output}")
        states = [item["state"] for item in items]
        print(", ".join(f"{state}: {states.count(state)}" for state in sorted(set(states))), flush=True)
        if all(state in {"done", "failed"} for state in states):
            if "failed" in states:
                raise ValueError(f"Extraction failed for {states.count('failed')} item(s); see {args.output}")
            return
        time.sleep(max(0, min(10, deadline - time.monotonic())))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
