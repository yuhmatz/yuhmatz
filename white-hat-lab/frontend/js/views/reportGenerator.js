// Report Generator view: a structured finding form with a live preview and
// one-click Markdown / PDF export (both produced by the backend).

import { esc, mount } from '../util.js';

// Fields mirror the backend's normalizeFinding(). Order here drives the form.
const FIELDS = [
  { key: 'title', label: 'Vulnerability Title', type: 'text', ph: 'SQL Injection in login endpoint' },
  { key: 'reporter', label: 'Prepared by', type: 'text', ph: 'Your name' },
  { key: 'category', label: 'Vulnerability Category', type: 'select',
    options: ['Injection', 'Broken Access Control', 'Cross-Site Scripting (XSS)',
      'Security Misconfiguration', 'Sensitive Data Exposure', 'Authentication', 'Other'] },
  { key: 'severity', label: 'Severity', type: 'select',
    options: ['Critical', 'High', 'Medium', 'Low', 'Informational'] },
  { key: 'cvssScore', label: 'CVSS Base Score (0–10)', type: 'number', ph: '9.8', min: 0, max: 10, step: 0.1 },
  { key: 'affectedComponent', label: 'Affected Component', type: 'text', ph: 'POST /api/vuln/login' },
  { key: 'description', label: 'Description', type: 'textarea', ph: 'What the vulnerability is and why it exists.' },
  { key: 'stepsToReproduce', label: 'Steps to Reproduce', type: 'textarea',
    ph: '1. Navigate to the login form\n2. Enter the payload...\n3. Observe authentication bypass' },
  { key: 'proofOfConcept', label: 'Proof of Concept', type: 'textarea', ph: "username: admin'--  password: anything" },
  { key: 'riskAssessment', label: 'Risk Assessment', type: 'textarea', ph: 'Business impact if exploited.' },
  { key: 'remediation', label: 'Remediation Recommendations', type: 'textarea', ph: 'Use parameterized queries...' }
];

// A ready-made example so students can see a complete report immediately.
const EXAMPLE = {
  title: 'SQL Injection — Authentication Bypass in Login',
  reporter: 'Security Researcher',
  category: 'Injection',
  severity: 'Critical',
  cvssScore: '9.8',
  affectedComponent: 'POST /api/vuln/login',
  description:
    'The login endpoint builds its SQL query by concatenating the username and password directly into the statement. Untrusted input is therefore interpreted as SQL code, allowing an attacker to alter the query logic and bypass authentication entirely.',
  stepsToReproduce:
    "1. Navigate to the Training Environment > SQL Injection scenario.\n2. In the username field enter:  admin'--\n3. Enter any value for the password.\n4. Submit. The query becomes: SELECT ... WHERE username = 'admin'--' AND password = '...'\n5. The -- comments out the password check and you authenticate as admin.",
  proofOfConcept: "Username: admin'--\nPassword: anything\nResult: { success: true, user: { username: 'admin', role: 'administrator' } }",
  riskAssessment:
    'An unauthenticated attacker can bypass login and access any account, including administrators, leading to full data disclosure and potential total compromise of the application and its data.',
  remediation:
    'Use parameterized queries / prepared statements so user input is always treated as data, never executable SQL. Apply least-privilege database accounts, add input validation, and return generic authentication errors that do not leak SQL details.'
};

const state = Object.fromEntries(FIELDS.map((f) => [f.key, '']));

export function renderReportGenerator() {
  mount(`
    <div class="page-head">
      <span class="eyebrow">Report Generator</span>
      <h1>Turn a finding into a professional report</h1>
      <p class="sub">Reporting is where security value is delivered. Fill in the finding
      and export a clean Markdown or PDF report that mirrors real penetration-testing deliverables.</p>
    </div>

    <div class="btn-row no-print" style="margin-bottom:1rem">
      <button class="btn ghost" id="load-example">Load example finding</button>
      <button class="btn ghost" id="clear-form">Clear</button>
    </div>

    <div class="report-layout">
      <form class="report-form card" id="report-form">${FIELDS.map(fieldHtml).join('')}
        <div class="btn-row" style="margin-top:0.6rem">
          <button type="button" class="btn" id="dl-md">⬇ Download Markdown</button>
          <button type="button" class="btn" id="dl-pdf">⬇ Download PDF</button>
          <button type="button" class="btn ghost" id="print">🖨 Print / Save as PDF</button>
        </div>
      </form>

      <div class="report-preview" id="preview"></div>
    </div>
  `);

  const form = document.getElementById('report-form');
  form.addEventListener('input', (e) => {
    if (e.target.name) state[e.target.name] = e.target.value;
    updatePreview();
  });

  document.getElementById('load-example').addEventListener('click', () => {
    Object.assign(state, EXAMPLE);
    syncForm();
    updatePreview();
  });
  document.getElementById('clear-form').addEventListener('click', () => {
    FIELDS.forEach((f) => (state[f.key] = ''));
    syncForm();
    updatePreview();
  });

  document.getElementById('dl-md').addEventListener('click', () => download('/api/reports/markdown'));
  document.getElementById('dl-pdf').addEventListener('click', () => download('/api/reports/pdf'));
  document.getElementById('print').addEventListener('click', () => window.print());

  updatePreview();
}

function fieldHtml(f) {
  const common = `name="${f.key}" id="f-${f.key}" placeholder="${esc(f.ph || '')}"`;
  let control;
  if (f.type === 'textarea') control = `<textarea ${common}></textarea>`;
  else if (f.type === 'select')
    control = `<select ${common}>${f.options
      .map((o) => `<option value="${esc(o)}">${esc(o)}</option>`)
      .join('')}</select>`;
  else
    control = `<input type="${f.type}" ${common} ${
      f.min !== undefined ? `min="${f.min}" max="${f.max}" step="${f.step}"` : ''
    } />`;
  return `<div class="fieldset"><label for="f-${f.key}">${esc(f.label)}</label>${control}</div>`;
}

function syncForm() {
  FIELDS.forEach((f) => {
    const node = document.getElementById('f-' + f.key);
    if (node) node.value = state[f.key] ?? '';
  });
}

function cvssBand(score) {
  if (score === null || Number.isNaN(score)) return 'Unrated';
  if (score === 0) return 'None';
  if (score < 4) return 'Low';
  if (score < 7) return 'Medium';
  if (score < 9) return 'High';
  return 'Critical';
}

// Build the preview HTML client-side (mirrors the server's Markdown structure).
function updatePreview() {
  const f = state;
  const v = (x, fb = 'N/A') => (String(x || '').trim() ? esc(x) : fb);
  const scoreNum = f.cvssScore === '' ? null : Number(f.cvssScore);
  const cvss = scoreNum === null ? 'N/A' : `${scoreNum.toFixed(1)} (${cvssBand(scoreNum)})`;

  document.getElementById('preview').innerHTML = `
    <h1>Security Assessment Report</h1>
    <blockquote><strong>Confidential — White Hat Lab (Educational).</strong>
    Simulated finding for local training only.</blockquote>
    <p><strong>Finding:</strong> ${v(f.title, 'Untitled Finding')}<br/>
       <strong>Prepared by:</strong> ${v(f.reporter, 'Anonymous Researcher')}</p>
    <h2>1. Summary</h2>
    <table>
      <tr><td>Vulnerability Title</td><td>${v(f.title, 'Untitled Finding')}</td></tr>
      <tr><td>Category</td><td>${v(f.category)}</td></tr>
      <tr><td>Severity</td><td>${v(f.severity, 'Informational')}</td></tr>
      <tr><td>CVSS Base Score</td><td>${cvss}</td></tr>
      <tr><td>Affected Component</td><td>${v(f.affectedComponent)}</td></tr>
    </table>
    <h2>2. Description</h2><p>${v(f.description)}</p>
    <h2>3. Steps to Reproduce</h2><p style="white-space:pre-wrap">${v(f.stepsToReproduce)}</p>
    <h2>4. Proof of Concept</h2><pre>${v(f.proofOfConcept)}</pre>
    <h2>5. Risk Assessment</h2><p>${v(f.riskAssessment)}</p>
    <h2>6. Remediation Recommendations</h2><p>${v(f.remediation)}</p>
  `;
}

// POST the current finding and download the returned file (Markdown or PDF).
async function download(endpoint) {
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...state, date: new Date().toISOString().slice(0, 10) })
    });
    const blob = await res.blob();
    const dispo = res.headers.get('Content-Disposition') || '';
    const match = dispo.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : 'security-report';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('Download failed: ' + e);
  }
}
