// Trailing-edge debounce with an `immediate` bypass for keystroke-driven
// searches. The datasheets search uses `scheduler.js` for the
// full "latest-only + in-flight cancel" semantics; this helper is here
// for lightweight callers (e.g. re-emitting a `resize` or a dropdown
// change without needing full scheduler machinery).

/**
 * @template {(...args: any[]) => void} F
 * @param {F} fn
 * @param {number} waitMs
 * @returns {(...args: Parameters<F>) => void}
 */
export function debounce(fn, waitMs = 120) {
  let timer = null;
  return function debounced(...args) {
    if (timer != null) clearTimeout(timer);
    timer = setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, waitMs);
  };
}
