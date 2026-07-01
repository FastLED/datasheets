"""Populate vendor_prefix_cache in site-src/index.db.

Every 1-/2-/3-/4-char lowercase prefix of every distinct
`documents.vendor` value gets a row. Aliases from issue #2 body are
also inserted so `esp` -> espressif, `stm32` -> stmicroelectronics,
etc. work with a single PK lookup.

Each row's `top_docs` field is a JSON array of the vendor's top 10
docs sorted by (canonical_kind priority, part_number).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "site-src" / "index.db"

# Higher score wins. Everything not in this table falls back to a
# constant low value so it still sorts after the recognised kinds.
KIND_PRIORITY = {
    "datasheet": 100,
    "technical-reference-manual": 90,
    "reference-manual": 85,
    "user-manual": 80,
    "errata": 60,
    "product-brief": 40,
    "programmers-guide": 30,
    "hardware-design-with-rp2040": 25,
    "datasheet-industrial": 20,
    "pinout-front": 15,
    "pinout-back": 10,
    "schematic": 10,
}
KIND_FALLBACK = 0

# Aliases in the issue #2 body (esp -> espressif, etc.). These are
# inserted as-is (in addition to whatever real vendor slugs prefix them)
# so `esp` -> espressif is a single PK read even though `esp` is not a
# real vendor.
ALIASES = {
    "esp": "espressif",
    "st": "stmicroelectronics",
    "stm32": "stmicroelectronics",
    "pico": "raspberrypi",
    "rpi": "raspberrypi",
    "atmel": "microchip",
    "teensy": "pjrc",
    "kinetis": "nxp",
}


def _kind_priority(kind: str) -> int:
    return KIND_PRIORITY.get(kind, KIND_FALLBACK)


def _top_docs_for_vendor(cur: sqlite3.Cursor, vendor: str, limit: int = 10) -> list[dict]:
    rows = cur.execute(
        """
        SELECT doc_id, vendor, part_number, canonical_kind, path
        FROM documents
        WHERE vendor = ?
        """,
        (vendor,),
    ).fetchall()

    # Sort by (kind priority DESC, part_number ASC). Stable Python sort
    # handles the tie-break cleanly.
    sortable = [
        (
            -_kind_priority(r[3]),
            r[2].lower(),
            {
                "doc_id": r[0],
                "vendor": r[1],
                "part_number": r[2],
                "canonical_kind": r[3],
                "path": r[4],
            },
        )
        for r in rows
    ]
    sortable.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in sortable[:limit]]


def _prefixes(s: str) -> list[str]:
    out = []
    for n in (1, 2, 3, 4):
        if len(s) >= n:
            out.append(s[:n])
    return out


def main() -> int:
    if not DB_PATH.exists():
        raise SystemExit(f"missing {DB_PATH}; run build_index.py first")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Wipe existing cache in case we're rebuilding.
    cur.execute("DELETE FROM vendor_prefix_cache")

    vendors = [row[0] for row in cur.execute(
        "SELECT DISTINCT vendor FROM documents ORDER BY vendor"
    ).fetchall()]

    # Precompute top-doc payloads once per vendor.
    top_docs_by_vendor: dict[str, str] = {}
    for v in vendors:
        docs = _top_docs_for_vendor(cur, v)
        top_docs_by_vendor[v] = json.dumps(docs, ensure_ascii=False)

    # Also precompute payloads for alias targets that are actual vendors
    # (which they all are, by construction).
    for alias, target in ALIASES.items():
        if target not in top_docs_by_vendor:
            docs = _top_docs_for_vendor(cur, target)
            top_docs_by_vendor[target] = json.dumps(docs, ensure_ascii=False)

    # Prefix -> (vendor, payload). Later inserts win on tie; we prefer
    # real vendor slugs over aliases for shared prefixes (e.g. `st` is
    # already the 2-char prefix of `stmicroelectronics`, so it stays
    # mapped to `stmicroelectronics` from either path).
    prefix_rows: dict[str, tuple[str, str]] = {}

    # 1) Real vendor prefixes.
    for v in vendors:
        v_lower = v.lower()
        payload = top_docs_by_vendor[v]
        for p in _prefixes(v_lower):
            # A vendor's own prefix always resolves to itself. If two
            # vendors share a prefix (e.g. `n` for `nordic`/`nxp`), the
            # last write wins deterministically because vendors is sorted
            # alphabetically — we pick the alphabetically-last vendor.
            # That's arbitrary but stable and the UI can still handle
            # ambiguity via the dropdown.
            prefix_rows[p] = (v, payload)

    # 2) Aliases override — they encode explicit user intent.
    for alias, target in ALIASES.items():
        if target not in top_docs_by_vendor:
            continue  # target vendor has no docs in the corpus
        payload = top_docs_by_vendor[target]
        prefix_rows[alias.lower()] = (target, payload)

    cur.executemany(
        "INSERT INTO vendor_prefix_cache(prefix, vendor, top_docs) VALUES (?, ?, ?)",
        [(p, v, payload) for p, (v, payload) in sorted(prefix_rows.items())],
    )

    conn.commit()

    print(f"vendors                : {len(vendors)}")
    print(f"aliases                : {len(ALIASES)}")
    print(f"vendor_prefix_cache rows: {len(prefix_rows)}")

    cur.execute("PRAGMA optimize")
    conn.commit()
    conn.isolation_level = None
    cur.execute("VACUUM")
    conn.isolation_level = ""

    conn.close()

    print(f"updated {DB_PATH} ({DB_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
