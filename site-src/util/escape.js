// HTML-escape a string for safe interpolation into innerHTML.
//
// Called from every renderer that composes result rows via template
// literals — highlight markers and snippet contents go through this
// before being inserted, so `<mark>` from FTS5 snippets and user query
// text stay contained.

/**
 * @param {unknown} s
 * @returns {string}
 */
export function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c]);
}

/**
 * Escape a value for use inside an HTML attribute. Same escapes as
 * `escapeHtml` — the character set is a superset of what attribute
 * values need — kept as a separate export so calls read as
 * intent-documenting.
 *
 * @param {unknown} s
 * @returns {string}
 */
export function escapeAttr(s) {
  return escapeHtml(s);
}
