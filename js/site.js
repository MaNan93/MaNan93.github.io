(function () {
  var button = document.querySelector('[data-theme-toggle]');
  var stored = localStorage.getItem('preferredTheme');
  var dark = stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches);

  function apply(value) {
    document.body.classList.toggle('darkmode', value);
    if (button) button.textContent = value ? '☀️' : '🌙';
    document.documentElement.style.colorScheme = value ? 'dark' : 'light';
  }

  apply(dark);
  if (button) {
    button.addEventListener('click', function () {
      dark = !document.body.classList.contains('darkmode');
      localStorage.setItem('preferredTheme', dark ? 'dark' : 'light');
      apply(dark);
    });
  }
}());
