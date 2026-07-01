// A single per-page snippet under a result row. Renders the page
// number as a link that jumps to the modal viewer at the right page.

import { escapeHtml } from '../util/escape.js';
import { safeSnippet } from './match.js';
import { pdfHref } from './fmt.js';

/**
 * @param {{ page_num: number, snippet: string }} hit
 * @param {{ path: string, doc_id: number }} doc
 */
export function renderPageHit(hit, doc) {
  const page = Number(hit.page_num || 0);
  const anchor = page ? `#page=${page}` : '';
  const href = `${pdfHref(doc.path)}${anchor}`;
  return (
    '<div class="page-hit">' +
    `<span class="page-hit-num"><a href="${href}" target="_blank" rel="noopener">p.${escapeHtml(page)}</a></span>` +
    `<span class="page-hit-snippet">${safeSnippet(hit.snippet)}</span>` +
    '</div>'
  );
}
