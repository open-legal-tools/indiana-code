# Hosted MCP (streamable HTTP)

Authorized 2026-10-22: stand up `https://mcp.openindianalaw.org` on farm
`worker-01`, loopback only, dedicated Cloudflare tunnel. Do not open a new
public farm port. Do not reuse another tunnel's token.

Unofficial; not legal advice.

## Local check (no DNS)

```bash
export INDIANA_LAW_DB=/absolute/path/to/indiana-code.db
export INDIANA_LAW_TRANSPORT=streamable-http
export INDIANA_LAW_HOST=127.0.0.1
export INDIANA_LAW_PORT=8765
PYTHONPATH=src python -m indiana_law.mcp_server --http
```

- Landing: `http://127.0.0.1:8765/`
- Terms: `http://127.0.0.1:8765/terms`
- Privacy: `http://127.0.0.1:8765/privacy`
- Icon: `http://127.0.0.1:8765/icon.svg`
- MCP: `http://127.0.0.1:8765/mcp`

```json
{
  "mcpServers": {
    "indiana-code": {
      "url": "https://mcp.openindianalaw.org/mcp"
    }
  }
}
```

Keep the live origin on worker-01 only. Do not stand up a second public
copy on worker-02, worker-03, or worker-04. See [LISTING.md](LISTING.md).

## worker-01 layout

- Code + venv + store: `/home/transcribe/indiana-code`
- Tunnel config (no other farm tunnels): `~/.config/indiana-code/cloudflared.yml`
- Units: `deploy/indiana-code-mcp.service`, `deploy/cloudflared-indiana-code.service`
- Process binds `127.0.0.1:8765`. cloudflared rewrites `Host` to `127.0.0.1`.

## Checks

```bash
curl -sS http://127.0.0.1:8765/health
curl -sS -o /dev/null -w '%{http_code}\n' https://mcp.openindianalaw.org/
INDIANA_LAW_DB=/path/to/indiana-code.db python scripts/smoke_http.py https://mcp.openindianalaw.org/mcp
```
