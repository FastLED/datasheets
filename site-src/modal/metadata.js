// Per-document metadata card. Shown in the modal header above the
// PDF viewer. Data comes from `documents` — every field is already on
// the doc row we render, so no extra DB round-trip here.

import { escapeHtml } from '../util/escape.js';
import { fmtBytes, fmtPages } from '../render/fmt.js';

/**
 * @param {{
 *   part_number: string, canonical_kind: string, vendor: string,
 *   product_type: string, sha256?: string, size_bytes?: number,
 *   page_count?: number, path: string, filename?: string,
 * }} doc
 */
export function renderDocMetadata(doc) {
  const bits = [];
  if (doc.vendor) bits.push(`<span>vendor: ${escapeHtml(doc.vendor)}</span>`);
  if (doc.product_type) bits.push(`<span>type: ${escapeHtml(doc.product_type)}</span>`);
  if (doc.canonical_kind) bits.push(`<span>kind: ${escapeHtml(doc.canonical_kind)}</span>`);
  if (doc.page_count) bits.push(`<span>${escapeHtml(fmtPages(doc.page_count))}</span>`);
  if (doc.size_bytes) bits.push(`<span>${escapeHtml(fmtBytes(doc.size_bytes))}</span>`);
  if (doc.sha256) bits.push(`<span>sha256: ${escapeHtml(String(doc.sha256).slice(0, 12))}…</span>`);
  return `<div class="modal-meta">${bits.join('')}</div>`;
}
