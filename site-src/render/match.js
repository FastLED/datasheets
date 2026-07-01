// Highlight matches inside a plain (non-snippet) string. FTS5
// snippets already come pre-marked with `<mark>` (see `snippet(...)`
// in `search/query.js`); this helper is for the document header where
// we want to visually reinforce the vendor/part-number tokens.

import { escapeHtml } from '../util/escape.js';

/**
 * @param {string} text
 * @param {string[]} needles — lowercase substrings to highlight
 */
export function highlight(text, needles = []) {
  const src = String(text || '');
  if (!src) return '';
  const uniq = uniqueNeedles(needles);
  if (!uniq.length) return escapeHtml(src);

  const spans = [];
  const lower = src.toLowerCase();
  let i = 0;
  while (i < src.length) {
    let match = null;
    for (const n of uniq) {
      if (lower.startsWith(n, i)) { match = n; break; }
    }
    if (!match) {
      spans.push(escapeHtml(src[i]));
      i += 1;
      continue;
    }
    spans.push(`<mark>${escapeHtml(src.slice(i, i + match.length))}</mark>`);
    i += match.length;
  }
  return spans.join('');
}

function uniqueNeedles(needles) {
  const seen = new Set();
  const out = [];
  for (const raw of needles) {
    const t = String(raw || '').toLowerCase().trim();
    if (!t || t.length < 2 || seen.has(t)) continue;
    seen.add(t);
    out.push(t);
  }
  // Longest first — prevents `esp` masking a longer `esp32` needle.
  out.sort((a, b) => b.length - a.length);
  return out;
}

/**
 * Sanitize a pre-marked FTS5 snippet before insertion. The snippet
 * comes from `snippet(fts5, ..., '<mark>', '</mark>', ...)`, so we
 * KNOW it's UTF-8 text with only `<mark>` / `</mark>` HTML entities.
 * Escape everything except those literal tag pairs.
 *
 * @param {string} snip
 */
export function safeSnippet(snip) {
  const s = String(snip || '');
  // Split on the mark tags, escape the plain fragments, keep the
  // <mark>/</mark> literals as-is.
  const parts = s.split(/(<mark>|<\/mark>)/g);
  return parts
    .map((p) => (p === '<mark>' || p === '</mark>' ? p : escapeHtml(p)))
    .join('');
}
