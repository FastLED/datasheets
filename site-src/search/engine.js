// Top-level query router.
//
// Given a classified query + the dropdown vendor filter, decide which
// specialized search runs (vendor-only fast path, scoped body search,
// part-number probe, "no-scope hint", or empty). Returns a discriminated
// result object the renderer knows how to draw.
//
// This is the ONLY module that mixes classifier output with DB access —
// keeps the routing logic in one place instead of scattered across the
// UI wiring.
//
// Ranker rules (from issue #2), in priority order:
//   1. Vendor dropdown overrides any conflicting vendor token in the
//      query text AND bypasses the broad-term guard.
//   2. If any of {vendor, part, type} is set → scoped body FTS5.
//   3. If body-only AND all body tokens are broad-term → no-scope hint.
//   4. If body-only with distinctive tokens → treat as part-number probe.
//   5. Empty query, no dropdown → intro.
//   6. Empty query WITH dropdown → vendor doc list.

import { classify } from './classify.js';
import { partNumberProbe, vendorDocList } from './query.js';
import { bodySearch } from './body.js';
import { vendorOnly } from './vendor.js';

/**
 * Result kinds:
 *   { kind: 'empty' }
 *   { kind: 'intro' }
 *   { kind: 'no-scope-hint', reason: string }
 *   { kind: 'docs', docs: Doc[], mode: 'vendor'|'part'|'scoped'|'vendor-list' }
 */

/**
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {{ q: string, vendor: string }} intent
 * @param {{ vendors: Set<string>, parts: Set<string> }} tables
 */
export async function runSearch(query, intent, tables) {
  const q = String(intent.q || '').trim();
  const dropdownVendor = String(intent.vendor || '').trim();

  // Empty query — special-cased before classification (a "     " query
  // classifies to empty too, but the intro card should show only when
  // the user hasn't typed anything).
  if (!q) {
    if (dropdownVendor) {
      const docs = await vendorDocList(query, dropdownVendor, 20);
      return { kind: 'docs', mode: 'vendor-list', docs: shapeDocs(docs) };
    }
    return { kind: 'intro' };
  }

  const cls = classify(q, tables);

  // Fully empty (stopwords / punctuation only) — no dropdown, no
  // informational tokens → empty state, not intro. The user actually
  // typed something; hint that it was all noise.
  if (cls.empty && !dropdownVendor) {
    return { kind: 'empty' };
  }

  // Dropdown overrides any vendor token from the query, and bypasses
  // the broad-term guard.
  const vendor = dropdownVendor || cls.vendor;
  const hasScope = Boolean(vendor || cls.part_prefix || cls.product_type);

  // Broad-technical-term guard — body-only, no scope from anywhere.
  if (!hasScope && cls.bodyTokens.length && cls.allBroad) {
    return {
      kind: 'no-scope-hint',
      reason: `"${cls.bodyTokens.join(' ')}" matches too many datasheets on its own. Add a vendor or part number, or pick a vendor from the dropdown.`,
    };
  }

  // Vendor-only single-token fast path (only when vendor came from the
  // query text — dropdown-only with empty query is handled above).
  if (
    cls.bodyTokens.length === 0 &&
    !cls.part_prefix &&
    !cls.product_type &&
    !dropdownVendor &&
    cls.vendor &&
    cls.rawTokens.length === 1
  ) {
    const docs = await vendorOnly(query, {
      vendor: cls.vendor,
      prefix: cls.rawTokens[0],
      limit: 20,
    });
    return { kind: 'docs', mode: 'vendor', docs: shapeDocs(docs) };
  }

  // Part-number probe — body-only distinctive token (looks like a part
  // number: alphanumeric with digits, length >= 3).
  if (!hasScope && cls.bodyTokens.length === 1) {
    const t = cls.bodyTokens[0];
    if (/\d/.test(t) && t.length >= 3) {
      const docs = await partNumberProbe(query, t, 20);
      if (docs && docs.length) {
        return { kind: 'docs', mode: 'part', docs: shapeDocs(docs) };
      }
    }
    // Non-distinctive body token with no scope → empty. (Off-corpus
    // like `xyzzy`, or a normal English word that isn't a broad term.)
    return { kind: 'empty' };
  }

  // If we have scope but no body tokens, either list vendor's docs or
  // filter by part/type via a scoped MATCH-less query.
  if (hasScope && cls.bodyTokens.length === 0) {
    if (cls.part_prefix) {
      const docs = await partNumberProbe(query, cls.part_prefix, 20);
      return { kind: 'docs', mode: 'part', docs: shapeDocs(docs) };
    }
    if (vendor) {
      const docs = await vendorDocList(query, vendor, 20);
      return { kind: 'docs', mode: 'vendor-list', docs: shapeDocs(docs) };
    }
  }

  // Scoped body FTS5 — the main case (`esp dma`, `stm32h7 sdmmc`, etc.)
  if (cls.bodyTokens.length) {
    const docs = await bodySearch(query, {
      bodyTokens: cls.bodyTokens,
      vendor,
      part_prefix: cls.part_prefix,
      product_type: cls.product_type,
    });
    return { kind: 'docs', mode: 'scoped', docs };
  }

  return { kind: 'empty' };
}

/**
 * Normalize a plain document row (no page hits) into the shape the
 * renderer expects.
 *
 * @param {Array} docs
 */
function shapeDocs(docs) {
  return (docs || []).map((d) => ({
    doc_id: d.doc_id,
    vendor: d.vendor,
    product_type: d.product_type,
    part_number: d.part_number,
    canonical_kind: d.canonical_kind,
    path: d.path,
    filename: d.filename,
    page_count: d.page_count,
    size_bytes: d.size_bytes,
    rank: d.rank ?? null,
    page_hits: d.page_hits || [],
  }));
}
