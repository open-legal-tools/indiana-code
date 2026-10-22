"""Ingest IGA companion PDFs (Constitution, Non-code, full Acts, optional archive titles).

Unofficial; not legal advice. Requires the system `pdftotext` binary (poppler).
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path


KIND_CONSTITUTION = "constitution"
KIND_NONCODE = "noncode"
KIND_ACTS = "acts"
KIND_ARCHIVE = "archive_title"


def pdf_pages(path: str) -> list[str]:
    """Return one string per PDF page using pdftotext -layout."""
    with tempfile.TemporaryDirectory() as td:
        out = os.path.join(td, "out.txt")
        subprocess.run(["pdftotext", "-layout", path, out], check=True)
        text = Path(out).read_text(encoding="utf-8", errors="replace")
    pages = text.split("\f")
    return [p.strip() for p in pages if p.strip()]


def classify(filename: str) -> str | None:
    name = filename.lower()
    if "constitution" in name:
        return KIND_CONSTITUTION
    if "noncode" in name or "non-code" in name:
        return KIND_NONCODE
    if re.search(r"acts\.pdf$", name):
        return KIND_ACTS
    if re.search(r"(title[_-]?|^\d+\.pdf$)", name):
        return KIND_ARCHIVE
    return None


def year_from_path(path: str, default: int | None = None) -> int | None:
    m = re.search(r"(20\d{2})", os.path.basename(path))
    if m:
        return int(m.group(1))
    return default


def doc_id(kind: str, year: int | None, filename: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", Path(filename).stem.lower()).strip("-")
    if kind == KIND_ARCHIVE:
        return f"archive-{year or 'unknown'}-{stem}"
    if year:
        return f"{kind}-{year}"
    return stem


def extract_additional_from_zip(zip_path: str, dest_dir: str) -> list[str]:
    """Extract Additional_Documents_PDF members from an official HTML zip."""
    os.makedirs(dest_dir, exist_ok=True)
    written: list[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            if "Additional_Documents_PDF" not in info.filename:
                continue
            if not info.filename.lower().endswith(".pdf"):
                continue
            target = os.path.join(dest_dir, os.path.basename(info.filename))
            with zf.open(info) as src, open(target, "wb") as fh:
                fh.write(src.read())
            written.append(target)
    return written


def pages_from_pdf(path: str, kind: str | None = None, year: int | None = None) -> list[dict]:
    kind = kind or classify(os.path.basename(path))
    if not kind:
        raise ValueError(f"cannot classify {path}")
    year = year or year_from_path(path)
    did = doc_id(kind, year, os.path.basename(path))
    title = {
        KIND_CONSTITUTION: f"Indiana Constitution ({year})",
        KIND_NONCODE: f"Indiana non-code statutes ({year})",
        KIND_ACTS: f"Indiana Acts ({year})",
        KIND_ARCHIVE: f"Indiana Code archive {os.path.basename(path)} ({year})",
    }.get(kind, os.path.basename(path))
    out = []
    for i, text in enumerate(pdf_pages(path), start=1):
        out.append({
            "doc_id": did,
            "kind": kind,
            "year": year,
            "title": title,
            "source_file": os.path.basename(path),
            "page": i,
            "text": text,
        })
    return out
