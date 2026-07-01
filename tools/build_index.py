"""Build site-src/index.db from _cache/extracted/*.json.

Schema mirrors the memex-style layout in issue #2:
  - documents (metadata + indexes on vendor/part/type/kind)
  - chunks (external content for FTS5)
  - search_porter FTS5 (external-content, porter stemming)
  - search_trigram FTS5 (external-content, trigram)
  - vendor_prefix_cache (populated by build_vendor_cache.py)

Critical pitfalls from memex IMPLEMENT.md:
  - `PRAGMA page_size = 4096` MUST be set BEFORE the first CREATE, or
    the client's `maxPageSize` mismatch produces silent corruption when
    the DB is read via HTTP range requests.
  - External-content FTS5 keeps the FTS rows tiny; we align the
    chunks.rowid so INSERT INTO search_* (search_*) VALUES('rebuild')
    can pick up the correct source rows.
  - End with PRAGMA optimize + VACUUM so pages sit contiguously.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = REPO_ROOT / "_cache" / "extracted"
DB_PATH = REPO_ROOT / "site-src" / "index.db"


def _iter_cache_files() -> list[Path]:
    return sorted(CACHE_DIR.glob("*.json"))


def _build_schema(cur: sqlite3.Cursor) -> None:
    # documents
    cur.execute(
        """
        CREATE TABLE documents (
            doc_id           INTEGER PRIMARY KEY,
            vendor           TEXT NOT NULL,
            product_type     TEXT NOT NULL,
            part_number      TEXT NOT NULL,
            canonical_kind   TEXT NOT NULL,
            filename         TEXT NOT NULL,
            sha256           TEXT NOT NULL,
            size_bytes       INTEGER NOT NULL,
            page_count       INTEGER NOT NULL,
            path             TEXT NOT NULL
        )
        """
    )
    cur.execute("CREATE INDEX idx_documents_vendor ON documents(vendor)")
    cur.execute("CREATE INDEX idx_documents_part ON documents(part_number COLLATE NOCASE)")
    cur.execute("CREATE INDEX idx_documents_type ON documents(product_type)")
    cur.execute("CREATE INDEX idx_documents_kind ON documents(canonical_kind)")

    # chunks — external content source for the FTS5 tables.
    cur.execute(
        """
        CREATE TABLE chunks (
            doc_id     INTEGER NOT NULL,
            page_num   INTEGER NOT NULL,
            text       TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
        """
    )
    cur.execute("CREATE INDEX idx_chunks_doc ON chunks(doc_id)")

    # FTS5 tables — external content (`content='chunks'`) means the FTS
    # tables reference chunks by rowid rather than duplicating the text.
    cur.execute(
        """
        CREATE VIRTUAL TABLE search_porter USING fts5(
            text,
            content='chunks', content_rowid='rowid',
            tokenize='porter unicode61 remove_diacritics 1',
            columnsize=0
        )
        """
    )
    # Note: `search_trigram` was originally spec'd for substring matches
    # but we dropped it — the DB has a per-file 100 MB GitHub Pages
    # limit, and dropping trigram roughly halves the FTS5 overhead.
    # Vendor-prefix substring queries are served by the pre-baked
    # `vendor_prefix_cache` B-tree table instead; body FTS5 remains
    # porter-stemmed for the rest.

    # Vendor-prefix fast path (populated by build_vendor_cache.py).
    cur.execute(
        """
        CREATE TABLE vendor_prefix_cache (
            prefix    TEXT PRIMARY KEY,
            vendor    TEXT NOT NULL,
            top_docs  TEXT NOT NULL
        )
        """
    )


def _load_cache_records() -> list[dict]:
    records: list[dict] = []
    for f in _iter_cache_files():
        try:
            records.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception as e:
            print(f"! skipping malformed cache {f}: {e}", file=sys.stderr)
    # Stable ordering by (vendor, product_type, part_number,
    # canonical_kind) so doc_id assignment is deterministic.
    records.sort(key=lambda r: (
        r.get("vendor", ""), r.get("product_type", ""),
        r.get("part_number", ""), r.get("canonical_kind", ""),
    ))
    return records


def main() -> int:
    if not CACHE_DIR.exists():
        raise SystemExit(f"no cache dir at {CACHE_DIR}; run extract_pdf_text.py first")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Pragmas MUST come before the first CREATE. page_size is a
    # persistent property of the DB and can only be set on an empty DB.
    #
    # We use `journal_mode=DELETE` (the default rollback journal) rather
    # than WAL — the built DB is read-only from the browser's POV, and
    # WAL leaves `.db-shm` + `.db-wal` sidecar files that we'd otherwise
    # ship in the artifact.
    cur.execute("PRAGMA page_size = 4096")
    cur.execute("PRAGMA journal_mode = DELETE")

    _build_schema(cur)

    records = _load_cache_records()
    print(f"loaded {len(records)} document records")

    # Populate documents.
    doc_rows = []
    for rec in records:
        doc_rows.append((
            rec["vendor"],
            rec["product_type"],
            rec["part_number"],
            rec["canonical_kind"],
            rec["filename"],
            rec["sha256"],
            int(rec["size_bytes"]),
            int(rec["page_count"]),
            rec["path"],
        ))
    cur.executemany(
        """
        INSERT INTO documents (
            vendor, product_type, part_number, canonical_kind,
            filename, sha256, size_bytes, page_count, path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        doc_rows,
    )

    # Map (vendor, product_type, part_number, canonical_kind) -> doc_id.
    id_map: dict[tuple[str, str, str, str], int] = {}
    for row in cur.execute(
        "SELECT doc_id, vendor, product_type, part_number, canonical_kind FROM documents"
    ):
        id_map[(row[1], row[2], row[3], row[4])] = row[0]

    # Populate chunks. Assigning rowid explicitly keeps FTS5 rowids in
    # step with chunks rowids so the 'rebuild' command hits the right
    # source rows.
    #
    # Three shrink passes here — see issue #3 for the full rationale.
    # Hard budget is 40 MB for `site/index.db` (asserted below), which
    # forces us to be aggressive:
    #   1. Collapse consecutive whitespace to single spaces.
    #   2. Drop pages with fewer than 100 alphanumeric characters —
    #      pure-image pages, page-number-only pages, TOC pages, etc.
    #   3. Truncate the retained text to 300 chars per page — enough
    #      for the section heading + first sentence of body (which is
    #      where topic markers live on TRM pages).
    import re
    _ws = re.compile(r"\s+")
    _alnum = re.compile(r"[A-Za-z0-9]")
    TRUNC_CHARS = 300

    def _shrink(text: str) -> str:
        return _ws.sub(" ", text).strip()

    def _keep(text: str) -> bool:
        return len(_alnum.findall(text)) >= 100

    def _truncate(text: str) -> str:
        # Truncate at word boundary if possible, so snippet() doesn't
        # slice a token mid-way.
        if len(text) <= TRUNC_CHARS:
            return text
        cut = text[:TRUNC_CHARS]
        last_space = cut.rfind(" ")
        return cut[:last_space] if last_space > TRUNC_CHARS - 30 else cut

    total_chunks = 0
    dropped_chunks = 0
    next_rowid = 1
    for rec in records:
        key = (rec["vendor"], rec["product_type"], rec["part_number"], rec["canonical_kind"])
        doc_id = id_map[key]
        chunk_rows = []
        for page in rec.get("pages", []):
            text = _shrink(page.get("text") or "")
            if not _keep(text):
                dropped_chunks += 1
                continue
            text = _truncate(text)
            chunk_rows.append((next_rowid, doc_id, int(page["n"]), text))
            next_rowid += 1
        if chunk_rows:
            cur.executemany(
                "INSERT INTO chunks(rowid, doc_id, page_num, text) VALUES (?, ?, ?, ?)",
                chunk_rows,
            )
            total_chunks += len(chunk_rows)

    print(f"inserted {len(records)} documents, {total_chunks} chunks (dropped {dropped_chunks} low-content pages)")

    # Rebuild FTS5 indexes from the external content table.
    cur.execute("INSERT INTO search_porter(search_porter) VALUES('rebuild')")

    conn.commit()

    # Final layout pass. optimize compresses FTS5 segments; VACUUM
    # rewrites the DB so adjacent rows share pages, which minimizes the
    # number of HTTP range fetches at query time.
    cur.execute("PRAGMA optimize")
    conn.commit()
    # VACUUM cannot run inside a transaction; sqlite3 module handles
    # commit automatically when isolation_level=None or we call commit
    # first.
    conn.isolation_level = None
    cur.execute("VACUUM")
    conn.isolation_level = ""

    conn.close()

    size = DB_PATH.stat().st_size
    size_mb = size / (1024 * 1024)
    print(f"wrote {DB_PATH} ({size} bytes, {size_mb:.1f} MB)")
    # Hard budget per issue #3. Bloat past this = the query cost model
    # breaks and we should not deploy — fail the build loudly.
    MAX_MB = 40
    if size_mb > MAX_MB:
        raise SystemExit(
            f"! index.db is {size_mb:.1f} MB, exceeds {MAX_MB} MB budget "
            f"(see issue #3). Tune TRUNC_CHARS in build_index.py."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
