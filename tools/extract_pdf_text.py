"""Extract text from every PDF in the datasheets corpus.

Walks <vendor>/<product-type>/<part-number>/*.pdf under the repo root,
extracting text page-by-page with pypdf. Each PDF becomes one JSON file
under _cache/extracted/ keyed by
<vendor>--<product-type>--<part-number>--<canonical-kind>.json.

Incremental: if the cached SHA-256 matches the current PDF's SHA-256 the
extraction is skipped. Image-only pages (common in TRMs) are kept with
empty text.
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "_cache" / "extracted"

# Directories we never descend into when looking for corpus PDFs.
EXCLUDED_DIRS = {
    ".git", "site-src", "site", "_cache", "tools", "builders", "tests",
    "node_modules", ".claude", ".venv", "venv", "__pycache__",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_kind(pdf_path: Path) -> str:
    # datasheet.pdf -> datasheet; technical-reference-manual.pdf ->
    # technical-reference-manual; pinout-front.pdf -> pinout-front.
    return pdf_path.stem.lower()


def _iter_pdfs() -> list[Path]:
    """Yield <vendor>/<product-type>/<part-number>/*.pdf triples."""
    pdfs: list[Path] = []
    for vendor_dir in sorted(REPO_ROOT.iterdir()):
        if not vendor_dir.is_dir() or vendor_dir.name in EXCLUDED_DIRS:
            continue
        if vendor_dir.name.startswith("."):
            continue
        for product_type_dir in sorted(vendor_dir.iterdir()):
            if not product_type_dir.is_dir():
                continue
            for part_dir in sorted(product_type_dir.iterdir()):
                if not part_dir.is_dir():
                    continue
                for entry in sorted(part_dir.iterdir()):
                    if not entry.is_file():
                        continue
                    if entry.suffix.lower() != ".pdf":
                        continue
                    pdfs.append(entry)
    return pdfs


def _cache_path(pdf: Path) -> Path:
    vendor = pdf.parent.parent.parent.name
    product_type = pdf.parent.parent.name
    part_number = pdf.parent.name
    kind = _canonical_kind(pdf)
    fname = f"{vendor}--{product_type}--{part_number}--{kind}.json"
    return CACHE_DIR / fname


def _extract(pdf: Path, sha: str) -> dict:
    vendor = pdf.parent.parent.parent.name
    product_type = pdf.parent.parent.name
    part_number = pdf.parent.name
    kind = _canonical_kind(pdf)
    size_bytes = pdf.stat().st_size
    rel_path = pdf.relative_to(REPO_ROOT).as_posix()

    pages: list[dict] = []
    page_count = 0
    try:
        reader = PdfReader(str(pdf))
        # Some encrypted PDFs need a decrypt attempt with an empty password.
        if getattr(reader, "is_encrypted", False):
            try:
                reader.decrypt("")
            except Exception:
                pass
        page_count = len(reader.pages)
        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            # pypdf occasionally returns lone Unicode surrogate code
            # points (from broken PDF encoding maps). utf-8 refuses to
            # encode those; strip them so json.dumps + write_text
            # succeed. Backslash-replace preserves debuggability.
            if text:
                text = text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
            pages.append({"n": i, "text": text})
    except Exception as e:
        # Corrupt/unreadable PDFs still get a record so the DB knows they
        # exist — pages just remain empty.
        print(f"  ! extract failed for {rel_path}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)

    return {
        "vendor": vendor,
        "product_type": product_type,
        "part_number": part_number,
        "canonical_kind": kind,
        "filename": pdf.name,
        "path": rel_path,
        "sha256": sha,
        "size_bytes": size_bytes,
        "page_count": page_count,
        "pages": pages,
    }


def main() -> int:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    pdfs = _iter_pdfs()
    total = len(pdfs)
    print(f"scanning {total} PDFs under {REPO_ROOT}")

    extracted = 0
    cached_hits = 0
    total_pages = 0

    for pdf in pdfs:
        rel = pdf.relative_to(REPO_ROOT).as_posix()
        cache = _cache_path(pdf)
        sha = _sha256(pdf)
        reuse = False
        if cache.exists():
            try:
                prev = json.loads(cache.read_text(encoding="utf-8"))
                if prev.get("sha256") == sha:
                    reuse = True
            except Exception:
                reuse = False

        if reuse:
            total_pages += int(prev.get("page_count", 0))
            cached_hits += 1
            print(f"[cache] {rel} ({prev.get('page_count', 0)}p)")
            continue

        print(f"[read ] {rel}")
        data = _extract(pdf, sha)
        total_pages += data["page_count"]
        extracted += 1
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"[done ] {rel} pages={data['page_count']} size={data['size_bytes']}")

    print("")
    print(f"total docs      : {total}")
    print(f"extracted this run: {extracted}")
    print(f"reused from cache: {cached_hits}")
    print(f"total pages     : {total_pages}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
