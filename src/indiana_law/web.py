"""Public HTML for the hosted streamable-HTTP MCP. Unofficial; not legal advice."""

LANDING_TITLE = "Indiana Code MCP"
TERMS_TITLE = "Indiana Code MCP — terms"


def landing_html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{LANDING_TITLE}</title>
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; max-width: 42rem;
            margin: 2rem auto; padding: 0 1.25rem; }}
    h1 {{ font-size: 1.6rem; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    pre {{ overflow: auto; padding: 0.75rem 1rem; border: 1px solid #8884; }}
    .flag {{ font-size: 0.85rem; letter-spacing: 0.04em; text-transform: uppercase;
             color: #666; }}
    .warn {{ border-left: 4px solid #b45309; padding: 0.4rem 0.8rem; }}
  </style>
</head>
<body>
  <p class="flag">Indianacle · Open Legal Tools</p>
  <h1>Indiana Code MCP</h1>
  <p class="warn"><strong>Unofficial. Not legal advice.</strong>
  Dated copies of the Indiana Code from the General Assembly’s annual
  downloads. Verify every citation at
  <a href="https://iga.in.gov/laws/ic/downloads">iga.in.gov</a>.</p>
  <p>Search, resolve citations, read a section as of a date, browse the
  outline, and look up public-law clauses. Companion PDFs (Constitution,
  Non-code, Acts, and older archive titles when loaded) are searchable
  separately.</p>
  <h2>Connect</h2>
  <p>Streamable HTTP endpoint:</p>
  <pre>https://mcp.indianacle.com/mcp</pre>
  <pre>{{
  "mcpServers": {{
    "indiana-code": {{
      "url": "https://mcp.indianacle.com/mcp"
    }}
  }}
}}</pre>
  <p>Source:
  <a href="https://github.com/open-legal-tools/indiana-code">open-legal-tools/indiana-code</a>.
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
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font: 16px/1.5 ui-sans-serif, system-ui, sans-serif; max-width: 42rem;
            margin: 2rem auto; padding: 0 1.25rem; }}
  </style>
</head>
<body>
  <p><a href="/">← Indiana Code MCP</a></p>
  <h1>Terms and limits</h1>
  <p><strong>This is not an official publication and not legal advice.</strong>
  Nothing here creates an attorney-client relationship. Confirm the current
  text at the Indiana General Assembly before relying on a citation.</p>
  <ul>
    <li>Code snapshots: annual HTML compiles for 2017–2026.</li>
    <li>Act clauses: 2017 and 2019–2026. 2018 acts are missing.</li>
    <li>As-of dates use a July-1 cutoff plus those clauses. Mid-year answers
        can be incomplete.</li>
    <li>Companion PDFs are <code>pdftotext</code> extracts, not the HTML parser.</li>
    <li>No Administrative Code, court rules, citator, or “good law” signal.</li>
    <li>No query logs are published. Do not send confidential client facts
        to a public endpoint if that would be inappropriate.</li>
  </ul>
  <p>Official source:
  <a href="https://iga.in.gov/laws/ic/downloads">IGA Indiana Code downloads</a>.
  Package:
  <a href="https://github.com/open-legal-tools/indiana-code">open-legal-tools/indiana-code</a>.</p>
</body>
</html>
"""
