"""Assemble the final `site/` directory from `site-src/` and the built DB.

This is the last step of the pipeline. Upstream steps (in order):
    1. tools/fetch_memex.py       -> site-src/vendor/  (memex WASM bundle)
    2. tools/extract_pdf_text.py  -> _cache/extracted/*.json
    3. tools/build_index.py       -> site-src/index.db
    4. tools/build_vendor_cache.py-> ALTERs site-src/index.db

This script copies the assembled `site-src/` tree into `site/` verbatim,
writes `site/_meta.json` (commit SHA, memex SHA, built_at, doc_count),
and writes `site/.nojekyll` so GitHub Pages does NOT run Jekyll on us
(critical — Jekyll drops underscore-prefixed files and rewrites paths).

Idempotent: `site/` is rebuilt from scratch every run.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_SRC = REPO_ROOT / "site-src"
SITE_OUT = REPO_ROOT / "site"
MEMEX_SHA_FILE = REPO_ROOT / "builders" / "MEMEX_SHA"

# Files and directories inside site-src/ that get copied verbatim.
# Missing entries are silently skipped so partial local builds still work.
COPY_DIRS = ("search", "render", "modal", "style", "util", "vendor", "pdfjs")
COPY_FILE_PATTERNS = ("*.html", "*.js", "*.css")
COPY_TOP_LEVEL_FILES = ("index.db",)


def _commit_sha() -> str:
    # Prefer GH Actions' commit SHA when available; fall back to git rev-parse.
    sha = os.environ.get("GITHUB_SHA")
    if sha:
        return sha
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
        )
        return out.decode("ascii").strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _memex_sha() -> str:
    if MEMEX_SHA_FILE.exists():
        return MEMEX_SHA_FILE.read_text(encoding="utf-8").strip()
    return "unknown"


def _doc_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            cur = conn.execute("SELECT COUNT(*) FROM documents")
            row = cur.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()
    except sqlite3.Error as e:
        print(f"[warn] could not read doc_count from {db_path}: {e}",
              file=sys.stderr)
        return 0


def _reset_output() -> None:
    if SITE_OUT.exists():
        shutil.rmtree(SITE_OUT)
    SITE_OUT.mkdir(parents=True, exist_ok=True)


def _copy_dirs() -> None:
    for name in COPY_DIRS:
        src = SITE_SRC / name
        if not src.exists():
            print(f"[skip] {src} does not exist")
            continue
        dst = SITE_OUT / name
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print(f"[copy] {src} -> {dst}")


def _copy_top_level_globs() -> None:
    for pattern in COPY_FILE_PATTERNS:
        for src in SITE_SRC.glob(pattern):
            if not src.is_file():
                continue
            dst = SITE_OUT / src.name
            shutil.copy2(src, dst)
            print(f"[copy] {src} -> {dst}")


def _copy_top_level_files() -> None:
    for name in COPY_TOP_LEVEL_FILES:
        src = SITE_SRC / name
        if not src.exists():
            print(f"[skip] {src} does not exist")
            continue
        dst = SITE_OUT / name
        shutil.copy2(src, dst)
        print(f"[copy] {src} -> {dst}")


def _write_meta(commit: str, memex_sha: str, doc_count: int) -> Path:
    meta = {
        "commit": commit,
        "memex_sha": memex_sha,
        "built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "doc_count": doc_count,
    }
    dst = SITE_OUT / "_meta.json"
    dst.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"[meta] {dst} = {meta}")
    return dst


def _write_nojekyll() -> Path:
    # Empty file; presence alone signals to GH Pages: skip Jekyll.
    dst = SITE_OUT / ".nojekyll"
    dst.write_bytes(b"")
    print(f"[meta] {dst}")
    return dst


def main() -> int:
    if not SITE_SRC.exists():
        raise SystemExit(f"missing {SITE_SRC}")

    _reset_output()
    _copy_dirs()
    _copy_top_level_globs()
    _copy_top_level_files()

    commit = _commit_sha()
    memex_sha = _memex_sha()
    doc_count = _doc_count(SITE_OUT / "index.db")

    _write_meta(commit, memex_sha, doc_count)
    _write_nojekyll()

    print(f"\nSite assembled at {SITE_OUT}")
    print(f"  commit    = {commit}")
    print(f"  memex_sha = {memex_sha}")
    print(f"  doc_count = {doc_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
