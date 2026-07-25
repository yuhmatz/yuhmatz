// Application shell: hash-based router + sidebar nav + server status indicator.
// Adding a new learning module means adding one entry to ROUTES and one view file.

import { renderHome } from './views/home.js';
import { renderLearningCenter } from './views/learningCenter.js';
import { renderTrainingEnv } from './views/trainingEnv.js';
import { renderReportGenerator } from './views/reportGenerator.js';
import { renderTools } from './views/tools.js';

const ROUTES = [
  { path: '#/', label: 'Overview', icon: '🏠', render: renderHome },
  { path: '#/learn', label: 'Learning Center', icon: '📚', render: renderLearningCenter },
  { path: '#/training', label: 'Training Environment', icon: '🎯', render: renderTrainingEnv },
  { path: '#/report', label: 'Report Generator', icon: '📄', render: renderReportGenerator },
  { path: '#/tools', label: 'Recon Scanner', icon: '🛠️', render: renderTools }
];

function buildNav() {
  document.getElementById('nav').innerHTML = ROUTES.map(
    (r) => `<a href="${r.path}" data-path="${r.path}"><span class="nav-ico">${r.icon}</span>${r.label}</a>`
  ).join('');
}

function router() {
  const hash = window.location.hash || '#/';
  const route = ROUTES.find((r) => r.path === hash) || ROUTES[0];

  document.querySelectorAll('.nav a').forEach((a) =>
    a.classList.toggle('active', a.dataset.path === route.path)
  );
  route.render();
}

// Poll the backend once on load so the sidebar shows whether the lab is running.
async function checkServer() {
  const wrap = document.getElementById('server-status');
  const text = document.getElementById('server-status-text');
  try {
    const res = await fetch('/api/health');
    const data = await res.json();
    wrap.classList.add('online');
    text.textContent = `lab online · ${data.boundTo}`;
  } catch {
    wrap.classList.add('offline');
    text.textContent = 'backend offline';
  }
}

buildNav();
window.addEventListener('hashchange', router);
router();
checkServer();
