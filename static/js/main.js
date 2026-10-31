// Mobile menu
document.getElementById('menuBtn').addEventListener('click', () =>
  document.getElementById('mainNav').classList.toggle('open'));

// Scroll reveal
const io = new IntersectionObserver(entries => entries.forEach(e => {
  if (e.isIntersecting) { e.target.classList.add('show'); io.unobserve(e.target); }
}), { threshold: 0.15 });
document.querySelectorAll('.reveal').forEach(el => io.observe(el));

// Animated counters
const counterIO = new IntersectionObserver(entries => entries.forEach(e => {
  if (!e.isIntersecting) return;
  const el = e.target, target = +el.dataset.target; let n = 0;
  const step = Math.max(1, Math.ceil(target / 60));
  const t = setInterval(() => { n = Math.min(n + step, target); el.textContent = n; if (n >= target) clearInterval(t); }, 25);
  counterIO.unobserve(el);
}), { threshold: 0.5 });
document.querySelectorAll('.counter').forEach(el => counterIO.observe(el));
