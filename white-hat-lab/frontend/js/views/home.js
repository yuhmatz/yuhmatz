// Home / dashboard view — orientation and the suggested learning path.

import { mount } from '../util.js';

export function renderHome() {
  mount(`
    <div class="page-head">
      <span class="eyebrow">White Hat Lab</span>
      <h1>A safe place to learn offensive security — legally.</h1>
      <p class="sub">This lab runs entirely on your machine. It pairs the theory of ethical
      hacking with a deliberately vulnerable practice range and the professional reporting
      workflow that turns findings into fixes.</p>
    </div>

    <div class="grid cols-3">
      <a class="card" href="#/learn" style="text-decoration:none;color:inherit">
        <h3 class="mt0">📚 Learning Center</h3>
        <p class="muted">Rules of Engagement and the eight-stage penetration testing lifecycle.</p>
      </a>
      <a class="card" href="#/training" style="text-decoration:none;color:inherit">
        <h3 class="mt0">🎯 Training Environment</h3>
        <p class="muted">Four vulnerable endpoints: SQLi, reflected XSS, data exposure, path traversal.</p>
      </a>
      <a class="card" href="#/report" style="text-decoration:none;color:inherit">
        <h3 class="mt0">📄 Report Generator</h3>
        <p class="muted">Write up a finding and export it as Markdown or PDF.</p>
      </a>
    </div>

    <div class="card">
      <h3 class="mt0">Suggested path</h3>
      <ol class="muted" style="line-height:2">
        <li>Read the <a href="#/learn">Rules of Engagement</a> — the ethics come first, always.</li>
        <li>Walk the <a href="#/learn">Methodology</a> to understand the full lifecycle.</li>
        <li>Run the <a href="#/tools">recon scanner</a> against <code>127.0.0.1:3000</code> (Scanning).</li>
        <li>Exploit each scenario in the <a href="#/training">Training Environment</a> (Exploitation).</li>
        <li>Read the <code>HOW TO FIX</code> comments in <code>backend/routes/vulnerable.js</code>.</li>
        <li>Write up what you found in the <a href="#/report">Report Generator</a> (Reporting).</li>
      </ol>
    </div>

    <div class="callout danger">
      <strong>Scope statement:</strong> your authorized scope is this application on
      <code>127.0.0.1</code> and nothing else. The server refuses to bind to any non-loopback
      interface and rejects non-local requests by design.
    </div>
  `);
}
