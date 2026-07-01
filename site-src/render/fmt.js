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

/**
 * Escape a document path for use in a link's `href`. The `pdf/` prefix
 * is added by the site's asset layout — see `tools/build_site.py`.
 *
 * @param {string} p
 */
export function pdfHref(p) {
  const path = String(p || '').replace(/^\/+/, '');
  return `pdf/${escapeHtml(path)}`;
}
