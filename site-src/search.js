// Entry point. Called from `index.html` after `openMemexDb()`
// resolves. Wires the DOM, boots the vendor filter, and installs the
// scheduler that runs on every keystroke.
//
// Design constraint: this module must not import memex directly. The
// `db` handle is passed in; that keeps the module testable with a
// stubbed `query()` function and keeps the memex asset boundary
// visible only in the HTML shell.

import { listVendorsWithCounts, listPartNumbers } from './search/query.js';
import { runSearch } from './search/engine.js';
import { initVendorFilter } from './search/vendor-filter.js';
import { readState, writeState } from './search/url-state.js';
import { createLatestOnlySearchScheduler } from './search/scheduler.js';
import {
  renderResults, showLoading, showIntro, showError,
} from './render/overlay.js';
import { configurePdfRoots } from './render/fmt.js';

const $ = (id) => document.getElementById(id);

/**
 * @param {{ query: (sql: string, bind?: any[]) => Promise<any[]> }} db
 *   Object returned by `openMemexDb()`. We only use `db.query`, so
 *   any compatible wrapper works.
 */
export async function installSearch(db) {
  const query = db.query.bind(db);

  const status = $('dbStatus');
  const setStatus = (text, cls = '') => {
    if (!status) return;
    status.textContent = text;
    status.className = cls;
  };

  // Load `_meta.json` for the PDF root templates. The frontend's link
  // template picks between `pdf_root` (inline / shipped) and
  // `pdf_root_lfs` (external raw host, e.g. raw.githubusercontent.com
  // for public repos) per-document based on the `is_lfs` bool the
  // build writes into each `documents` row.
  //
  // Failing this fetch is non-fatal — pdfHref falls back to `pdf/`.
  try {
    const meta = await fetch('_meta.json', { cache: 'no-cache' }).then((r) => r.ok ? r.json() : null);
    if (meta) {
      configurePdfRoots({
        pdf_root: meta.pdf_root,
        pdf_root_lfs: meta.pdf_root_lfs,
      });
    }
  } catch { /* keep defaults */ }

  setStatus('schema: loading vendor / part-number tables…');

  // Load the two small in-memory tables used by the classifier + the
  // dropdown. Both are ~hundreds of rows — one B-tree scan each.
  let vendorRows = [];
  let partRows = [];
  try {
    [vendorRows, partRows] = await Promise.all([
      listVendorsWithCounts(query),
      listPartNumbers(query),
    ]);
  } catch (err) {
    setStatus(`schema failed: ${err && err.message || err}`, 'err');
    showError(err);
    return;
  }

  const vendors = new Set((vendorRows || []).map((r) => String(r.vendor || '').toLowerCase()));
  const parts = new Set(
    (partRows || [])
      .map((r) => String(r.part_number || '').toLowerCase())
      .filter(Boolean),
  );

  // URL state: initial query and vendor from the URL bar.
  const initial = readState();

  // Wire vendor dropdown. Fires an intent update when the user
  // switches vendors (broad-term guard is bypassed while a vendor is
  // pinned — see engine.js).
  const vendorFilter = $('vendorFilterIn');
  if (vendorFilter) {
    await initVendorFilter(query, vendorFilter, () => {
      scheduler.request(currentIntent(), { immediate: true });
    }, initial.vendor);
  }

  // Restore the query text if provided in the URL.
  const uni = $('uniIn');
  if (uni && initial.q) uni.value = initial.q;

  // Scheduler wraps the actual `runSearch` call so keystrokes debounce
  // and stale requests get dropped.
  const scheduler = createLatestOnlySearchScheduler({
    debounceMs: 130,
    run: async (intent, shouldRender) => {
      // Show the spinner only for scoped body searches — vendor-only /
      // part-probe queries typically resolve in a few ms and the
      // flicker is worse than the wait.
      const needsSpinner = intent.q.split(/\s+/).filter(Boolean).length > 1;
      if (needsSpinner) showLoading();

      const result = await runSearch(query, intent, { vendors, parts });
      if (!shouldRender()) return;

      const needles = [
        ...intent.q.split(/\s+/).filter((t) => t.length >= 2),
        intent.vendor,
      ].filter(Boolean);
      renderResults(intent.q, result, needles);
      writeState(intent);
    },
    onError: (err) => {
      showError(err);
      setStatus(`search error: ${err && err.message || err}`, 'err');
    },
  });

  setStatus('ready', 'ok');

  function currentIntent() {
    return {
      q: uni ? uni.value : '',
      vendor: vendorFilter ? vendorFilter.value : '',
    };
  }

  if (uni) {
    uni.addEventListener('input', () => scheduler.request(currentIntent()));
    // Esc clears; Enter fires immediate.
    uni.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        uni.value = '';
        scheduler.request(currentIntent(), { immediate: true });
      } else if (e.key === 'Enter') {
        scheduler.request(currentIntent(), { immediate: true });
      }
    });
    uni.focus();
  }

  // First render.
  if (initial.q || initial.vendor) {
    scheduler.request(currentIntent(), { immediate: true });
  } else {
    showIntro();
  }
}
