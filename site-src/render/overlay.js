// The results panel renderer and the generic modal overlay shell.
//
// `renderResults` takes an engine result (see `search/engine.js`) and
// paints it into `#results`. It also owns the empty / intro / loading
// states so the callers stay branchless.

import { escapeHtml } from '../util/escape.js';
import { renderResultRow } from './result-row.js';

const $ = (id) => document.getElementById(id);

const RESULTS_ID = 'results';

function setOverlay(html, kind) {
  const out = $(RESULTS_ID);
  if (!out) return;
  out.className = kind ? kind : '';
  out.innerHTML = html;
  out.removeAttribute('hidden');
}

export function showLoading() {
  setOverlay(
    '<div class="spinner-row" role="status" aria-live="polite">' +
    '<span class="spinner" aria-hidden="true"></span>' +
    '<span>Searching...</span>' +
    '</div>',
    'loading',
  );
}

export function showIntro() {
  setOverlay(
    '<div class="help-card">' +
    '<h3>Search vendor datasheets</h3>' +
    '<p>Type a vendor prefix (`esp`, `nordic`, `stm32`), a part number (`esp32-s3`, `nrf52833`), or a vendor + body query (`esp dma`, `stm32h7 sdmmc`, `nordic uarte`).</p>' +
    '<p class="help-hint">Broad terms like `dma` or `spi` alone won\'t search — add a vendor or use the dropdown to scope them.</p>' +
    '<div class="help-examples" aria-label="Example searches">' +
    ['esp dma', 'stm32h7 sdmmc', 'nrf52 errata', 'ws2812b', 'rp2040 pio']
      .map((q) => `<code data-example="${escapeHtml(q)}">${escapeHtml(q)}</code>`).join('') +
    '</div>' +
    '</div>',
    'intro',
  );
  wireExampleClicks();
}

export function showEmpty(query) {
  setOverlay(
    '<div class="search-empty" role="status" aria-live="polite">' +
    `<h3>No matches for "${escapeHtml(query)}"</h3>` +
    '<p>Try a vendor slug (`espressif`, `nordic`), a part number, or a vendor + technical term (`esp dma`).</p>' +
    '</div>',
    'empty',
  );
}

export function showNoScopeHint(reason) {
  setOverlay(
    '<div class="no-scope-hint" role="status" aria-live="polite">' +
    '<h3>Add a vendor or part to your query</h3>' +
    `<p>${escapeHtml(reason)}</p>` +
    '<p>Examples: <code>esp dma</code>, <code>nordic spi</code>, <code>stm32h7 sdmmc</code>.</p>' +
    '</div>',
    'no-scope',
  );
}

export function showError(err) {
  setOverlay(
    `<div class="err">Search failed: ${escapeHtml(err && err.message || String(err))}</div>`,
    'err',
  );
}

/**
 * @param {string} query
 * @param {{ kind: string, mode?: string, docs?: any[], reason?: string }} result
 * @param {string[]} highlightNeedles
 */
export function renderResults(query, result, highlightNeedles = []) {
  if (!result) { showEmpty(query); return; }
  switch (result.kind) {
    case 'intro':         showIntro(); return;
    case 'empty':         showEmpty(query); return;
    case 'no-scope-hint': showNoScopeHint(result.reason || ''); return;
    case 'docs': {
      const docs = result.docs || [];
      if (!docs.length) { showEmpty(query); return; }
      const heading = headingFor(result.mode, docs.length);
      const rows = docs.map((d) => renderResultRow(d, highlightNeedles)).join('');
      setOverlay(
        `<div class="cat"><div class="cat-head">${heading}</div>${rows}</div>`,
        result.mode || '',
      );
      return;
    }
    default:
      showEmpty(query);
  }
}

function headingFor(mode, n) {
  const count = n.toLocaleString();
  switch (mode) {
    case 'vendor':      return `Vendor matches (${count})`;
    case 'part':        return `Part-number matches (${count})`;
    case 'vendor-list': return `Documents in vendor (${count})`;
    case 'scoped':      return `Best matches (${count})`;
    default:            return `Results (${count})`;
  }
}

function wireExampleClicks() {
  const input = document.getElementById('uniIn');
  if (!input) return;
  document.querySelectorAll('#results code[data-example]').forEach((el) => {
    el.addEventListener('click', () => {
      input.value = el.getAttribute('data-example') || '';
      input.focus();
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });
}

// --- Generic modal shell (used by pdf-preview.js) ---

/**
 * Toggle the shared modal by id. The modal element must already be in
 * the DOM (see `index.html`).
 *
 * @param {string} modalId
 * @param {boolean} open
 */
export function toggleModal(modalId, open) {
  const el = document.getElementById(modalId);
  if (!el) return;
  el.classList.toggle('open', open);
  document.body.classList.toggle('modal-open', open);
}
