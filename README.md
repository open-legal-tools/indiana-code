# Indiana Law MCP

Free, searchable Indiana law — as an MCP server.

Covers the Indiana Code and Indiana appellate court opinions (Supreme Court and Court of Appeals).
All data served locally from SQLite. No API calls at query time.

**8 tools:**
- `search_indiana_code` — full-text search with BM25 ranking
- `get_section` — retrieve IC XX-XX-XX-XX by citation
- `list_titles` — browse the IC title index
- `browse_chapter` — read a chapter in full
- `search_indiana_opinions` — search Supreme Court and Court of Appeals opinions
- `get_opinion` — retrieve full opinion text
- `recent_indiana_opinions` — daily handdown review
- `search_indiana_law` — unified search across code and opinions
- `indiana_law_status` — database health check

Data sources: [Indiana General Assembly API](https://docs.api.iga.in.gov) (code), [CourtListener](https://courtlistener.com) (opinions).
Every section links back to the official IGA source. This is an access layer, not a replacement.

---

## Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Set credentials
cp .env.example ~/.indiana-law-env
# Edit ~/.indiana-law-env — add IGA_API_TOKEN
# Request free token: apitoken.request@iga.in.gov

# 3. Bootstrap Indiana Code (runs ~3-4 hours, resumable)
source ~/.indiana-law-env
python scripts/bootstrap_code.py

# 4. Bootstrap opinions (one-time, ~30 min)
python scripts/bootstrap_opinions.py

# 5. Test the MCP server
python src/mcp_server.py
```

## MCP Client Configuration

Add to your Claude Code MCP config (typically `~/.claude/mcp_config.json`):

```json
{
  "mcpServers": {
    "indiana-law": {
      "command": "/Users/danielle/projects/indiana-law/.venv/bin/python",
      "args": ["/Users/danielle/projects/indiana-law/src/mcp_server.py"],
      "env": {
        "INDIANA_LAW_DB": "/Users/danielle/projects/indiana-law/data/indiana_law.db"
      }
    }
  }
}
```

## Daily Sync

Keep opinions current with new handdowns:

```bash
# Add to crontab (runs at 6am daily alongside other stand-ups)
0 6 * * * /Users/danielle/projects/indiana-law/scripts/daily_sync.sh
```

Free CourtListener tier (no API key): 125 calls/day — sufficient for Indiana-only daily sync.
Paid tier ($10/mo): 600 calls/day.

## Database

SQLite at `data/indiana_law.db`. FTS5 virtual tables for full-text search with porter stemming.
SALI LMSS doc_type taxonomy on opinions (same enum as case-reader).

## Project

Part of the ITJD brand. See `~/projects/itjd/CLAUDE.md`.
