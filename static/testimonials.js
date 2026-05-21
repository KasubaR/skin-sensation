(function () {
  const starInput = document.querySelector('[data-star-input]');
  if (!starInput) return;

  const radios = starInput.querySelectorAll('input[type="radio"]');
  const labels = starInput.querySelectorAll('.testimonials-star-label');

  function highlightUpTo(value) {
    labels.forEach((label) => {
      const input = label.querySelector('input');
      if (!input) return;
      label.classList.toggle('is-active', parseInt(input.value, 10) <= value);
    });
  }

  labels.forEach((label) => {
    const input = label.querySelector('input');
    if (!input) return;

    label.addEventListener('mouseenter', () => {
      highlightUpTo(parseInt(input.value, 10));
    });

    label.addEventListener('click', () => {
      highlightUpTo(parseInt(input.value, 10));
    });
  });

  starInput.addEventListener('mouseleave', () => {
    const checked = starInput.querySelector('input[type="radio"]:checked');
    highlightUpTo(checked ? parseInt(checked.value, 10) : 0);
  });

  const checked = starInput.querySelector('input[type="radio"]:checked');
  if (checked) {
    highlightUpTo(parseInt(checked.value, 10));
  }
})();
