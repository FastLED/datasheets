// SQL query builders + memex query runner. The SQL shapes here mirror
// the ones documented in issue #2. Every string interpolation uses
// bind parameters — no interpolated user input.
//
// `query()` (the runner) is expected to be provided by memex's exports
// on the DB object — we pass it into every function so this module can
// be unit-tested with a mock runner.

/**
 * Escape a token for use inside an FTS5 MATCH string.
 *
 * FTS5 treats `-`, `:`, `"`, `(`, `)`, `*`, `AND`, `OR`, `NOT`, `NEAR`
 * as syntax. To match those literally, wrap the token in double
 * quotes. Internal double quotes get doubled.
 *
 * We ALWAYS quote body tokens — safer, and it neutralizes the case
 * where a user types `esp NOT dma` and expects a literal `NOT`
 * (Round 4 in the issue).
 *
 * @param {string} token
 */
export function ftsEscape(token) {
  const t = String(token || '');
  if (!t) return '';
  return `"${t.replace(/"/g, '""')}"`;
}

/**
 * Build the FTS5 MATCH string from body tokens. Tokens are AND'd
 * (implicit — FTS5 default when tokens are space-separated).
 *
 * @param {string[]} bodyTokens
 */
export function buildMatch(bodyTokens) {
  return bodyTokens.map(ftsEscape).filter(Boolean).join(' ');
}

/**
 * Single-token vendor-only lookup via the pre-baked cache. Returns the
 * parsed JSON payload of the `top_docs` column, or null if the prefix
 * isn't cached.
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {string} prefix
 */
export async function vendorPrefixCacheLookup(query, prefix) {
  const rows = await query(
    'SELECT top_docs FROM vendor_prefix_cache WHERE prefix = ? LIMIT 1',
    [prefix],
  );
  if (!rows || !rows.length) return null;
  try {
    return JSON.parse(rows[0].top_docs);
  } catch {
    return null;
  }
}

/**
 * Vendor + body body-scoped rank via FTS5 porter + BM25.
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {{
 *   match: string,
 *   vendor?: string | null,
 *   part_prefix?: string | null,
 *   product_type?: string | null,
 *   limit?: number,
 * }} params
 */
export async function scopedBodySearch(query, params) {
  const {
    match,
    vendor = null,
    part_prefix = null,
    product_type = null,
    limit = 60,
  } = params;

  const filters = [];
  const binds = [];
  if (match) {
    filters.push('search_porter MATCH ?');
    binds.push(match);
  }
  if (vendor) {
    filters.push('d.vendor = ?');
    binds.push(vendor);
  }
  if (part_prefix) {
    filters.push('lower(d.part_number) LIKE lower(?)');
    binds.push(part_prefix + '%');
  }
  if (product_type) {
    filters.push('d.product_type = ?');
    binds.push(product_type);
  }
  if (!filters.length) return [];

  const sql = `
    SELECT d.doc_id, d.vendor, d.product_type, d.part_number, d.canonical_kind,
           d.path, d.filename, d.page_count, d.size_bytes, d.is_lfs,
           c.page_num,
           snippet(search_porter, 0, '<mark>', '</mark>', '…', 12) AS snip,
           bm25(search_porter, 1) AS rank
    FROM search_porter
    JOIN chunks c ON c.rowid = search_porter.rowid
    JOIN documents d ON d.doc_id = c.doc_id
    WHERE ${filters.join(' AND ')}
    ORDER BY rank
    LIMIT ${Number.isFinite(limit) ? Math.floor(limit) : 60}
  `;
  return query(sql, binds);
}

/**
 * Direct part-number probe — no FTS5, cheap index scan.
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {string} partPrefix
 * @param {number} limit
 */
export async function partNumberProbe(query, partPrefix, limit = 20) {
  const sql = `
    SELECT d.doc_id, d.vendor, d.product_type, d.part_number, d.canonical_kind,
           d.path, d.filename, d.page_count, d.size_bytes, d.is_lfs
    FROM documents d
    WHERE lower(d.part_number) LIKE lower(?)
    ORDER BY d.part_number
    LIMIT ${Number.isFinite(limit) ? Math.floor(limit) : 20}
  `;
  return query(sql, [partPrefix + '%']);
}

/**
 * List documents under a vendor (used when the dropdown is set and the
 * query is empty).
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 * @param {string} vendor
 * @param {number} limit
 */
export async function vendorDocList(query, vendor, limit = 20) {
  const sql = `
    SELECT d.doc_id, d.vendor, d.product_type, d.part_number, d.canonical_kind,
           d.path, d.filename, d.page_count, d.size_bytes, d.is_lfs
    FROM documents d
    WHERE d.vendor = ?
    ORDER BY d.part_number, d.canonical_kind
    LIMIT ${Number.isFinite(limit) ? Math.floor(limit) : 20}
  `;
  return query(sql, [vendor]);
}

/**
 * Load the set of known vendor slugs and per-vendor counts (used by the
 * dropdown initializer and the classifier).
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 */
export async function listVendorsWithCounts(query) {
  return query(
    'SELECT vendor, COUNT(*) AS n FROM documents GROUP BY vendor ORDER BY vendor',
    [],
  );
}

/**
 * Load the set of known part_number values (lowercased) for classifier
 * fast-path lookups. The number of distinct part numbers is small
 * (currently in the low hundreds), so keeping them in a Set on the
 * client is cheap.
 *
 * @param {(sql: string, bind?: any[]) => Promise<any[]>} query
 */
export async function listPartNumbers(query) {
  return query('SELECT DISTINCT part_number FROM documents', []);
}
