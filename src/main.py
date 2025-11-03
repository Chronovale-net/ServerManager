#!/usr/bin/env python3
from dotenv import load_dotenv
from http_headers import get_common_headers
from endpoints import get_servers_endpoint
import sys
from typing import Optional
try:
    import requests
except Exception:  # pragma: no cover - safe import guard
    requests = None  # type: ignore

# load env variables
load_dotenv()


def _redact_auth(headers: dict) -> dict:
    """Return a shallow copy of headers with the Authorization value redacted.

    This is useful for safe printing/logging during development.
    """
    out = headers.copy()
    if "Authorization" in out:
        out["Authorization"] = "Bearer <REDACTED>"
    return out


if __name__ == "__main__":
    headers: Optional[dict] = None
    try:
        headers = get_common_headers()
        print("Prepared common headers:", _redact_auth(headers))
    except ValueError as exc:
        # Token not present — warn but continue running the script. Callers can
        # supply the token explicitly to get_common_headers(token=...).
        print("Warning: could not build headers:", exc)

    # Test GET request to the root endpoint to check token validity
    try:
        base_url = get_servers_endpoint()
        if requests is None:
            print("requests not available; skip startup API check. Install dependencies.")
        elif headers is None:
            print("No headers available; skip startup API check.")
        else:
            resp = requests.get(base_url, headers=headers, timeout=10)
            print(f"Startup API check: {resp.status_code} {resp.reason}")
            if resp.status_code != 200:
                print("Warning: API check did not return 200 OK. Check your API token.")
                sys.exit(1)
    except Exception as exc:
        # Any error here should not crash the REPL; just report it.
        print("Startup API check failed:", exc, file=sys.stderr)

    print("Ready!")
    while True:
        lol = input()
        if lol == "exit":
            break
        print(lol)
