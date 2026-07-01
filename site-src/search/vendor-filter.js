// Vendor dropdown initializer.
//
// - Populates the `<select id="vendorFilterIn">` from
//   `SELECT DISTINCT vendor, COUNT(*) FROM documents GROUP BY vendor`.
// - Attaches a change handler that fires the provided `onChange`
//   callback with the selected slug ('' = All vendors).
// - Restores the selection from a URL param on first load.

import { escapeHtml } from '../util/escape.js';
import { listVendorsWithCounts } from './query.js';

/**
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {HTMLSelectElement} selectEl
 * @param {(vendor: string) => void} onChange
 * @param {string} initialVendor — pre-selected value from URL state
 */
export async function initVendorFilter(query, selectEl, onChange, initialVendor = '') {
  const rows = await listVendorsWithCounts(query);
  const opts = ['<option value="">All vendors</option>'];
  const validSlugs = new Set(['']);
  for (const r of rows || []) {
    const vendor = String(r.vendor || '');
    const n = Number(r.n || 0);
    if (!vendor) continue;
    validSlugs.add(vendor);
    opts.push(
      `<option value="${escapeHtml(vendor)}">${escapeHtml(vendor)} (${n.toLocaleString()})</option>`,
    );
  }
  selectEl.innerHTML = opts.join('');

  // Restore selection from URL state ONLY if the slug is a real vendor
  // in the DB — protects against stale share links from a rebuild that
  // dropped a vendor.
  if (initialVendor && validSlugs.has(initialVendor)) {
    selectEl.value = initialVendor;
  }

  selectEl.addEventListener('change', () => {
    onChange(selectEl.value);
  });

  return {
    getVendors: () => validSlugs,
  };
}
