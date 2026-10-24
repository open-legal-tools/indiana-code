# Directory listing packet

**Status: drafted, not submitted.** Danielle must approve any
directory submit; it is a message to a third party. This file is the
checklist. Do not treat a filled form as permission to send it.

Unofficial; not legal advice.

## Hosting (do not clone onto worker-02–04)

The live origin stays on **worker-01** only
(`127.0.0.1:8765` + tunnel `indiana-code-mcp`).

| Node | Use for this MCP | Why |
| --- | --- | --- |
| worker-01 | Live origin | Already has the store, systemd unit, and tunnel |
| worker-02 | No | Dify / Gitea / Ollama already loaded |
| worker-03 | Optional later: **cold** store copy | Lightest box; not a second public URL |
| worker-04 | No | Household AdGuard DNS, Jellyfin, LibreChat |

Four live SQLite copies would drift and waste ~7 GB each. Cloudflare
already fronts the one origin. A standby replica is a later backup
decision, not a listing requirement.

## URLs (after the next worker-01 deploy)

| Role | URL |
| --- | --- |
| Landing / docs | https://mcp.openindianalaw.org |
| MCP | https://mcp.openindianalaw.org/mcp |
| Terms | https://mcp.openindianalaw.org/terms |
| Privacy | https://mcp.openindianalaw.org/privacy |
| Icon | https://mcp.openindianalaw.org/icon.svg |
| Source | https://github.com/open-indiana-law/indiana-code |
| Support | https://github.com/open-indiana-law/indiana-code/issues |

Aliases (`mcp.openindianalaw.com`, `mcp.indianacle.com`) should keep
working. List only the `.org` URL in directories.

`/privacy` and `/icon.svg` are in this branch. They are **not live**
until worker-01 is redeployed.

## Claude Connectors Directory

Portal: https://claude.ai/directory/manage — choose **MCP connector**.
Needs a paid Claude plan. Guide:
https://claude.com/docs/connectors/building/submission

Paste these fields. Danielle enters her own email in the portal.

- **Connection URL:** `https://mcp.openindianalaw.org/mcp`
- **Authentication:** none (public legal text; tools are read-only)
- **Name (≤100):** Indiana Code
- **One-liner (≤200):** Unofficial Indiana Code, IGA companions, and appellate clusters for research. Not legal advice.
- **Description (≤2,000):** Dated unofficial copies of the Indiana Code (2017–2026), official IGA companion PDFs as far as published, current court rules, and Indiana appellate clusters. Search sections, resolve citations, read a section as of a date, browse the outline, look up public-law clauses, and find text mentions of statutes or cases. This is an access layer, not an official publication, not a citator, and not legal advice. Verify every citation at iga.in.gov.
- **Categories:** Legal research; Government
- **Documentation URL:** https://mcp.openindianalaw.org
- **Privacy policy URL:** https://mcp.openindianalaw.org/privacy
- **Support:** https://github.com/open-indiana-law/indiana-code/issues
- **Icon:** `docs/listing/icon.svg` (draft two-page mark; replace if a brand icon is chosen)
- **Slug:** `indiana-code` (permanent once published — confirm before submit)
- **Use cases:** Look up an Indiana statute as of a date; resolve an IC citation in text; find opinions that mention a section or a reporter cite
- **Reads / writes:** reads public law only
- **Company:** Open Indiana Law
- **Website:** https://openindianalaw.org
- **Data handling:** first-party index of public legal text; no personal-health data; no sponsored content
- **Test account:** none. Reviewer connects to the public URL and calls `ic_search` with `habeas`, then `ic_get_section` with `35-42-1-1`.

Tools already have `title` plus `readOnlyHint` / `destructiveHint`.
Confirm that in Claude as a custom connector before submit.

## Official MCP Registry

Draft metadata: [server.json](../server.json).
Guide: https://modelcontextprotocol.io/registry/quickstart
Remote servers: https://modelcontextprotocol.io/registry/remote-servers

- **Name:** `org.openindianalaw/indiana-code` (prove `openindianalaw.org` by DNS or HTTP challenge at publish time)
- **Fallback name** if DNS auth is deferred: `io.github.open-indiana-law/indiana-code` (GitHub org login)
- **Remote:** `https://mcp.openindianalaw.org/mcp` (`streamable-http`)
- **Version:** `0.1.0` (must change on every later publish; metadata is immutable)

Do not run `mcp-publisher publish` until Danielle approves that third-party submit.

## Cursor

1. Community list: https://cursor.directory/mcp/new
   - Name: Indiana Code
   - Description: Unofficial Indiana Code, companions, and appellate cases for AI tools. Not legal advice.
   - Install-docs URL: https://mcp.openindianalaw.org
   - Deep link (optional): generate from Cursor after adding the remote URL
2. Official Marketplace is a reviewed plugin at
   https://cursor.com/marketplace/publish — later, not required for discovery.

## Still open before any submit

1. Redeploy worker-01 so `/privacy` and `/icon.svg` answer 200.
2. Danielle picks or accepts the draft icon.
3. Optional but wise: rate limits and privacy-safe tool counters (no query text).
4. Danielle’s explicit OK to submit to each directory.

## Not in this packet

- No REST API.
- No Cloudflare R2 snapshot.
- No worker-02 / 03 / 04 origin.
- No message to Claude, Cursor, the MCP Registry, ChatGPT, IGA, or anyone else.
