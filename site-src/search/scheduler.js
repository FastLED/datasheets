// Latest-only search scheduler with debounce + in-flight guard.
//
// Same pattern as FastLED/boards' `createLatestOnlySearchScheduler` —
// pared down for the datasheets use case (one search callable, one
// intent shape).
//
// Intent shape here: `{ q: string, vendor: string }` where `vendor`
// is the dropdown value ('' = All vendors).

/**
 * @param {{ q?: string, vendor?: string }} intent
 */
export function normalizeSearchIntent(intent = {}) {
  return {
    q: String(intent.q || '').trim(),
    vendor: String(intent.vendor || ''),
  };
}

/**
 * @param {ReturnType<typeof normalizeSearchIntent>} a
 * @param {ReturnType<typeof normalizeSearchIntent>} b
 */
export function sameSearchIntent(a, b) {
  if (!a || !b) return false;
  return a.q === b.q && a.vendor === b.vendor;
}

/**
 * Create a scheduler that:
 *   - debounces keystrokes by `debounceMs`
 *   - drops stale requests (only the most recent intent renders)
 *   - runs one search at a time; queues the next-latest
 *
 * @param {{
 *   run: (intent: object, shouldRender: () => boolean) => Promise<void>,
 *   debounceMs?: number,
 *   onQueued?: (intent: object) => void,
 *   onError?: (err: unknown) => void,
 * }} opts
 */
export function createLatestOnlySearchScheduler({
  run,
  debounceMs = 120,
  onQueued = () => {},
  onError = (err) => console.error(err),
} = {}) {
  if (typeof run !== 'function') {
    throw new TypeError('search scheduler requires a run(intent, shouldRender) function');
  }

  let latest = null;
  let active = null;
  let queued = null;
  let timer = null;

  function shouldRender(intent) {
    return sameSearchIntent(intent, latest);
  }

  async function start(intent) {
    active = intent;
    queued = null;
    try {
      await run(intent, () => shouldRender(intent));
    } catch (err) {
      if (shouldRender(intent)) onError(err);
    } finally {
      active = null;
      const next = queued;
      queued = null;
      if (next && !sameSearchIntent(next, intent)) request(next);
    }
  }

  function schedule(intent, delayMs) {
    timer = setTimeout(() => {
      timer = null;
      start(intent);
    }, delayMs);
  }

  function request(intent, { immediate = false } = {}) {
    const next = normalizeSearchIntent(intent);
    if ((active || timer) && sameSearchIntent(next, latest)) return;
    latest = next;
    if (timer != null) {
      clearTimeout(timer);
      timer = null;
    }
    if (active) {
      queued = sameSearchIntent(next, active) ? null : next;
      onQueued(next);
      return;
    }
    schedule(next, immediate ? 0 : debounceMs);
  }

  return {
    request,
    getState() {
      return { latest, active, queued, scheduled: timer != null };
    },
  };
}
