(function () {
  const nav = document.querySelector('.services-cat-nav-inner');
  const sections = document.querySelectorAll('[data-category-section]');
  if (!nav || !sections.length) return;

  const links = nav.querySelectorAll('a[href^="#"]');
  const byId = {};
  links.forEach((link) => {
    const id = link.getAttribute('href').slice(1);
    if (id) byId[id] = link;
  });

  function setActive(id) {
    links.forEach((a) => a.classList.remove('is-active'));
    const active = byId[id];
    if (active) active.classList.add('is-active');
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActive(entry.target.id);
        }
      });
    },
    {
      rootMargin: '-20% 0px -55% 0px',
      threshold: 0,
    }
  );

  sections.forEach((section) => observer.observe(section));

  const hashId = window.location.hash.slice(1);
  if (hashId && byId[hashId]) {
    setActive(hashId);
  } else if (links[0]) {
    links[0].classList.add('is-active');
  }
})();
