# Pre-2017 archive title PDFs

The IGA downloads page lists older session years as a zip of 36 title PDFs.
Those years are not in the HTML Code store (2017–2026).

This package can index them as companion documents after you download a year
from https://iga.in.gov/laws/ic/downloads and unzip it:

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
