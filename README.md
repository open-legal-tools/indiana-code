# Indiana Code MCP

**Public home:** [Open Indiana Law](https://github.com/open-indiana-law) ([open-indiana-law/indiana-code](https://github.com/open-indiana-law/indiana-code)).
Unofficial MCP: [mcp.openindianalaw.org](https://mcp.openindianalaw.org) (`/mcp`).
This copy is unofficial and is not legal advice.

Dated, unofficial copies of the Indiana Code (2017–2026) as a local MCP
server. Search, citation resolve, as-of text, version history, outline
browse, and public-law clause lookup.

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
| `ic_list_companion` | Constitution / Non-code / Acts / archive PDFs (when loaded) |
| `ic_search_companion` | Full-text search of those companion PDFs |
| `ic_get_companion` | One page of a companion PDF |

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

## Hosted prototype

A hosted, unofficial instance of this server runs at **https://mcp.indianacle.com**
(Streamable HTTP endpoint `https://mcp.indianacle.com/mcp`, with a landing page at
the root and the terms at `/terms`). It is an early prototype with known gaps; see
[NOT_COVERED.md](NOT_COVERED.md) and the terms page, and verify every citation at
[iga.in.gov](https://iga.in.gov/laws/ic/downloads). It is not legal advice.
Opening `/mcp` in a browser shows a JSON 406 error: that is the machine protocol,
not a broken site. For how it is hosted, see [docs/DEPLOY.md](docs/DEPLOY.md).

## Usage counts (optional, off by default)

A host can count how often each tool is used. Set `INDIANA_LAW_USAGE_DB` to a file path and the server records, per UTC
day and per tool, only the number of calls and errors. It never sees or stores IP addresses, queries, arguments, results
or session ids, so the totals cannot identify anyone, and a failure to write a count never breaks a tool. Read the totals
with `python -m indiana_law.usage /path/to/usage.sqlite`.

## Source

Annual HTML zips from the Indiana General Assembly. This project does not use
the IGA API. Schema: [docs/DESIGN-schema-v1.md](docs/DESIGN-schema-v1.md).
