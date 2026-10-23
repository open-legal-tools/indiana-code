# Hosted MCP (streamable HTTP)

The same package can speak Streamable HTTP. Standing up a public URL, changing
DNS, or opening a port on the farm still needs Danielle's approval. This file
is the runbook, not authorization.

## Local check (no DNS)

```bash
export INDIANA_LAW_DB=/absolute/path/to/indiana-code.db
export INDIANA_LAW_TRANSPORT=streamable-http
export INDIANA_LAW_HOST=127.0.0.1
export INDIANA_LAW_PORT=8765
PYTHONPATH=src python -m indiana_law.mcp_server
```

The MCP endpoint is `http://127.0.0.1:8765/mcp`.

Cursor / Claude (remote URL, once a host exists):

```json
{
  "mcpServers": {
    "indiana-code": {
      "url": "https://mcp.indianacle.com/mcp"
    }
  }
}
```

## Public host (live as an unofficial prototype)

- Process: this package, streamable HTTP, read-only SQLite
- Machine: a small always-on box behind a Cloudflare tunnel; its port is not
  exposed directly to the internet. A Cloudflare Worker is a poor fit for a
  512 MB database.
- Name: `mcp.indianacle.com` (Cloudflare DNS on the already-owned zone)
- Landing page at `/`, terms at `/terms`, MCP endpoint at `/mcp`

A real MCP `initialize` handshake against `https://mcp.indianacle.com/mcp` was
verified on 2026-10-23 (server `indiana-code`, version 1.30.0). The same
endpoint also works from a local run: see the Streamable HTTP section of the
README. This is an unofficial prototype; coverage limits are in
[../NOT_COVERED.md](../NOT_COVERED.md) and on the terms page.
