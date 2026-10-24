#!/bin/bash
# Ingest extracted IGA archive title PDFs (2009-2016). Unofficial; not legal advice.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DB="${1:-$ROOT/data/store/indiana-code.db}"
cd "$ROOT"
for year in 2009 2010 2011 2012 2013 2014 2015 2016; do
  dir="$ROOT/data/iga-archives/$year"
  if [ ! -d "$dir" ]; then
    echo "skip missing $dir"
    continue
  fi
  echo "INGEST $year $(ls "$dir"/*.pdf | wc -l) pdfs" 
  PYTHONPATH=src python3 -m indiana_law.cli ingest-companion "$DB" \
    --year "$year" --kind archive_title --pdf-dir "$dir"
done
echo "done archive titles"
