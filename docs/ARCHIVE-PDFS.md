# Pre-2017 archive title PDFs

The IGA downloads page lists older session years as a zip of title PDFs.
Those years are not in the HTML Code store (2017–2026). Official URL form
(from the site JS): `https://iga.in.gov/ic/{year}/{year}-Indiana-Code.zip`.
Use a browser-shaped User-Agent; a bare curl can get the SPA shell.

```bash
python scripts/fetch_iga_archives.py --extract
```

2006–2008 did not return a zip at that path on 2026-10-22 (SPA shell).
2005 and 2009–2016 did. This package indexes extracted title PDFs as companion
documents:

```bash
PYTHONPATH=src python -m indiana_law.cli ingest-companion data/store/indiana-code.db \
  --year 2016 \
  --kind archive_title \
  --pdf path/to/2016/Title_1.pdf \
  --pdf path/to/2016/Title_2.pdf
```

Or pass every PDF in a directory:

```bash
for f in path/to/2016/*.pdf; do
  PYTHONPATH=src python -m indiana_law.cli ingest-companion data/store/indiana-code.db \
    --year 2016 --kind archive_title --pdf "$f"
done
```

Fidelity is PDF text extraction, not the HTML parser. Expect lower quality
than 2017–2026. Caselaw and SALI are out of scope here.
