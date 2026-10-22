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

## Proposed public host

- Process: this package, streamable HTTP, read-only SQLite
- Machine: a small always-on box (farm node or VPS). A Cloudflare Worker is a
  poor fit for a 512 MB database.
- Name: `mcp.indianacle.com` (Cloudflare DNS on the already-owned zone)
- Do not wait on `openlegaltools.com`

Local HTTP was verified on 2026-10-21: `initialize` and `tools/list` returned
HTTP 200 at `http://127.0.0.1:8765/mcp`. That is not a public deployment.

Until DNS and the host are approved, run stdio locally from the README. Do not
create a Cloudflare record or open a farm port from this file.
