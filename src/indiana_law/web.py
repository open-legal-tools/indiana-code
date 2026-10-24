"""Public HTML for the hosted streamable-HTTP MCP. Unofficial; not legal advice."""

LANDING_TITLE = "Indiana Code MCP"
TERMS_TITLE = "Indiana Code MCP — terms"
PRIVACY_TITLE = "Indiana Code MCP — privacy"

_CSS = """
:root { color-scheme: light; }
html, body { background: #f4efe6; color: #1c1917; }
body {
  font: 17px/1.55 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
  max-width: 40rem; margin: 0 auto; padding: 2.25rem 1.25rem 3rem;
}
.flag { font: 0.78rem/1.3 ui-sans-serif, system-ui, sans-serif;
  letter-spacing: 0.08em; text-transform: uppercase; color: #5c5348; margin: 0 0 1rem; }
h1 { font-size: 1.85rem; font-weight: 600; margin: 0 0 0.75rem; }
h2 { font-size: 1.15rem; margin: 1.75rem 0 0.5rem; }
p, li { margin: 0 0 0.85rem; }
a { color: #6b2d12; }
.warn { border-left: 4px solid #9a3412; padding: 0.35rem 0 0.35rem 0.85rem; }
.note { background: #efe7d8; border: 1px solid #d6cbb6; padding: 0.7rem 0.9rem; }
pre, code { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.86rem; }
pre { background: #fffdf8; border: 1px solid #d6cbb6; padding: 0.75rem 1rem; overflow: auto; }
ul { padding-left: 1.2rem; }
"""


def landing_html(public_host: str = "mcp.openindianalaw.org") -> str:
    mcp_url = f"https://{public_host}/mcp"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{LANDING_TITLE}</title>
  <style>{_CSS}</style>
</head>
<body>
  <p class="flag">Open Indiana Law</p>
  <h1>Indiana Code MCP</h1>
  <p class="warn"><strong>Unofficial. Not legal advice.</strong>
  Dated copies of the Indiana Code from the General Assembly’s annual
  downloads. Verify every citation at
  <a href="https://iga.in.gov/laws/ic/downloads">iga.in.gov</a>.</p>
  <p>This page is a door for software. Search the Code, resolve citations,
  read a section as of a date, browse the outline, look up public-law
  clauses, search companion PDFs, and search Indiana appellate clusters.</p>
  <p class="note">If you open <code>/mcp</code> in a browser you will see
  a JSON error (<code>406 Not Acceptable</code>). That is the machine
  protocol, not a broken site. Connect it from Cursor or Claude using the
  URL below.</p>
  <h2>Connect</h2>
  <p>Streamable HTTP endpoint:</p>
  <pre>{mcp_url}</pre>
  <pre>{{
  "mcpServers": {{
    "indiana-code": {{
      "url": "{mcp_url}"
    }}
  }}
}}</pre>
  <h2>What is loaded</h2>
  <ul>
    <li>Indiana Code snapshots 2017–2026 (HTML).</li>
    <li>Official IGA companions as far as published: session laws 1852–2026,
        non-code 1807–2026, compiled Code PDFs for 2005–2006 and 2009–2016,
        constitutions, and historical tables. 2007–2008 compiled zips were
        never posted.</li>
    <li>Current Indiana court-rules PDFs from rules.incourts.gov.</li>
    <li>Indiana appellate clusters with opinion bodies from Harvard CAP and
        official court PDFs when present; not a complete set.</li>
  </ul>
  <p>Source:
  <a href="https://github.com/open-indiana-law/indiana-code">open-indiana-law/indiana-code</a>.
  Coverage limits: <a href="/terms">terms</a>.
  How we handle requests: <a href="/privacy">privacy</a>.</p>
  <p>This service counts only how many times each tool is used each day. It does not record what you ask.</p>
</body>
</html>
"""


def terms_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{TERMS_TITLE}</title>
  <style>{_CSS}</style>
</head>
<body>
  <p class="flag"><a href="/">← Indiana Code MCP</a></p>
  <h1>Terms and limits</h1>
  <p><strong>This is not an official publication and not legal advice.</strong>
  Nothing here creates an attorney-client relationship. Confirm the current
  text at the Indiana General Assembly before relying on a citation.</p>
  <ul>
    <li>Code snapshots: annual HTML compiles for 2017–2026.</li>
    <li>Act clauses: 2017 and 2019–2026. 2018 acts are missing.</li>
    <li>As-of dates use a July-1 cutoff plus those clauses. Mid-year answers
        can be incomplete.</li>
    <li>Companion PDFs are <code>pdftotext</code> extracts, not the HTML parser.
        Session laws go back to 1852; non-code to 1807. Compiled Code PDFs
        exist for 2005–2006 and 2009–2016. 2007–2008 compiled zips were
        never posted.</li>
    <li>Court rules are the current official compiled PDFs from
        rules.incourts.gov, not a historical rules archive.</li>
    <li>Opinion bodies come from Harvard CAP and official Indiana court PDFs
        when present; not every decision ever issued.</li>
    <li>No Administrative Code, citator, or “good law” signal.</li>
    <li>No query logs are published. See <a href="/privacy">privacy</a>.
        Do not send confidential client facts to a public endpoint if that
        would be inappropriate.</li>
  </ul>
  <p>Official source:
  <a href="https://iga.in.gov/laws/ic/downloads">IGA Indiana Code downloads</a>.
  Package:
  <a href="https://github.com/open-indiana-law/indiana-code">open-indiana-law/indiana-code</a>.</p>
</body>
</html>
"""


def privacy_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{PRIVACY_TITLE}</title>
  <style>{_CSS}</style>
</head>
<body>
  <p class="flag"><a href="/">← Indiana Code MCP</a></p>
  <h1>Privacy</h1>
  <p>Last updated 23 October 2026. Open Indiana Law is a public-good
  project operated by Danielle Teagarden. This page covers the unofficial
  Indiana Code MCP at
  <a href="https://mcp.openindianalaw.org">mcp.openindianalaw.org</a>
  and its aliases.</p>
  <p class="warn"><strong>Unofficial. Not legal advice.</strong>
  Nothing here creates an attorney-client relationship. Do not send
  confidential client facts, work product, or personal information in a
  search or tool call.</p>

  <h2>What this service is</h2>
  <p>A read-only search layer over public Indiana legal text: dated
  unofficial copies of the Indiana Code, official IGA companion PDFs,
  current court rules, and Indiana appellate clusters. No account is
  required. The tools do not write to the store and do not act on a
  user’s other accounts.</p>

  <h2>What we collect on purpose</h2>
  <p>We do <strong>not</strong> keep a published log of search text,
  citation strings, case names, or other tool arguments. Those strings
  can be as sensitive as the legal question you are working on.</p>
  <p>We count how often each tool is used. For each UTC day and each tool
  we keep only:</p>
  <ul>
    <li>how many times the tool was called, and</li>
    <li>how many of those calls failed.</li>
  </ul>
  <p>We do not record who called, from where, with what client, or what was
  asked. The counts are for capacity planning and for showing that free
  legal tools are used. They are not sold, and they are not used to train a model.</p>

  <h2>What hosts see anyway</h2>
  <p>Traffic reaches the origin through a Cloudflare Tunnel. Cloudflare
  and the origin host can see ordinary web metadata: IP address, time,
  User-Agent, requested path, and status code. That is true of any
  public HTTPS service. We do not run extra advertising or social
  pixels.</p>
  <p>If you connect through Claude, Cursor, or another AI client, that
  client also sees your prompts and our replies under <em>its</em>
  privacy policy. We cannot control what those products retain.</p>

  <h2>Source files</h2>
  <p>The public source is
  <a href="https://github.com/open-indiana-law/indiana-code">open-indiana-law/indiana-code</a>.
  GitHub sees whoever visits or files an issue there. The derived
  SQLite store, CourtListener bulk files, and Harvard CAP zips are not
  in Git.</p>

  <h2>Retention</h2>
  <p>Cloudflare and host logs follow those vendors’ defaults. We do not
  keep a query archive. If aggregate counters exist, we keep them only
  as long as they are useful for capacity (measured in months, not
  years) and then discard them.</p>

  <h2>Children</h2>
  <p>This service is not directed at children. It is a research tool
  over public law.</p>

  <h2>Contact</h2>
  <p>Questions or deletion requests:
  <a href="https://github.com/open-indiana-law/indiana-code/issues">GitHub issues</a>.
  Coverage limits: <a href="/terms">terms</a>.</p>
</body>
</html>
"""


def icon_svg() -> str:
    """Draft listing mark: two statute pages. Replace if a brand icon is chosen."""
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img" aria-label="Open Indiana Law">
  <rect width="512" height="512" fill="#f4efe6"/>
  <rect x="118" y="96" width="118" height="320" rx="10" fill="#6b2d12"/>
  <rect x="276" y="96" width="118" height="320" rx="10" fill="#6b2d12"/>
  <rect x="138" y="116" width="78" height="280" rx="4" fill="#f4efe6"/>
  <rect x="296" y="116" width="78" height="280" rx="4" fill="#f4efe6"/>
  <rect x="150" y="148" width="54" height="10" fill="#6b2d12"/>
  <rect x="150" y="178" width="54" height="10" fill="#6b2d12"/>
  <rect x="150" y="208" width="40" height="10" fill="#6b2d12"/>
  <rect x="308" y="148" width="54" height="10" fill="#6b2d12"/>
  <rect x="308" y="178" width="54" height="10" fill="#6b2d12"/>
  <rect x="308" y="208" width="40" height="10" fill="#6b2d12"/>
</svg>
"""
