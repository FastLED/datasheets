// Query-time token classifier. Splits a raw query string into
// {vendor, part, type, body} groups per the rules in issue #2.
//
// The classifier is *pure* — it takes the token list plus the set of
// known vendors and part-number prefixes (fetched once at page load),
// and returns a structured `Classification` object. No DB access.
//
// Rule ordering per token (single pass):
//   1. Stopword filter
//   2. Vendor exact/alias match
//   3. Part-number prefix match
//   4. Product-type match
//   5. Otherwise → body token
//
// Broad-term guard is evaluated by `engine.js`, not here; this module
// only reports whether the classified body tokens are ALL on the
// broad-term list so the caller can decide.

export const STOPWORDS = new Set([
  'the', 'a', 'an', 'and', 'or', 'of', 'for', 'with', 'to',
  'in', 'on', 'is', 'it', 'by',
]);

// Aliases that map user shorthand to the canonical vendor slug used
// in `documents.vendor`. Exact hits on a real vendor slug win over
// the alias table (the check order in classifyToken respects that).
export const VENDOR_ALIASES = new Map([
  ['esp', 'espressif'],
  ['st', 'stmicroelectronics'],
  ['stm32', 'stmicroelectronics'],
  ['pico', 'raspberrypi'],
  ['rpi', 'raspberrypi'],
  ['atmel', 'microchip'],
  ['teensy', 'pjrc'],
  ['kinetis', 'nxp'],
]);

// Some aliases also carry a part-number filter (`kinetis` → NXP AND
// part_number LIKE 'MK%'). Attached here so engine.js can apply it
// without a second lookup table.
export const VENDOR_ALIAS_PART_HINT = new Map([
  ['kinetis', 'MK'],
  ['stm32',   'STM32'],
]);

export const PRODUCT_TYPES = new Set([
  'soc', 'mcu', 'addressable-led', 'led-driver', 'board', 'power',
]);

// Broad body-terms — extremely common in embedded-silicon documents.
// When a body query is composed of ONLY these tokens (no vendor / part
// scope), the classifier short-circuits to a "add a vendor or part"
// no-scope hint rather than running FTS5. Otherwise a query like
// `register` would touch tens of thousands of chunks across the corpus.
//
// Terms flagged after real-usage benchmarking (`tests/test_query_perf.py`)
// — anything whose FTS5 posting list exceeds ~5000 rows without a vendor
// filter should go here.
export const BROAD_TERMS = new Set([
  // Peripherals / protocols
  'dma', 'spi', 'i2c', 'uart', 'usb', 'pwm', 'adc', 'dac',
  'i2s', 'can', 'lin', 'mmc', 'sdmmc', 'ethernet', 'sdio',
  // Generic silicon vocabulary
  'interrupt', 'timer', 'clock', 'gpio', 'dhcp', 'flash',
  'rom', 'ram', 'register', 'registers', 'bit', 'bits',
  'byte', 'bytes', 'word', 'address', 'addr',
  'read', 'write', 'reserved', 'default', 'value',
  'enable', 'disable', 'reset', 'mode', 'status',
  'input', 'output', 'signal', 'pin', 'pins', 'port',
  'ports', 'set', 'clear', 'field', 'fields',
  'chapter', 'section', 'figure', 'table',
]);

// Canonical-kind hints — not required by the spec but useful for the
// `esp32 errata` case where a body word alone can flag intent.
export const CANONICAL_KIND_HINTS = new Set([
  'datasheet', 'errata', 'user-manual', 'reference-manual',
  'technical-reference-manual', 'schematic', 'pinout', 'product-brief',
]);

/**
 * Normalize a raw query — lowercase, collapse whitespace, treat
 * `:` `-` and dots as separators for tokenization ONLY (we keep the
 * original token as well so `esp32-s3` stays a single "part-number
 * candidate" token before it gets classified).
 *
 * Punctuation-only queries produce an empty token list.
 *
 * @param {string} query
 * @returns {string[]}
 */
export function tokenize(query) {
  const raw = String(query || '').toLowerCase().trim();
  if (!raw) return [];
  // Split only on whitespace so `esp32-s3` survives as one token.
  const rough = raw.split(/\s+/).filter(Boolean);
  // Filter anything that has no alphanumeric characters at all (`!!@#%`).
  return rough.filter((t) => /[a-z0-9]/.test(t));
}

/**
 * Strip separators from a token so `esp32-s3`, `esp32_s3`, and
 * `esp32:s3` all normalize to `esp32s3` for a second-pass
 * part-number lookup. Callers keep the original alongside.
 *
 * @param {string} token
 */
export function stripSeps(token) {
  return String(token || '').replace(/[\s:._\-]+/g, '');
}

/**
 * Classify a single token against the known-vendor and known-part sets.
 * Returns the token role plus the canonical value that should be used
 * downstream (e.g. `esp` → `espressif`).
 *
 * @param {string} token
 * @param {{vendors: Set<string>, parts: Set<string>}} tables
 */
export function classifyToken(token, tables) {
  const t = token.toLowerCase();
  if (!t) return null;

  if (STOPWORDS.has(t)) return { role: 'stopword', token: t };

  // Exact vendor slug wins over aliases.
  if (tables.vendors.has(t)) {
    return { role: 'vendor', token: t, vendor: t };
  }
  if (VENDOR_ALIASES.has(t)) {
    const vendor = VENDOR_ALIASES.get(t);
    const partHint = VENDOR_ALIAS_PART_HINT.get(t) || null;
    return { role: 'vendor', token: t, vendor, partHint };
  }

  // Product type is a small fixed set — check before part-number so
  // `board` doesn't accidentally match a part number that happens to
  // start with `board`.
  if (PRODUCT_TYPES.has(t)) {
    return { role: 'product_type', token: t, product_type: t };
  }

  // Part-number probe. We look at both the raw lowercase token AND its
  // separator-stripped variant so `esp32-s3` and `esp32s3` both hit.
  const stripped = stripSeps(t);
  if (tables.parts.has(t)) {
    return { role: 'part', token: t, part_prefix: t };
  }
  if (stripped && stripped !== t && tables.parts.has(stripped)) {
    return { role: 'part', token: t, part_prefix: stripped };
  }
  // Prefix hit (any known part number starts with the token). Cheap
  // set-membership isn't enough — we walk the set once. The set has a
  // few hundred entries at most, so this is fine at query time.
  for (const p of tables.parts) {
    if (p.startsWith(t) || (stripped && p.startsWith(stripped))) {
      return { role: 'part', token: t, part_prefix: stripped || t };
    }
  }

  return { role: 'body', token: t };
}

/**
 * Full classification of the query string.
 *
 * Result shape:
 *   {
 *     vendor:      string | null   // canonical slug or null
 *     vendorFrom:  'token' | null  // 'token' means it came from the query
 *     part_prefix: string | null   // lowercase, separators stripped
 *     product_type: string | null
 *     bodyTokens:  string[]        // remaining tokens for FTS5 MATCH
 *     droppedStopwords: string[]
 *     rawTokens:   string[]
 *     allBroad:    boolean         // true if bodyTokens are ALL broad terms
 *     empty:       boolean         // true if no informational tokens remain
 *   }
 *
 * @param {string} query
 * @param {{vendors: Set<string>, parts: Set<string>}} tables
 */
export function classify(query, tables) {
  const rawTokens = tokenize(query);
  const droppedStopwords = [];
  let vendor = null;
  let vendorFrom = null;
  let partPrefix = null;
  let productType = null;
  const bodyTokens = [];

  for (const t of rawTokens) {
    const cls = classifyToken(t, tables);
    if (!cls) continue;
    switch (cls.role) {
      case 'stopword':
        droppedStopwords.push(cls.token);
        break;
      case 'vendor':
        if (!vendor) {
          vendor = cls.vendor;
          vendorFrom = 'token';
          if (cls.partHint && !partPrefix) partPrefix = cls.partHint.toLowerCase();
        }
        break;
      case 'part':
        if (!partPrefix) partPrefix = cls.part_prefix;
        break;
      case 'product_type':
        if (!productType) productType = cls.product_type;
        break;
      case 'body':
      default:
        bodyTokens.push(cls.token);
        break;
    }
  }

  const allBroad = bodyTokens.length > 0 && bodyTokens.every((t) => BROAD_TERMS.has(t));
  const empty = !vendor && !partPrefix && !productType && bodyTokens.length === 0;

  return {
    vendor,
    vendorFrom,
    part_prefix: partPrefix,
    product_type: productType,
    bodyTokens,
    droppedStopwords,
    rawTokens,
    allBroad,
    empty,
  };
}
