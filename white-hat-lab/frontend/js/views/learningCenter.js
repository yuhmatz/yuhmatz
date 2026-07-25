// Learning Center view: Rules of Engagement + interactive Methodology timeline.

import { rulesOfEngagement, engagementChecklist } from '../data/rulesOfEngagement.js';
import { methodology } from '../data/methodology.js';
import { esc, mount } from '../util.js';

let activeTab = 'roe';
let activeStep = methodology[0].id;

export function renderLearningCenter() {
  mount(`
    <div class="page-head">
      <span class="eyebrow">Learning Center</span>
      <h1>Ethical Hacking, from principles to process</h1>
      <p class="sub">Start with the rules that keep testing legal and ethical, then walk
      the full penetration-testing lifecycle stage by stage.</p>
    </div>

    <div class="tabs">
      <button class="tab-btn ${activeTab === 'roe' ? 'active' : ''}" data-tab="roe">⚖️ Rules of Engagement</button>
      <button class="tab-btn ${activeTab === 'method' ? 'active' : ''}" data-tab="method">🧭 Methodology</button>
    </div>

    <div id="lc-body"></div>
  `);

  document.querySelectorAll('.tab-btn').forEach((btn) =>
    btn.addEventListener('click', () => {
      activeTab = btn.dataset.tab;
      renderLearningCenter();
    })
  );

  document.getElementById('lc-body').innerHTML =
    activeTab === 'roe' ? renderRoe() : renderMethodology();

  if (activeTab === 'method') wireMethodology();
}

function renderRoe() {
  const items = rulesOfEngagement
    .map(
      (r) => `
      <div class="roe-item">
        <div class="roe-ico">${r.icon}</div>
        <div>
          <h4>${esc(r.title)}</h4>
          <p>${esc(r.body)}</p>
        </div>
      </div>`
    )
    .join('');

  const checklist = engagementChecklist
    .map((c) => `<li>${esc(c)}</li>`)
    .join('');

  return `
    <div class="grid cols-2">
      <div class="card">
        <h3 class="mt0">Core principles</h3>
        ${items}
      </div>
      <div>
        <div class="card">
          <h3 class="mt0">Pre-engagement checklist</h3>
          <p class="muted" style="margin-top:0">Before any authorized test begins, confirm every item:</p>
          <ul style="line-height:1.9">${checklist}</ul>
        </div>
        <div class="card">
          <h3 class="mt0">The golden rule</h3>
          <div class="callout danger" style="margin:0">
            If you do not have <strong>explicit, written authorization</strong> and a
            <strong>clearly defined scope</strong>, you do not have permission to test.
            This lab is your authorized playground — everything else is off-limits.
          </div>
        </div>
      </div>
    </div>`;
}

function renderMethodology() {
  const steps = methodology
    .map(
      (s, i) => `
      <button class="method-step ${s.id === activeStep ? 'active' : ''}" data-step="${s.id}">
        <span class="num">${i + 1}</span>
        <span>${s.icon} ${esc(s.name)}</span>
      </button>`
    )
    .join('');

  return `
    <div class="method-layout">
      <div class="method-steps">${steps}</div>
      <div class="card method-detail" id="method-detail">${renderStepDetail(activeStep)}</div>
    </div>`;
}

function renderStepDetail(stepId) {
  const s = methodology.find((m) => m.id === stepId) || methodology[0];
  const idx = methodology.findIndex((m) => m.id === s.id);
  const list = (arr) => arr.map((x) => `<li>${esc(x)}</li>`).join('');
  const chips = s.tools.map((t) => `<span class="chip">${esc(t)}</span>`).join('');

  return `
    <div class="scenario-head">
      <h3 class="mt0">${s.icon} Stage ${idx + 1}: ${esc(s.name)}</h3>
    </div>
    <p class="muted">${esc(s.description)}</p>

    <div class="detail-block">
      <h5>Purpose</h5>
      <p style="margin-top:0.2rem;color:var(--text-muted)">${esc(s.purpose)}</p>
    </div>

    <div class="detail-block" style="margin-top:1rem">
      <h5>Typical tools</h5>
      <div class="chip-row">${chips}</div>
    </div>

    <div class="detail-grid">
      <div class="detail-block">
        <h5>Expected outputs</h5>
        <ul>${list(s.outputs)}</ul>
      </div>
      <div class="detail-block">
        <h5>Best practices</h5>
        <ul>${list(s.bestPractices)}</ul>
      </div>
    </div>`;
}

function wireMethodology() {
  document.querySelectorAll('.method-step').forEach((btn) =>
    btn.addEventListener('click', () => {
      activeStep = btn.dataset.step;
      document.querySelectorAll('.method-step').forEach((b) =>
        b.classList.toggle('active', b.dataset.step === activeStep)
      );
      document.getElementById('method-detail').innerHTML = renderStepDetail(activeStep);
    })
  );
}
