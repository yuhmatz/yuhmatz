// Tools view: documents the standalone recon scanner and how it maps onto the
// Scanning phase of the methodology.

import { mount } from '../util.js';

export function renderTools() {
  mount(`
    <div class="page-head">
      <span class="eyebrow">Security Automation</span>
      <h1>Recon Scanner</h1>
      <p class="sub">A standalone Python utility that demonstrates the Scanning phase:
      it checks common HTTP service ports on a localhost target and collects response headers.</p>
    </div>

    <div class="callout danger">
      The scanner refuses to run against anything except loopback addresses. Port scanning
      hosts you do not own or are not authorized to test is illegal in many jurisdictions.
    </div>

    <div class="card">
      <h3 class="mt0">Usage</h3>
      <pre class="result-box">
# From the project root, with the lab server running:
python3 tools/recon_scanner.py http://127.0.0.1:3000

# Scan a custom port list:
python3 tools/recon_scanner.py 127.0.0.1 --ports 80,443,3000,8080

# Machine-readable output:
python3 tools/recon_scanner.py http://127.0.0.1:3000 --json</pre>
    </div>

    <div class="grid cols-2">
      <div class="card">
        <h3 class="mt0">What it does</h3>
        <ul class="muted">
          <li>Validates the target resolves to a loopback address (safety guard)</li>
          <li>TCP-connect scans common web ports (80, 443, 3000, 5000, 8000, 8080, 8443)</li>
          <li>Sends an HTTP request to each open port and captures response headers</li>
          <li>Fingerprints the server and flags missing security headers</li>
          <li>Performs light content discovery against a small, safe wordlist</li>
          <li>Prints a readable, colorized terminal report</li>
        </ul>
      </div>
      <div class="card">
        <h3 class="mt0">Where it fits</h3>
        <p class="muted">This tool automates <strong>Stage 2 — Scanning</strong> of the
        methodology. Its output (open ports, service versions, missing headers, discovered
        paths) becomes the input for <strong>Stage 3 — Enumeration</strong> and
        <strong>Stage 4 — Vulnerability Assessment</strong>.</p>
        <p class="muted">Findings you confirm can then be written up in the
        <a href="#/report">Report Generator</a>.</p>
      </div>
    </div>
  `);
}
