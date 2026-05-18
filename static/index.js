  // Wishlist toggle
  document.querySelectorAll('.wishlist-btn').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      const icon = btn.querySelector('i');
      if (!icon) return;
      icon.classList.toggle('fa-regular');
      icon.classList.toggle('fa-solid');
    });
  });

  // Booking callout now links directly to booking.html

  // Account dropdown
  const navAccount = document.getElementById('navAccount');
  const navAccountBtn = document.getElementById('navAccountBtn');
  if (navAccount && navAccountBtn) {
    navAccountBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      const open = navAccount.classList.toggle('open');
      navAccountBtn.setAttribute('aria-expanded', open);
      document.getElementById('navAccountDropdown').setAttribute('aria-hidden', !open);
    });
    document.addEventListener('click', (e) => {
      if (!navAccount.contains(e.target)) {
        navAccount.classList.remove('open');
        navAccountBtn.setAttribute('aria-expanded', 'false');
        document.getElementById('navAccountDropdown').setAttribute('aria-hidden', 'true');
      }
    });
  }

  // Hamburger menu
  const hamburger = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobileMenu');
  if (hamburger && mobileMenu) {
    hamburger.addEventListener('click', () => {
      mobileMenu.classList.toggle('open');
      const icon = hamburger.querySelector('i');
      if (!icon) return;
      icon.classList.toggle('fa-bars');
      icon.classList.toggle('fa-xmark');
    });
  }

  // Testimonials carousel
  const testimonialsRoot = document.querySelector('[data-testimonials-carousel]');
  const testimonialsViewport = document.querySelector('[data-testimonials-viewport]');
  if (testimonialsRoot && testimonialsViewport) {
    const prevBtn = testimonialsRoot.querySelector('[data-testimonials-prev]');
    const nextBtn = testimonialsRoot.querySelector('[data-testimonials-next]');
    const dots = testimonialsRoot.querySelectorAll('[data-testimonials-dot]');

    function slideWidth() {
      return testimonialsViewport.clientWidth;
    }

    function activeIndex() {
      const w = slideWidth();
      if (!w) return 0;
      return Math.min(dots.length - 1, Math.max(0, Math.round(testimonialsViewport.scrollLeft / w)));
    }

    function syncDots() {
      const i = activeIndex();
      dots.forEach((dot, idx) => {
        const on = idx === i;
        dot.classList.toggle('is-active', on);
        dot.setAttribute('aria-selected', on ? 'true' : 'false');
      });
    }

    function goToIndex(index) {
      const w = slideWidth();
      testimonialsViewport.scrollTo({ left: index * w, behavior: 'smooth' });
    }

    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        const i = activeIndex();
        goToIndex(Math.max(0, i - 1));
      });
    }

    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        const i = activeIndex();
        goToIndex(Math.min(dots.length - 1, i + 1));
      });
    }

    dots.forEach((dot, idx) => {
      dot.addEventListener('click', () => goToIndex(idx));
    });

    testimonialsViewport.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        if (e.key === 'ArrowLeft' && prevBtn) prevBtn.click();
        if (e.key === 'ArrowRight' && nextBtn) nextBtn.click();
      }
    });

    let scrollTick = null;
    testimonialsViewport.addEventListener('scroll', () => {
      if (scrollTick) cancelAnimationFrame(scrollTick);
      scrollTick = requestAnimationFrame(syncDots);
    });

    window.addEventListener('resize', syncDots);
    syncDots();
  }
