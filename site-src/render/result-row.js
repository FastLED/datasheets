// One row per document. Header shows vendor / part / kind + metadata,
// followed by up to 3 page-snippet children (populated by body FTS5).
//
// For vendor-only + part-number-probe results the doc has no page_hits
// — the renderer just skips the snippet block.

import { escapeHtml } from '../util/escape.js';
import { fmtBytes, fmtPages, pdfHref } from './fmt.js';
import { highlight } from './match.js';
import { renderPageHit } from './page-hit.js';

/**
 * @param {{
 *   doc_id: number, vendor: string, product_type: string,
 *   part_number: string, canonical_kind: string, path: string,
 *   filename?: string, page_count?: number, size_bytes?: number,
 *   page_hits?: Array<{page_num:number, snippet:string}>,
 * }} doc
 * @param {string[]} highlightNeedles — tokens from the query for header
 *                                       highlight (part, vendor, etc.)
 */
export function renderResultRow(doc, highlightNeedles = []) {
  const part = highlight(doc.part_number || '', highlightNeedles);
  const vendor = escapeHtml(doc.vendor || '');
  const kind = escapeHtml(doc.canonical_kind || '');
  const productType = escapeHtml(doc.product_type || '');
  const path = String(doc.path || '');
  const href = pdfHref(path, doc.is_lfs);

  const bytes = fmtBytes(doc.size_bytes);
  const pages = fmtPages(doc.page_count);
  const metaBits = [vendor, productType, bytes, pages].filter(Boolean);
  const meta = metaBits.map((b) => `<span>${b}</span>`).join('');

  const pageHits = Array.isArray(doc.page_hits) ? doc.page_hits : [];
  const snippets = pageHits.map((h) => renderPageHit(h, doc)).join('');

  return (
    '<div class="result-row">' +
    '<div class="result-head">' +
    `<span class="result-part">${part}</span>` +
    (kind ? `<span class="result-kind">${kind}</span>` : '') +
    `<span class="result-meta">${meta}</span>` +
    '</div>' +
    `<div class="result-path"><a href="${href}" target="_blank" rel="noopener">${escapeHtml(path)}</a></div>` +
    (snippets ? `<div class="page-hits">${snippets}</div>` : '') +
    '</div>'
  );
}
