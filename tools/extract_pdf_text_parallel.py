"""Parallel wrapper around extract_pdf_text — spawns N worker processes.

Each worker imports extract_pdf_text as a library and processes an
assigned slice of PDFs. Incremental cache means already-extracted PDFs
are skipped in each worker.
"""
from __future__ import annotations

import multiprocessing as mp
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_pdf_text as ext  # noqa: E402


def _worker(paths: list[Path]) -> int:
    ext.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    done = 0
    for pdf in paths:
        cache = ext._cache_path(pdf)
        try:
            sha = ext._sha256(pdf)
        except Exception as e:
            print(f"! sha {pdf}: {e}", file=sys.stderr)
            continue
        if cache.exists():
            try:
                import json
                existing = json.loads(cache.read_text(encoding="utf-8"))
                if existing.get("sha256") == sha:
                    done += 1
                    continue
            except Exception:
                pass
        try:
            rec = ext._extract(pdf, sha)
            import json
            cache.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
            done += 1
            print(f"[pid={mp.current_process().pid}] {pdf.relative_to(ext.REPO_ROOT)} — {rec['page_count']} pages", flush=True)
        except Exception as e:
            print(f"! extract {pdf}: {e}", file=sys.stderr)
    return done


def main() -> int:
    n_workers = 6
    ext.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pdfs = ext._iter_pdfs()
    print(f"found {len(pdfs)} PDFs; using {n_workers} workers")
    # Round-robin split so a slow worker doesn't get all the huge TRMs.
    slices = [[] for _ in range(n_workers)]
    # Sort by file size DESC so biggest go first — better load balance.
    pdfs.sort(key=lambda p: -p.stat().st_size)
    for i, p in enumerate(pdfs):
        slices[i % n_workers].append(p)

    with mp.Pool(n_workers) as pool:
        results = pool.map(_worker, slices)
    print(f"done — total processed: {sum(results)} of {len(pdfs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
