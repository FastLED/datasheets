// `?q=<query>&vendor=<slug>` URL state persistence — so a search link
// is shareable and re-loading the page restores the last query.
//
// Uses `history.replaceState` (no history entries for every keystroke)
// so the back button behavior stays sensible.

/**
 * Read the initial query and vendor from the current URL.
 */
export function readState() {
  const params = new URLSearchParams(location.search);
  return {
    q: params.get('q') || '',
    vendor: params.get('vendor') || '',
  };
}

/**
 * Write the current intent into the URL bar. Empty values are removed
 * so shareable links stay tidy.
 *
 * @param {{ q?: string, vendor?: string }} intent
 */
export function writeState(intent) {
  const params = new URLSearchParams(location.search);
  const q = String(intent.q || '').trim();
  const vendor = String(intent.vendor || '').trim();
  if (q) params.set('q', q); else params.delete('q');
  if (vendor) params.set('vendor', vendor); else params.delete('vendor');
  const qs = params.toString();
  const next = qs ? `${location.pathname}?${qs}` : location.pathname;
  // replaceState avoids polluting browser history with every keystroke.
  history.replaceState(null, '', next);
}
