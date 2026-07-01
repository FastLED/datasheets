// PDF preview modal — feature-flagged.
//
// Full pdfjs-dist integration is a later integration step (issue #2
// acceptance criterion). This module ships as a stub that:
//   - defines the modal open/close API
//   - falls back to a "download PDF" link when pdfjs isn't loaded
//   - is safe to import even if `pdfjs/pdf.mjs` isn't present yet
//
// The eventual full path is:
//   1. import pdfjs viewer factory from './pdfjs/pdf.mjs'
//   2. instantiate a viewer inside `.modal-body-content`
//   3. jump to `#page=<N>` when the anchor is set on the doc

import { escapeHtml } from '../util/escape.js';
import { toggleModal } from '../render/overlay.js';
import { renderDocMetadata } from './metadata.js';
import { pdfHref } from '../render/fmt.js';

const MODAL_ID = 'previewModal';
const PDFJS_ENABLED = false; // Flip when we ship pdfjs assets.

/**
 * @param {object} doc
 * @param {number | null} page
 */
export function openPdfPreview(doc, page = null) {
  const modal = document.getElementById(MODAL_ID);
  if (!modal) {
    // Modal shell isn't in the DOM (e.g. the caller opted out) —
    // fall back to opening the PDF in a new tab at the requested page.
    const href = pdfHref(doc.path || '') + (page ? `#page=${page}` : '');
    window.open(href, '_blank', 'noopener');
    return;
  }
  const title = escapeHtml(doc.part_number || doc.filename || 'Preview');
  const href = pdfHref(doc.path || '') + (page ? `#page=${page}` : '');
  const body = PDFJS_ENABLED
    ? '<div id="pdfViewer" class="modal-body-content"></div>'
    : `<div class="modal-empty">Inline preview coming soon. <a href="${href}" target="_blank" rel="noopener">Open PDF</a></div>`;

  modal.innerHTML =
    '<div class="modal-body">' +
    '<header>' +
    `<span class="title">${title}</span>` +
    `<button class="close" aria-label="Close" data-close="1">×</button>` +
    '</header>' +
    renderDocMetadata(doc) +
    body +
    '</div>';

  modal.querySelector('[data-close]')?.addEventListener('click', () => closePdfPreview());
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closePdfPreview();
  });
  toggleModal(MODAL_ID, true);
}

export function closePdfPreview() {
  toggleModal(MODAL_ID, false);
}
