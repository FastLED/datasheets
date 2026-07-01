// Small formatters shared by row renderers.

import { escapeHtml } from '../util/escape.js';

/**
 * Bytes → "1.2 MB" / "812 KB" / "312 B".
 * @param {number} n
 */
export function fmtBytes(n) {
  const v = Number(n || 0);
  if (!v) return '';
  if (v >= 1024 * 1024) return `${(v / (1024 * 1024)).toFixed(1)} MB`;
  if (v >= 1024) return `${(v / 1024).toFixed(0)} KB`;
  return `${v} B`;
}

/**
 * Page count → "312 pages" / "1 page".
 * @param {number} n
 */
export function fmtPages(n) {
  const v = Number(n || 0);
  if (!v) return '';
  return v === 1 ? '1 page' : `${v.toLocaleString()} pages`;
}

/**
 * A short ISO date → local formatted date. Falls back to the raw
 * string if `Date` can't parse it.
 * @param {string} iso
 */
export function fmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return escapeHtml(iso);
  return d.toISOString().slice(0, 10);
}

// PDF URL template state. Populated at boot from `_meta.json` (see
// `search.js`). Two roots so we can route LFS-tracked files to a
// different host than shipped-inline files.
//
// Defaults are safe: local `pdf/` prefix. When `_meta.json.pdf_root_lfs`
// points to a public raw host, LFS docs route there and the artifact
// stays small; otherwise both roots stay `pdf/` and PDFs ship in the
// artifact.
let _pdfRoot = 'pdf/';
let _pdfRootLfs = 'pdf/';

/**
 * Configure the two PDF roots. Called once at boot from `search.js`
 * with the values from `_meta.json`. Both accept `pdf/`-style relative
 * prefixes or absolute URLs; a trailing slash is added if missing so
 * concatenation is safe.
 *
 * @param {{pdf_root?: string, pdf_root_lfs?: string}} config
 */
export function configurePdfRoots(config) {
  const norm = (s, fallback) => {
    const v = String(s || '').trim();
    if (!v) return fallback;
    return v.endsWith('/') ? v : v + '/';
  };
  _pdfRoot = norm(config && config.pdf_root, _pdfRoot);
  _pdfRootLfs = norm(config && config.pdf_root_lfs, _pdfRootLfs);
}

/**
 * Build a link URL for a doc.
 *
 * The template detects LFS vs non-LFS from the `is_lfs` bool that
 * `build_index.py` writes on each `documents` row (via
 * `git check-attr filter`). LFS-tracked docs prepend `pdf_root_lfs`;
 * plain docs prepend `pdf_root`.
 *
 * @param {string} p — path relative to repo root, e.g.
 *   `espressif/soc/ESP32/datasheet.pdf`
 * @param {boolean|number} [isLfs=false] — falsy = shipped-locally,
 *   truthy = LFS-tracked (route via `pdf_root_lfs`).
 */
export function pdfHref(p, isLfs) {
  const path = String(p || '').replace(/^\/+/, '');
  const root = isLfs ? _pdfRootLfs : _pdfRoot;
  // If the root is an absolute URL we assume the caller wants the
  // path to be URL-safe; use encodeURI so spaces/etc survive. If it's
  // a relative `pdf/` prefix, escapeHtml is enough since the browser
  // resolves the relative path in-place.
  if (/^https?:/i.test(root)) {
    return root + encodeURI(path);
  }
  return root + escapeHtml(path);
}
