"""Download official opinion PDFs listed in a cases.json (public court documents) into data/opinions-cache/, politely.

Usage: python3 scripts/fetch_opinions_for_citator.py CASES_JSON [--delay 1.0]
Each case needs "id" and "u" (the court's own document URL). Existing files are skipped. data/ is gitignored.
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "opinions-cache"


def main(argv):
    cases = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    delay = float(argv[argv.index("--delay") + 1]) if "--delay" in argv else 1.0
    CACHE.mkdir(parents=True, exist_ok=True)
    for c in cases:
        out = CACHE / f"{c['id']}.pdf"
        if out.exists() and out.stat().st_size > 1000:
            continue
        req = urllib.request.Request(c["u"], headers={"User-Agent": "indiana-law-citator-prototype (personal research)"})
        try:
            out.write_bytes(urllib.request.urlopen(req, timeout=60).read())
            print("ok", c["id"], out.stat().st_size, flush=True)
        except Exception as error:  # keep going; report at the end
            print("FAILED", c["id"], error, flush=True)
        time.sleep(delay)


if __name__ == "__main__":
    main(sys.argv)
