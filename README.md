# Indiana Code MCP

Dated, unofficial copies of Indiana legal text as a local MCP server.
Structured Indiana Code for 2017–2026; official IGA companions as far back
as IGA publishes them; current court-rules PDFs; Indiana appellate clusters
with opinion bodies when Harvard CAP or official court PDFs supplied them.

This is an access layer, not an official publication, and not legal advice.
Verify every citation at [iga.in.gov](https://iga.in.gov/laws/ic/downloads).

The older IGA-API / opinions server in `src/mcp_server.py` is historical and
is not wired to any database. Use `python -m indiana_law.mcp_server`.

## Tools

| Tool | What it does |
| --- | --- |
| `ic_search` | Full-text search (optional year / title) |
| `ic_resolve_citation` | Pull IC citations out of free text |
| `ic_get_section` | Section text as of a date |
| `ic_get_versions` | Every loaded version of a section |
| `ic_browse` | Titles → articles → chapters → sections |
| `ic_get_act` | Code targets of a public law (`P.L.98-2026`) |
| `ic_list_companion` | Constitution, Non-code, Acts, archive titles, historical tables, court rules (when loaded) |
| `ic_search_companion` | Full-text search of those companion PDFs |
| `ic_get_companion` | One page of a companion PDF |
| `case_search` | Indiana appellate clusters (Harvard CAP / official court PDFs when present) |
| `case_get` | One cluster, with opinion text only when a body was ingested |

Every answer includes `unofficial`, snapshot, dates, flags, and a disclaimer.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Point at a built store (this checkout already has one):
export INDIANA_LAW_DB="$PWD/data/store/indiana-code.db"
```

Rebuild from the official JSONL already on disk: [docs/REBUILD.md](docs/REBUILD.md).
Coverage limits: [NOT_COVERED.md](NOT_COVERED.md).

```bash
python -m pytest tests
INDIANA_LAW_DB=data/store/indiana-code.db python scripts/smoke_mcp.py
```

## Run the MCP server (stdio)

```bash
export INDIANA_LAW_DB=/absolute/path/to/indiana-code.db
python -m indiana_law.mcp_server
```

### Cursor

Add to `~/.cursor/mcp.json` (or the project MCP config):

```json
{
  "mcpServers": {
    "indiana-code": {
      "command": "python",
      "args": ["-m", "indiana_law.mcp_server"],
      "env": {
        "INDIANA_LAW_DB": "/absolute/path/to/indiana-code.db",
        "PYTHONPATH": "/absolute/path/to/indiana-law/src"
      }
    }
  }
}
```

If you installed the package into a venv, use that venv's `python` and you can
drop `PYTHONPATH`.

### Claude Desktop / Claude Code

```json
{
  "mcpServers": {
    "indiana-code": {
      "command": "python",
      "args": ["-m", "indiana_law.mcp_server"],
      "env": {
        "INDIANA_LAW_DB": "/absolute/path/to/indiana-code.db",
        "PYTHONPATH": "/absolute/path/to/indiana-law/src"
      }
    }
  }
}
```

## Streamable HTTP (local)

```bash
INDIANA_LAW_TRANSPORT=streamable-http INDIANA_LAW_PORT=8765 \
  python -m indiana_law.mcp_server
```

Hosted streamable HTTP (unofficial; not legal advice):
`https://mcp.indianacle.com/mcp`. Landing and terms are on `/` and `/terms`.
See [docs/DEPLOY.md](docs/DEPLOY.md).

## Source

Annual HTML zips from the Indiana General Assembly. This project does not use
the IGA API. Schema: [docs/DESIGN-schema-v1.md](docs/DESIGN-schema-v1.md).
