(() => {
  const header = document.querySelector('.home-page .navbar');
  const updateHeader = () => header?.classList.toggle('is-scrolled', window.scrollY > 18);
  updateHeader();
  window.addEventListener('scroll', updateHeader, {passive:true});
  const items = document.querySelectorAll('[data-reveal]');
  if (!('IntersectionObserver' in window) || !items.length || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      observer.unobserve(entry.target);
    });
  }, {threshold:0.12, rootMargin:'0px 0px -35px 0px'});
  document.documentElement.classList.add('reveal-ready');
  items.forEach(item => observer.observe(item));
})();
