/**
 * Services catalog search UI: navbar overlay, mobile filter drawer.
 */
(function () {
  'use strict';

  function qs(sel, root) {
    return (root || document).querySelector(sel);
  }

  function qsa(sel, root) {
    return Array.from((root || document).querySelectorAll(sel));
  }

  /* ── Navbar search overlay ── */
  function initNavSearchOverlay() {
    const overlay = document.getElementById('navSearchOverlay');
    if (!overlay) return;
    if (overlay.dataset.initialized) return;
    overlay.dataset.initialized = 'true';

    const form = qs('.nav-search-overlay-form', overlay);
    const input = qs('input[name="search"]', overlay);
    const closeBtns = qsa('[data-nav-search-close]', overlay);

    function trapFocus(e) {
      if (e.key !== 'Tab') return;
      const focusable = Array.from(overlay.querySelectorAll('button, input, a, [tabindex]:not([tabindex="-1"])'));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }

    function openOverlay() {
      overlay.hidden = false;
      document.body.classList.add('nav-search-open');
      overlay.addEventListener('keydown', trapFocus);
      if (input) {
        input.focus();
      }
    }

    function closeOverlay() {
      overlay.hidden = true;
      document.body.classList.remove('nav-search-open');
      overlay.removeEventListener('keydown', trapFocus);
    }

    qsa('.nav-search-btn, .mobile-search-item button').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        openOverlay();
      });
    });

    closeBtns.forEach(function (btn) {
      btn.addEventListener('click', closeOverlay);
    });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        closeOverlay();
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !overlay.hidden) {
        closeOverlay();
      }
    });

    if (form) {
      form.addEventListener('submit', function () {
        closeOverlay();
      });
    }
  }

  /* ── Mobile filters drawer on services pages ── */
  function initCatalogFilters() {
    qsa('[data-filters-toggle]').forEach(function (btn) {
      const panelId = btn.getAttribute('aria-controls');
      const panel = panelId ? document.getElementById(panelId) : qs('[data-filters-panel]', btn.closest('[data-catalog-toolbar]'));
      if (!panel) return;

      btn.addEventListener('click', function () {
        const expanded = btn.getAttribute('aria-expanded') === 'true';
        btn.setAttribute('aria-expanded', expanded ? 'false' : 'true');
        panel.hidden = expanded;
      });
    });
  }

  /* ── Sync browse mode on full page load from query string ── */
  function initBrowseHint() {
    const params = new URLSearchParams(window.location.search);
    if (params.get('search') || params.get('category') || params.get('sort') || params.get('page')) {
      document.body.classList.add('catalog-browse-active');
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initNavSearchOverlay();
    initCatalogFilters();
    initBrowseHint();
  });
})();
