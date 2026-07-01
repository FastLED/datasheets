// A `vendor_prefix_cache`-sourced row. The cache stores top hits with
// pre-baked snippets; when present, we render the same shape as a
// normal result row but flag it with a `vendor-hit` class so the
// caller can style it (e.g. a subtle highlight).

import { renderResultRow } from './result-row.js';

/**
 * @param {object} doc
 * @param {string[]} highlightNeedles
 */
export function renderVendorRow(doc, highlightNeedles = []) {
  // Delegate to the standard row renderer; the outer `.cat.vendor-hits`
  // wrapper from the engine renderer scopes any vendor-specific styling.
  return renderResultRow(doc, highlightNeedles);
}
