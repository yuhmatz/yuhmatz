// Training Environment view: interactive testers for each vulnerable endpoint.
// The scenario list is fetched from the backend catalog so UI + server stay in
// sync. Each tester lets the student send a payload and inspect the raw result.

import { esc, mount, pretty, severityClass } from '../util.js';

export async function renderTrainingEnv() {
  mount(`
    <div class="page-head">
      <span class="eyebrow">Training Environment</span>
      <h1>Practice range</h1>
      <p class="sub">Every endpoint below is <strong>intentionally vulnerable</strong> and
      served only on 127.0.0.1. Send payloads, read the responses, then study how each
      flaw would be fixed. This is your authorized scope — nothing outside it is.</p>
    </div>
    <div class="callout danger">
      These flaws are for learning on this machine only. Using the same techniques on
      systems you do not own or are not authorized to test is illegal.
    </div>
    <div id="scenarios"><div class="card">Loading scenarios…</div></div>
  `);

  let scenarios = [];
  try {
    const res = await fetch('/api/vuln/catalog');
    scenarios = (await res.json()).scenarios || [];
  } catch (e) {
    document.getElementById('scenarios').innerHTML =
      `<div class="card"><p class="muted">Could not reach the backend. Is the server running? (npm start)</p></div>`;
    return;
  }

  const container = document.getElementById('scenarios');
  container.innerHTML = '';
  scenarios.forEach((s) => container.appendChild(buildScenarioCard(s)));
}

function scenarioHeader(s) {
  return `
    <div class="scenario-head">
      <div>
        <h3 class="mt0">${esc(s.title)}</h3>
        <span class="owasp-tag">${esc(s.owasp)}</span>
      </div>
      <span class="badge ${severityClass(s.severity)}">${esc(s.severity)}</span>
    </div>
    <p class="muted">${esc(s.summary)}</p>
    <div style="margin:0.4rem 0"><span class="endpoint-pill">${esc(s.endpoint)}</span></div>
    <div class="hint-box">💡 <strong>Hint:</strong> ${esc(s.hint)}</div>
  `;
}

function buildScenarioCard(s) {
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = scenarioHeader(s);

  const body = document.createElement('div');
  if (s.id === 'sqli') body.appendChild(buildSqli());
  else if (s.id === 'xss') body.appendChild(buildXss());
  else if (s.id === 'exposure') body.appendChild(buildExposure());
  else if (s.id === 'traversal') body.appendChild(buildTraversal());
  card.appendChild(body);
  return card;
}

/* ------------------------------- SQL Injection --------------------------- */
function buildSqli() {
  const wrap = document.createElement('div');
  wrap.innerHTML = `
    <div class="form-row">
      <div class="field"><label>Username</label><input id="sqli-user" value="admin'--" /></div>
      <div class="field"><label>Password</label><input id="sqli-pass" value="anything" /></div>
    </div>
    <div class="btn-row" style="margin-top:0.7rem">
      <button class="btn" id="sqli-vuln">Attack /api/vuln/login</button>
      <button class="btn ghost" id="sqli-secure">Try the same payload on the secure endpoint</button>
    </div>
    <div id="sqli-out"></div>
  `;
  const out = wrap.querySelector('#sqli-out');
  const send = async (path, label) => {
    const username = wrap.querySelector('#sqli-user').value;
    const password = wrap.querySelector('#sqli-pass').value;
    out.innerHTML = `<p class="result-label">${label}</p><div class="result-box">Sending…</div>`;
    try {
      const res = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();
      const ok = data.success;
      out.innerHTML =
        `<p class="result-label">${label} — HTTP ${res.status}</p>` +
        `<div class="result-box ${ok ? 'success' : 'fail'}">${esc(pretty(data))}</div>`;
    } catch (e) {
      out.innerHTML = `<div class="result-box fail">${esc(String(e))}</div>`;
    }
  };
  wrap.querySelector('#sqli-vuln').addEventListener('click', () =>
    send('/api/vuln/login', 'Vulnerable endpoint')
  );
  wrap.querySelector('#sqli-secure').addEventListener('click', () =>
    send('/api/secure/login', 'Secure endpoint (parameterized)')
  );
  return wrap;
}

/* ------------------------------- Reflected XSS --------------------------- */
function buildXss() {
  const wrap = document.createElement('div');
  wrap.innerHTML = `
    <div class="form-row">
      <div class="field"><label>Name parameter (payload)</label>
        <input id="xss-name" value="<script>alert('xss')<\/script>" /></div>
      <button class="btn" id="xss-go">Render profile</button>
      <button class="btn ghost" id="xss-open">Open in new tab</button>
    </div>
    <p class="result-label">Live rendered response (sandboxed iframe)</p>
    <iframe id="xss-frame" title="profile preview"
      style="width:100%;height:220px;border:1px solid var(--border);border-radius:8px;background:#05090f"
      sandbox="allow-scripts allow-modals"></iframe>
    <p class="muted" style="font-size:0.8rem">The iframe uses <code>allow-scripts</code> so the
    injected script actually executes — exactly what makes reflected XSS dangerous.</p>
  `;
  const frame = wrap.querySelector('#xss-frame');
  const url = () => '/api/vuln/profile?name=' + encodeURIComponent(wrap.querySelector('#xss-name').value);
  wrap.querySelector('#xss-go').addEventListener('click', () => (frame.src = url()));
  wrap.querySelector('#xss-open').addEventListener('click', () => window.open(url(), '_blank'));
  frame.src = url();
  return wrap;
}

/* --------------------------- Sensitive Data Exposure -------------------- */
function buildExposure() {
  const wrap = document.createElement('div');
  wrap.innerHTML = `
    <div class="btn-row">
      <button class="btn" id="exp-list">Fetch /admin-backup index</button>
      <button class="btn ghost" id="exp-open">Open /admin-backup in new tab</button>
    </div>
    <div id="exp-out"></div>
  `;
  const out = wrap.querySelector('#exp-out');
  wrap.querySelector('#exp-open').addEventListener('click', () => window.open('/admin-backup', '_blank'));
  wrap.querySelector('#exp-list').addEventListener('click', async () => {
    out.innerHTML = `<div class="result-box">Fetching…</div>`;
    try {
      const res = await fetch('/admin-backup');
      const html = await res.text();
      // Extract the linked filenames from the returned index for a quick summary.
      const files = [...html.matchAll(/file=([^"']+)/g)].map((m) => decodeURIComponent(m[1]));
      out.innerHTML =
        `<p class="result-label">Exposed backup files (HTTP ${res.status})</p>` +
        `<div class="result-box fail">${esc(files.join('\n') || '(none found)')}</div>` +
        `<p class="muted" style="font-size:0.8rem">Click a file in the traversal tester below to read it,
         or open the raw index in a new tab.</p>`;
    } catch (e) {
      out.innerHTML = `<div class="result-box fail">${esc(String(e))}</div>`;
    }
  });
  return wrap;
}

/* ---------------------------- Directory Traversal ----------------------- */
function buildTraversal() {
  const wrap = document.createElement('div');
  wrap.innerHTML = `
    <div class="form-row">
      <div class="field"><label>File to download</label>
        <input id="trav-file" value="database_backup.sql" /></div>
      <button class="btn" id="trav-go">Read file</button>
    </div>
    <div class="btn-row" style="margin-top:0.5rem">
      <button class="btn ghost tiny" data-payload="database_backup.sql">database_backup.sql</button>
      <button class="btn ghost tiny" data-payload="../config.js">../config.js (escape sandbox)</button>
      <button class="btn ghost tiny" data-payload="../../package.json">../../package.json</button>
    </div>
    <div id="trav-out"></div>
  `;
  const input = wrap.querySelector('#trav-file');
  const out = wrap.querySelector('#trav-out');
  const read = async () => {
    const file = input.value;
    out.innerHTML = `<div class="result-box">Reading “${esc(file)}”…</div>`;
    try {
      const res = await fetch('/api/vuln/download?file=' + encodeURIComponent(file));
      const text = await res.text();
      const resolved = res.headers.get('X-Resolved-Path') || '';
      out.innerHTML =
        `<p class="result-label">HTTP ${res.status}${resolved ? ' · resolved → ' + esc(resolved) : ''}</p>` +
        `<div class="result-box ${res.ok ? 'success' : 'fail'}">${esc(text)}</div>`;
    } catch (e) {
      out.innerHTML = `<div class="result-box fail">${esc(String(e))}</div>`;
    }
  };
  wrap.querySelector('#trav-go').addEventListener('click', read);
  wrap.querySelectorAll('[data-payload]').forEach((b) =>
    b.addEventListener('click', () => {
      input.value = b.dataset.payload;
      read();
    })
  );
  return wrap;
}
