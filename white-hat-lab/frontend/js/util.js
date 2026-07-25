// Tiny DOM & formatting helpers. Keeping these in one place avoids a build step
// while still giving the views a clean, declarative way to render.

/** Escape a string for safe insertion into HTML (used by OUR trusted UI). */
export function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/** Create an element from an HTML string. */
export function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

/** Convenience: set the main view's HTML. */
export function mount(html) {
  const view = document.getElementById('view');
  view.innerHTML = html;
  view.scrollTop = 0;
  window.scrollTo(0, 0);
  return view;
}

/** Pretty-print JSON for the result panels. */
export function pretty(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

/** Map a severity word to a CSS badge class. */
export function severityClass(sev = '') {
  const s = sev.toLowerCase();
  if (s.startsWith('crit')) return 'crit';
  if (s.startsWith('high')) return 'high';
  if (s.startsWith('med')) return 'med';
  return 'low';
}
