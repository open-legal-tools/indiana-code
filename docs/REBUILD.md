# Rebuild the Indiana Code store

The 512 MB SQLite file is derived. JSONL is canonical. Source zips stay
outside Git. Unofficial; not legal advice.

Official downloads: https://iga.in.gov/laws/ic/downloads

## From already-parsed JSONL (this checkout)

```bash
PYTHONPATH=src python -m indiana_law.cli build-store data/store/indiana-code.db \
  --snapshot 2024-06-20:2017::0:data/jsonl/2024-06-20/code.v3.jsonl \
  --snapshot 2024-06-21:2018::0:data/jsonl/2024-06-21/code.v3.jsonl \
  --snapshot 2019-06-27:2019:2019-06-27:1:data/jsonl/2019-06-27/code.v3.jsonl \
  --snapshot 2020-06-23:2020:2020-06-23:1:data/jsonl/2020-06-23/code.v3.jsonl \
  --snapshot 2021-11-09:2021:2021-11-09:1:data/jsonl/2021-11-09/code.v3.jsonl \
  --snapshot 2022-09-09:2022:2022-09-09:1:data/jsonl/2022-09-09/code.v3.jsonl \
  --snapshot 2023-06-19:2023:2023-06-19:1:data/jsonl/2023-06-19/code.v3.jsonl \
  --snapshot 2024-06-17:2024:2024-06-17:1:data/jsonl/2024-06-17/code.v3.jsonl \
  --snapshot 2025-06-30:2025:2025-06-30:1:data/jsonl/2025-06-30/code.v3.jsonl \
  --snapshot 2026-06-23:2026:2026-06-23:1:data/jsonl/2026-06-23/code.v3.jsonl \
  --acts data/jsonl/acts/acts-2017.v3.jsonl \
  --acts data/jsonl/acts/acts-2019.v3.jsonl \
  --acts data/jsonl/acts/acts-2020.v3.jsonl \
  --acts data/jsonl/acts/acts-2021.v3.jsonl \
  --acts data/jsonl/acts/acts-2022.v3.jsonl \
  --acts data/jsonl/acts/acts-2023.v3.jsonl \
  --acts data/jsonl/acts/acts-2024.v3.jsonl \
  --acts data/jsonl/acts/acts-2025.v3.jsonl \
  --acts data/jsonl/acts/acts-2026.v3.jsonl
```

2017 and 2018 were republished by IGA under 2024-dated folders; compile dates
are unknown (`compile_date_certain=0`). There is no 2018 acts file.

## From a fresh official HTML zip

```bash
# unzip the year's HTML-only zip, then:
PYTHONPATH=src python -m indiana_law.cli parse-snapshot \
  path/to/extracted-html \
  data/jsonl/YYYY-MM-DD/code.v3.jsonl \
  --snapshot-id YYYY-MM-DD \
  --zip-sha256 "$(shasum -a 256 path/to/year-Indiana-Code-html.zip | awk '{print $1}')"

# optional: pdftotext the year's Acts PDF, then:
PYTHONPATH=src python -m indiana_law.cli parse-acts \
  path/to/acts.txt \
  data/jsonl/acts/acts-YYYY.v3.jsonl \
  --year YYYY
```

Then run `build-store` as above. Expected counts after a Code rebuild:
10 snapshots, about 114,071 section versions, about 777,842 appearances.

## Historical IGA companions (session laws, non-code, tables)

```bash
python scripts/fetch_iga_historical.py
python scripts/ingest_iga_historical.py data/store/indiana-code.db
```

## Harvard CAP opinion bodies

```bash
python scripts/fetch_harvard_cap.py
python scripts/extract_harvard_cap.py
PYTHONPATH=src python -m indiana_law.cli ingest-caselaw data/store/indiana-code.db \
  --clusters data/courtlistener/indiana/clusters.jsonl \
  --opinions data/courtlistener/indiana/opinions.jsonl \
  --harvard data/harvard-cap/indiana.jsonl
PYTHONPATH=src python -m indiana_law.cli ingest-case-citations data/store/indiana-code.db \
  --clusters data/courtlistener/2026-09-30/indiana/clusters.jsonl \
  --harvard data/harvard-cap/indiana.jsonl
```

## Official Indiana court PDFs (including unpublished / NFP)

```bash
python scripts/fetch_official_decisions.py
python scripts/ingest_official_decisions.py data/store/indiana-code.db
```

Do not Git-track the derived store, CAP zips, or official PDFs.
