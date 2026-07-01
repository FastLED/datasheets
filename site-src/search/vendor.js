// Single-token vendor fast path. Uses `vendor_prefix_cache` (a
// pre-baked table populated by `tools/build_vendor_cache.py`) for a
// single B-tree read instead of an FTS5 scan.
//
// Fallback: if the token isn't in the cache table (empty cache, or
// tests running against a raw memex build), we fall back to a direct
// `documents.vendor = ?` list.

import { vendorPrefixCacheLookup, vendorDocList } from './query.js';

/**
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {{ vendor: string, prefix: string, limit?: number }} params
 * @returns {Promise<Array>}
 */
export async function vendorOnly(query, { vendor, prefix, limit = 20 }) {
  // Fast path: cached top docs for common prefixes (`esp`, `nord`, etc.).
  const cached = await vendorPrefixCacheLookup(query, prefix);
  if (cached && Array.isArray(cached) && cached.length) {
    return cached.slice(0, limit);
  }
  // Fallback: list docs under the resolved vendor slug.
  return vendorDocList(query, vendor, limit);
}
