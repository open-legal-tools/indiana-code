"""Public HTML for the hosted streamable-HTTP MCP. Unofficial; not legal advice."""

LANDING_TITLE = "Indiana Code MCP"
TERMS_TITLE = "Indiana Code MCP — terms"

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
  Coverage limits: <a href="/terms">terms</a>.</p>
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
    <li>No query logs are published. Do not send confidential client facts
        to a public endpoint if that would be inappropriate.</li>
  </ul>
  <p>Official source:
  <a href="https://iga.in.gov/laws/ic/downloads">IGA Indiana Code downloads</a>.
  Package:
  <a href="https://github.com/open-indiana-law/indiana-code">open-indiana-law/indiana-code</a>.</p>
</body>
</html>
"""
