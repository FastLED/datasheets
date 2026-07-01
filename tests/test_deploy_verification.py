"""Verify the deployed index.db is byte-range servable.

Runnable locally (`python tests/test_deploy_verification.py`) or in CI.

Checks three things — the same three the build-site.yml workflow enforces
after deploy:

  1. HTTP 206 Partial Content is returned for a `Range: bytes=0-4095`
     request WITH `Accept-Encoding: identity`.
  2. The response includes a well-formed `Content-Range: bytes 0-4095/N`
     header (N is the true file size).
  3. The first 4 bytes are `SQLi` (the start of `SQLite format 3\\0`).

If any check fails, exits non-zero. Uses stdlib only (urllib) — no pytest,
no requests, so this can run in a bare Python environment.

Target URL comes from `${DATASHEETS_URL}` (defaults to the FastLED/datasheets
GH Pages URL). Use e.g. `DATASHEETS_URL=http://localhost:8000 python ...`
to test a local `python -m http.server`.

Background: without `Accept-Encoding: identity`, GH Pages gzips
`application/octet-stream` responses and silently ignores the Range
header, so a browser sees the full gzipped file. SQLite then reads the
gzip magic as page 0 and errors out with "database disk image is
malformed". Memex `IMPLEMENT.md` pitfall #1.
"""

from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from typing import Tuple

DEFAULT_URL = "https://fastled.github.io/datasheets"
RANGE_END = 4095   # inclusive; total 4096 bytes
SQLITE_MAGIC = b"SQLi"


def _target_base() -> str:
    return os.environ.get("DATASHEETS_URL", DEFAULT_URL).rstrip("/")


def _fetch_range(url: str) -> Tuple[int, dict[str, str], bytes]:
    """Fetch a single byte range with Accept-Encoding: identity.

    Returns (status_code, headers_dict, body_bytes).
    Raises urllib.error.URLError on transport error.
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "datasheets-deploy-verify/1.0",
            "Range": f"bytes=0-{RANGE_END}",
            # CRITICAL — see docstring.
            "Accept-Encoding": "identity",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            code = resp.getcode()
            headers = {k: v for k, v in resp.getheaders()}
            body = resp.read()
    except urllib.error.HTTPError as e:
        code = e.code
        headers = {k: v for k, v in (e.headers.items() if e.headers else [])}
        body = e.read() if hasattr(e, "read") else b""
    return code, headers, body


def _header(headers: dict[str, str], key: str) -> str | None:
    key_lower = key.lower()
    for k, v in headers.items():
        if k.lower() == key_lower:
            return v
    return None


def _check(cond: bool, ok_msg: str, fail_msg: str) -> bool:
    if cond:
        print(f"  [PASS] {ok_msg}")
        return True
    print(f"  [FAIL] {fail_msg}", file=sys.stderr)
    return False


def verify_index_db(base_url: str) -> bool:
    """Run all three checks. Returns True iff all pass."""
    url = f"{base_url}/index.db"
    print(f"\n=== Verifying {url} ===")
    try:
        code, headers, body = _fetch_range(url)
    except urllib.error.URLError as e:
        print(f"  [FAIL] transport error: {e}", file=sys.stderr)
        return False

    print(f"  HTTP status:   {code}")
    cr = _header(headers, "Content-Range")
    ce = _header(headers, "Content-Encoding")
    cl = _header(headers, "Content-Length")
    print(f"  Content-Range: {cr!r}")
    print(f"  Content-Encoding: {ce!r}")
    print(f"  Content-Length: {cl!r}")
    print(f"  body bytes:    {len(body)} (first 4 = {body[:4]!r})")

    passed = True

    # 1) 206 Partial Content.
    passed &= _check(
        code == 206,
        "HTTP 206 Partial Content",
        f"expected HTTP 206, got {code} — the CDN ignored the Range header. "
        "Almost always means Accept-Encoding: identity was NOT honored and "
        "the response is gzipped. See memex IMPLEMENT.md pitfall #1.",
    )

    # 2) Well-formed Content-Range header.
    cr_ok = False
    total = None
    if cr and cr.lower().startswith("bytes 0-4095/"):
        try:
            total = int(cr.split("/", 1)[1])
            cr_ok = total > 0
        except ValueError:
            cr_ok = False
    passed &= _check(
        cr_ok,
        f"Content-Range: {cr} (total size = {total})",
        f"Content-Range must be `bytes 0-4095/<N>` with N>0; got {cr!r}",
    )

    # 3) First 4 bytes are the SQLite header magic.
    passed &= _check(
        body[:4] == SQLITE_MAGIC,
        "first 4 bytes are 'SQLi'",
        f"first 4 bytes are {body[:4]!r}, expected {SQLITE_MAGIC!r}. "
        "The DB is either corrupt or being served gzipped (would start "
        "with 0x1f 0x8b).",
    )

    return passed


def main() -> int:
    base = _target_base()
    ok = verify_index_db(base)
    if ok:
        print("\nAll deploy verification checks PASSED.")
        return 0
    print("\nDeploy verification FAILED.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
