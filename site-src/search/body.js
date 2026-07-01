// Scoped porter FTS5 body search — the common case for `esp dma`,
// `nordic uarte`, etc. Returns a list of already-grouped documents
// with page-hit snippets ready for rendering.

import { scopedBodySearch, buildMatch } from './query.js';

const MAX_DOCS = 20;
const MAX_PAGES_PER_DOC = 3;

/**
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {{
 *   bodyTokens: string[],
 *   vendor?: string | null,
 *   part_prefix?: string | null,
 *   product_type?: string | null,
 *   maxDocs?: number,
 *   maxPagesPerDoc?: number,
 * }} params
 * @returns {Promise<Array>}
 */
export async function bodySearch(query, params) {
  const {
    bodyTokens,
    vendor = null,
    part_prefix = null,
    product_type = null,
    maxDocs = MAX_DOCS,
    maxPagesPerDoc = MAX_PAGES_PER_DOC,
  } = params;

  const match = buildMatch(bodyTokens);
  const rows = await scopedBodySearch(query, {
    match,
    vendor,
    part_prefix,
    product_type,
    limit: 60,
  });

  return groupRows(rows, { maxDocs, maxPagesPerDoc });
}

/**
 * Collapse per-page FTS5 rows into per-document groups.
 *
 * Rows come in already sorted by BM25 rank. We iterate in order and
 * push each new document as we see it; the first page per document
 * defines the document rank.
 *
 * @param {Array} rows
 * @param {{ maxDocs: number, maxPagesPerDoc: number }} opts
 */
export function groupRows(rows, { maxDocs, maxPagesPerDoc }) {
  const byDoc = new Map();
  const order = [];
  for (const r of rows || []) {
    const key = r.doc_id;
    if (!byDoc.has(key)) {
      byDoc.set(key, {
        doc_id: r.doc_id,
        vendor: r.vendor,
        product_type: r.product_type,
        part_number: r.part_number,
        canonical_kind: r.canonical_kind,
        path: r.path,
        filename: r.filename,
        page_count: r.page_count,
        size_bytes: r.size_bytes,
        rank: r.rank,
        page_hits: [],
      });
      order.push(key);
    }
    const doc = byDoc.get(key);
    if (doc.page_hits.length < maxPagesPerDoc) {
      doc.page_hits.push({
        page_num: r.page_num,
        snippet: r.snip,
      });
    }
  }
  return order.slice(0, maxDocs).map((k) => byDoc.get(k));
}
