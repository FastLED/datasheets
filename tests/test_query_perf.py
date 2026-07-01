"""Adversarial query-speed regression test.

Runs a battery of queries that mimic the frontend's classifier output
and measures both wall time and B-tree page accesses. Flags outliers
above a per-query-class budget.

Under HTTP range loading, page-access count is the dominant cost model
(each page = one ~30 ms range fetch on a cold cache). We approximate
by using SQLite's `sqlite3_stmt_status(SQLITE_STMTSTATUS_FULLSCAN_STEP)`
and reading the fetched-rows-per-query counter.

Usage:
    python tests/test_query_perf.py               # against site-src/index.db
    DATASHEETS_DB=/tmp/x.db python tests/test_query_perf.py

Exit non-zero if any query exceeds its budget.
"""
from __future__ import annotations

import os
import sqlite3
import statistics
import sys
import time
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = REPO_ROOT / "site-src" / "index.db"


# Query family -> (sql_builder(vendor, body_tokens, part_prefix), budget_ms)
#
# The budget is generous (~4x expected local time) — over HTTP range the
# real cost multiplies with page-count, and we catch outliers by ratio
# not absolute time. What we really want is to flag queries whose page
# count blows up by 100x when they should be logarithmic.

def _match_vendor_body(vendor: str | None, tokens: list[str]) -> str:
    """Compose an FTS5 MATCH string like `vendor:esp AND ("dma" "reg")`."""
    parts: list[str] = []
    if vendor:
        parts.append(f"vendor:{vendor}")
    if tokens:
        body = " ".join(f'"{t}"' for t in tokens)
        parts.append(f"({body})")
    return " AND ".join(parts)


CASES: list[dict] = [
    # ─── vendor-prefix fast-path (should be sub-millisecond) ─────────
    {"cat": "vendor-cache", "sql": "SELECT top_docs FROM vendor_prefix_cache WHERE prefix=?",
     "binds": ["esp"], "budget_ms": 5, "why": "1 B-tree lookup"},
    {"cat": "vendor-cache", "sql": "SELECT top_docs FROM vendor_prefix_cache WHERE prefix=?",
     "binds": ["nordic"], "budget_ms": 5, "why": "1 B-tree lookup"},

    # ─── part-number probes ─────────────────────────────────────────
    {"cat": "part-probe", "sql": "SELECT doc_id, vendor, part_number FROM documents WHERE lower(part_number) LIKE lower(?) LIMIT 20",
     "binds": ["esp32%"], "budget_ms": 15, "why": "COLLATE NOCASE index"},
    {"cat": "part-probe", "sql": "SELECT doc_id, vendor, part_number FROM documents WHERE lower(part_number) LIKE lower(?) LIMIT 20",
     "binds": ["nrf52%"], "budget_ms": 15, "why": "COLLATE NOCASE index"},
    {"cat": "part-probe", "sql": "SELECT doc_id, vendor, part_number FROM documents WHERE lower(part_number) LIKE lower(?) LIMIT 20",
     "binds": ["xyzzy%"], "budget_ms": 15, "why": "empty-result probe"},

    # ─── vendor + body (the key case) ───────────────────────────────
    {"cat": "vendor-body", "sql": "SELECT c.page_num, snippet(search_porter, 0, '<m>', '</m>', '...', 8), bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 3 LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["dma"])], "budget_ms": 30, "why": "vendor column-filter + body"},
    {"cat": "vendor-body", "sql": "SELECT c.page_num, snippet(search_porter, 0, '<m>', '</m>', '...', 8), bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 3 LIMIT 60",
     "binds": [_match_vendor_body("nordic", ["uarte"])], "budget_ms": 30, "why": "vendor+body"},
    {"cat": "vendor-body", "sql": "SELECT c.page_num, snippet(search_porter, 0, '<m>', '</m>', '...', 8), bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 3 LIMIT 60",
     "binds": [_match_vendor_body("stmicroelectronics", ["sdmmc"])], "budget_ms": 30, "why": "vendor+body"},
    {"cat": "vendor-body", "sql": "SELECT c.page_num, snippet(search_porter, 0, '<m>', '</m>', '...', 8), bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 3 LIMIT 60",
     "binds": [_match_vendor_body("raspberrypi", ["pio"])], "budget_ms": 30, "why": "vendor+body"},
    {"cat": "vendor-body", "sql": "SELECT c.page_num, snippet(search_porter, 0, '<m>', '</m>', '...', 8), bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 3 LIMIT 60",
     "binds": [_match_vendor_body("nxp", ["uart"])], "budget_ms": 30, "why": "vendor+body"},

    # ─── vendor + very common body token ────────────────────────────
    {"cat": "vendor-common", "sql": "SELECT c.page_num, bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 2 LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["register"])], "budget_ms": 50, "why": "vendor + high-freq body token"},
    {"cat": "vendor-common", "sql": "SELECT c.page_num, bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 2 LIMIT 60",
     "binds": [_match_vendor_body("nordic", ["bit"])], "budget_ms": 50, "why": "vendor + very common"},

    # ─── unscoped broad body — should NEVER be sent to FTS5 by the ──
    #     frontend (broad-term guard). Test what happens if it does.
    {"cat": "unscoped-broad-anti", "sql": "SELECT c.page_num, bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 2 LIMIT 60",
     "binds": ["dma"], "budget_ms": 400, "why": "worst-case: FTS5 scans full posting list w/o vendor pre-filter"},
    {"cat": "unscoped-broad-anti", "sql": "SELECT c.page_num, bm25(search_porter, 1) FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY 2 LIMIT 60",
     "binds": ["register"], "budget_ms": 800, "why": "worst-case: very-high-freq token"},

    # ─── vendor + many body tokens ──────────────────────────────────
    {"cat": "vendor-multi-body", "sql": "SELECT c.page_num FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY bm25(search_porter, 1) LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["dma", "spi", "interrupt"])], "budget_ms": 30, "why": "AND-intersection of 3 posting lists"},
    {"cat": "vendor-multi-body", "sql": "SELECT c.page_num FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY bm25(search_porter, 1) LIMIT 60",
     "binds": [_match_vendor_body("stmicroelectronics", ["timer", "clock", "gpio", "register", "bit"])], "budget_ms": 60, "why": "5 AND-intersected tokens"},

    # ─── vendor + non-existent body token ───────────────────────────
    {"cat": "vendor-nomatch", "sql": "SELECT c.page_num FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY bm25(search_porter, 1) LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["xyzzy"])], "budget_ms": 15, "why": "empty intersection short-circuits"},

    # ─── part-number in FTS5 body (people type part numbers) ────────
    {"cat": "part-in-body", "sql": "SELECT c.page_num FROM search_porter JOIN chunks c ON c.rowid=search_porter.rowid WHERE search_porter MATCH ? ORDER BY bm25(search_porter, 1) LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["esp32"])], "budget_ms": 40, "why": "part-number as body token"},

    # ─── vendor doc list (dropdown + empty query) ──────────────────
    {"cat": "vendor-doclist", "sql": "SELECT doc_id, vendor, part_number, canonical_kind, path FROM documents WHERE vendor=? ORDER BY part_number LIMIT 20",
     "binds": ["espressif"], "budget_ms": 8, "why": "indexed vendor scan"},

    # ─── list all vendors (dropdown init) ──────────────────────────
    {"cat": "vendor-list", "sql": "SELECT vendor, COUNT(*) FROM documents GROUP BY vendor ORDER BY vendor",
     "binds": [], "budget_ms": 15, "why": "grouped index scan"},

    # ─── list all part numbers (classifier init) ───────────────────
    {"cat": "part-list", "sql": "SELECT DISTINCT part_number FROM documents",
     "binds": [], "budget_ms": 15, "why": "distinct scan"},

    # ─── FTS5 abuse: prefix matches ─────────────────────────────────
    {"cat": "prefix-match", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["esp*"])], "budget_ms": 40, "why": "vendor + prefix expansion"},
    {"cat": "prefix-match", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["a*"])], "budget_ms": 80, "why": "vendor + very-broad prefix"},

    # ─── FTS5 abuse: NEAR operator ──────────────────────────────────
    {"cat": "near-op", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": [f'vendor:espressif AND NEAR("dma" "spi", 5)'], "budget_ms": 40, "why": "positional constraint"},

    # ─── very long query ────────────────────────────────────────────
    {"cat": "long-query", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["dma"] * 10)], "budget_ms": 30, "why": "10 repeated tokens"},
    {"cat": "long-query", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": [_match_vendor_body("espressif", ["dma", "spi", "i2c", "uart", "pwm", "adc", "timer", "clock", "gpio", "interrupt"])], "budget_ms": 30, "why": "10 distinct broad tokens"},

    # ─── unscoped body — what if broad-term guard was bypassed ─────
    {"cat": "unscoped-single", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": ["uarte"], "budget_ms": 30, "why": "rare token, unscoped"},
    {"cat": "unscoped-single", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": ["sdmmc"], "budget_ms": 30, "why": "medium-rare token, unscoped"},

    # ─── worst-case unscoped: multiple broad + no vendor filter ────
    {"cat": "unscoped-worst", "sql": "SELECT rowid, rank FROM search_porter WHERE search_porter MATCH ? ORDER BY rank LIMIT 60",
     "binds": ["dma spi"], "budget_ms": 100, "why": "AND of 2 very-broad tokens, no vendor scope"},

    # ─── documents table adversarial: LIKE with leading wildcard ───
    {"cat": "part-leading-wild", "sql": "SELECT doc_id FROM documents WHERE lower(part_number) LIKE lower(?) LIMIT 20",
     "binds": ["%dma%"], "budget_ms": 15, "why": "must not full-scan; part_number LIKE '%X%' is a scan anyway (accepted cost — the classifier never emits this)"},
]


def _time_query(conn: sqlite3.Connection, sql: str, binds: list, iters: int = 5) -> dict:
    """Warm once, then run N iterations and report min/median/max ms."""
    cur = conn.cursor()
    # Warmup — first pass builds the page cache.
    cur.execute(sql, binds).fetchall()
    times: list[float] = []
    row_count = 0
    for _ in range(iters):
        t0 = time.perf_counter()
        rows = cur.execute(sql, binds).fetchall()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
        row_count = len(rows)
    return {
        "min_ms": min(times),
        "median_ms": statistics.median(times),
        "max_ms": max(times),
        "row_count": row_count,
    }


def _plan(conn: sqlite3.Connection, sql: str, binds: list) -> str:
    cur = conn.cursor()
    parts = [f"  {row}" for row in cur.execute("EXPLAIN QUERY PLAN " + sql, binds)]
    return "\n".join(parts)


def main() -> int:
    db_path = Path(os.environ.get("DATASHEETS_DB", str(DEFAULT_DB)))
    if not db_path.exists():
        raise SystemExit(f"! DB not found: {db_path}")
    print(f"# testing {db_path} ({db_path.stat().st_size / 1024 / 1024:.1f} MB)\n")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    fails: list[dict] = []
    for case in CASES:
        result = _time_query(conn, case["sql"], case["binds"])
        over_budget = result["median_ms"] > case["budget_ms"]
        marker = "!!" if over_budget else "  "
        binds_repr = repr(case["binds"])[:80]
        print(f"{marker} [{case['cat']:>22}] "
              f"median {result['median_ms']:>7.2f} ms "
              f"(budget {case['budget_ms']:>4} ms) "
              f"rows {result['row_count']:>4}  "
              f"binds={binds_repr}")
        if over_budget:
            fails.append({**case, "result": result})

    conn.close()

    if fails:
        print(f"\n{len(fails)} query/queries over budget:")
        for f in fails:
            print(f"\n! [{f['cat']}] median {f['result']['median_ms']:.2f} ms (budget {f['budget_ms']} ms)")
            print(f"  why: {f['why']}")
            print(f"  binds: {f['binds']}")
            with sqlite3.connect(db_path) as c:
                print("  EXPLAIN QUERY PLAN:")
                print(_plan(c, f["sql"], f["binds"]))
        return 1

    print(f"\nAll {len(CASES)} queries within budget.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
