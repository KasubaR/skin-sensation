/* Gallery — filter + lightbox */
(function () {
  'use strict';

  const grid      = document.getElementById('galleryGrid');
  const emptyMsg  = document.getElementById('galleryEmpty');
  const lightbox  = document.getElementById('galleryLightbox');
  const lbImg     = document.getElementById('galleryLbImg');
  const lbCaption = document.getElementById('galleryLbCaption');
  const lbClose   = document.getElementById('galleryLbClose');
  const lbPrev    = document.getElementById('galleryLbPrev');
  const lbNext    = document.getElementById('galleryLbNext');

  if (!grid) return;

  const allItems = Array.from(grid.querySelectorAll('.gallery-item'));
  let visibleItems = allItems.slice();
  let currentIndex = 0;

  /* ── FILTER ── */
  const filterBtns = document.querySelectorAll('.gallery-filter-btn');

  filterBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      filterBtns.forEach(b => { b.classList.remove('is-active'); b.setAttribute('aria-selected', 'false'); });
      btn.classList.add('is-active');
      btn.setAttribute('aria-selected', 'true');

      const filter = btn.dataset.filter;
      visibleItems = [];

      allItems.forEach(item => {
        const match = filter === 'all' || item.dataset.category === filter;
        item.classList.toggle('is-hidden', !match);
        if (match) visibleItems.push(item);
      });

      emptyMsg.hidden = visibleItems.length > 0;
    });
  });

  /* ── LIGHTBOX ── */
  function openLightbox(index) {
    currentIndex = index;
    showImage(currentIndex);
    lightbox.hidden = false;
    document.body.style.overflow = 'hidden';
    lbClose.focus();
  }

  function closeLightbox() {
    lightbox.hidden = true;
    document.body.style.overflow = '';
    if (visibleItems[currentIndex]) visibleItems[currentIndex].focus();
  }

  function showImage(index) {
    const item = visibleItems[index];
    if (!item) return;

    // Trigger re-animation
    lbImg.style.animation = 'none';
    lbImg.offsetHeight; // reflow
    lbImg.style.animation = '';

    lbImg.src = item.dataset.src || item.querySelector('img').src;
    lbImg.alt = item.querySelector('img').alt || '';
    lbCaption.textContent = item.dataset.caption || '';

    lbPrev.disabled = index === 0;
    lbNext.disabled = index === visibleItems.length - 1;
  }

  function prev() {
    if (currentIndex > 0) { currentIndex--; showImage(currentIndex); }
  }

  function next() {
    if (currentIndex < visibleItems.length - 1) { currentIndex++; showImage(currentIndex); }
  }

  // Open on click / Enter / Space
  allItems.forEach((item, i) => {
    function open() {
      const idx = visibleItems.indexOf(item);
      if (idx !== -1) openLightbox(idx);
    }
    item.addEventListener('click', open);
    item.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); }
    });
  });

  lbClose.addEventListener('click', closeLightbox);
  lbPrev.addEventListener('click', prev);
  lbNext.addEventListener('click', next);

  // Backdrop click
  lightbox.addEventListener('click', e => {
    if (e.target === lightbox) closeLightbox();
  });

  // Keyboard nav
  document.addEventListener('keydown', e => {
    if (lightbox.hidden) return;
    if (e.key === 'Escape')      closeLightbox();
    if (e.key === 'ArrowLeft')   prev();
    if (e.key === 'ArrowRight')  next();
  });
})();
