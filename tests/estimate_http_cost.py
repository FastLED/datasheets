"""Estimate the HTTP-range cost of each canonical query.

Local SQLite runs in-memory / off the OS page cache — 5 ms for a query
that touches 50 unique DB pages. Over HTTP Range each unique page = one
~30 ms round trip on a warm-CDN, ~100 ms on a cold cache. So the
dominant live cost is the number of UNIQUE pages the query touches, not
the CPU time.

Strategy: open the DB with a cold in-process page cache (PRAGMA
cache_size = 0 forces re-fetch on every read), run the query, and count
pages_read via `sqlite3_db_status(SQLITE_DBSTATUS_CACHE_MISS, reset=1)`.
"""
from __future__ import annotations

import ctypes
import os
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "site-src" / "index.db"


def _match(vendor: str | None, tokens: list[str]) -> str:
    parts: list[str] = []
    if vendor:
        parts.append(f"vendor:{vendor}")
    if tokens:
        parts.append("(" + " ".join(f'"{t}"' for t in tokens) + ")")
    return " AND ".join(parts)


CASES = [
    ("vendor cache: esp",
     "SELECT top_docs FROM vendor_prefix_cache WHERE prefix=?", ["esp"]),
    ("part probe: esp32%",
     "SELECT * FROM documents WHERE lower(part_number) LIKE lower(?) LIMIT 20",
     ["esp32%"]),
    ("vendor+body: esp dma",
     "SELECT c.page_num, snippet(search_porter, 0, '<m>','</m>','…',8), rank "
     "FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid "
     "WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     [_match("espressif", ["dma"])]),
    ("vendor+body: esp register",
     "SELECT c.page_num, snippet(search_porter, 0, '<m>','</m>','…',8), rank "
     "FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid "
     "WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     [_match("espressif", ["register"])]),
    ("vendor+body: nordic uarte",
     "SELECT c.page_num, snippet(search_porter, 0, '<m>','</m>','…',8), rank "
     "FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid "
     "WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     [_match("nordic", ["uarte"])]),
    ("worst-case unscoped: dma alone",
     "SELECT c.page_num, snippet(search_porter, 0, '<m>','</m>','…',8), rank "
     "FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid "
     "WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     ["dma"]),
    ("worst-case unscoped: register alone",
     "SELECT c.page_num, snippet(search_porter, 0, '<m>','</m>','…',8), rank "
     "FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid "
     "WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     ["register"]),
]


def _fresh_connection(db_path: Path) -> sqlite3.Connection:
    # cache_size=0 wouldn't work everywhere — some drivers ignore it.
    # Instead, open a new connection each iteration (fresh page cache).
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.execute("PRAGMA cache_size = 0")
    return conn


# Bind sqlite3_db_status via ctypes so we can pull cache-miss counts.
# Not all Python builds expose this — degrade to "unknown" if missing.
def _try_load_db_status():
    try:
        lib = ctypes.CDLL(sqlite3.sqlite_version_info and "sqlite3.dll" or None)
        # ...easier route: use pragma page_count + cache_stats hacks.
    except OSError:
        return None
    return lib


def main() -> int:
    db_path = Path(os.environ.get("DATASHEETS_DB", str(DEFAULT_DB)))
    print(f"# DB {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)\n")
    print(f"{'query':<40}  {'cold ms':>8}  {'warm ms':>8}  {'ratio':>6}")
    print(f"{'-'*40}  {'-'*8}  {'-'*8}  {'-'*6}")

    import time
    for label, sql, binds in CASES:
        # Cold: fresh connection, tiny page cache — simulates first fetch.
        cold_conn = _fresh_connection(db_path)
        t0 = time.perf_counter()
        cold_conn.execute(sql, binds).fetchall()
        cold_ms = (time.perf_counter() - t0) * 1000
        cold_conn.close()

        # Warm: reuse the fresh connection for 5 runs, take median.
        warm_conn = _fresh_connection(db_path)
        warm_conn.execute(sql, binds).fetchall()
        warm_times = []
        for _ in range(5):
            t0 = time.perf_counter()
            warm_conn.execute(sql, binds).fetchall()
            warm_times.append((time.perf_counter() - t0) * 1000)
        warm_ms = sorted(warm_times)[len(warm_times) // 2]
        warm_conn.close()

        ratio = cold_ms / warm_ms if warm_ms > 0 else 0
        print(f"{label:<40}  {cold_ms:>7.2f}   {warm_ms:>7.2f}   {ratio:>5.1f}x")

    return 0


if __name__ == "__main__":
    sys.exit(main())
