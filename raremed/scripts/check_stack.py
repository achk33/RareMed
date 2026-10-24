"""Print health and status for a running RareMed API."""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("RAREMED_API_URL", "http://localhost:8000").rstrip("/")


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=10) as response:
        return json.load(response)


def main() -> int:
    try:
        health = get("/health")
        status = get("/api/v1/status")
    except urllib.error.URLError as exc:
        print(f"API not reachable at {BASE_URL}: {exc.reason}", file=sys.stderr)
        return 1

    print(json.dumps({"health": health, "status": status}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
