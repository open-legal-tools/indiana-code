"""POST initialize + tools/list to a local streamable-HTTP server.
usage: INDIANA_LAW_DB=... python scripts/smoke_http.py http://127.0.0.1:8765/mcp
"""
import json
import sys
import urllib.request

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/mcp"


def post(payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        body = resp.read().decode()
        return resp.status, body


status, body = post({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "smoke-http", "version": "0"},
    },
})
print("initialize", status, body[:400])
status, body = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
print("tools/list", status, body[:800])
