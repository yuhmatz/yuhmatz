'use strict';

/**
 * =============================================================================
 *  INTENTIONALLY VULNERABLE ROUTES  —  FOR LOCAL EDUCATIONAL USE ONLY
 * =============================================================================
 *
 * Every endpoint in this file contains a DELIBERATE security flaw. They exist so
 * students can *see* how classic web vulnerabilities behave, then practise
 * identifying, exploiting (in a sandbox), and — most importantly — FIXING them.
 *
 * DO NOT copy these patterns into real software. Each flaw is paired with a
 * "HOW TO FIX" comment showing the secure alternative.
 *
 * The whole server binds to 127.0.0.1 (see backend/config.js), so these flaws
 * are only ever reachable from this same machine.
 * =============================================================================
 */

const express = require('express');
const fs = require('fs');
const path = require('path');
const config = require('../config');

/**
 * Build the router. We inject the database so the SQLi demo runs against a real
 * SQL engine.
 * @param {import('sql.js').Database} db
 */
module.exports = function createVulnerableRouter(db) {
  const router = express.Router();

  // ---------------------------------------------------------------------------
  // Scenario catalog — consumed by the frontend "Training Environment" view so
  // the UI and the backend never drift out of sync.
  // ---------------------------------------------------------------------------
  router.get('/catalog', (_req, res) => {
    res.json({
      scenarios: [
        {
          id: 'sqli',
          title: 'SQL Injection — Authentication Bypass',
          owasp: 'A03:2021 – Injection',
          endpoint: 'POST /api/vuln/login',
          summary:
            'The login query concatenates user input directly into SQL. A crafted username can rewrite the query logic and bypass authentication.',
          hint: "Username: admin'--  (any password). Or dump every row with username:  ' OR '1'='1' --  (note the trailing --, which comments out the password check).",
          severity: 'Critical'
        },
        {
          id: 'xss',
          title: 'Reflected Cross-Site Scripting (XSS)',
          owasp: 'A03:2021 – Injection',
          endpoint: 'GET /api/vuln/profile?name=...',
          summary:
            'The profile page echoes the "name" parameter into HTML without encoding, so any markup or script is executed by the browser.',
          hint: "Try name:  <script>alert('xss')</script>  or  <img src=x onerror=alert(1)>",
          severity: 'Medium'
        },
        {
          id: 'exposure',
          title: 'Sensitive Data Exposure — Forgotten Backups',
          owasp: 'A05:2021 – Security Misconfiguration',
          endpoint: 'GET /admin-backup',
          summary:
            'An unauthenticated, "hidden" route lists server backup files (a database dump, an .env backup, an employee export). Obscurity is not security.',
          hint: 'Browse to /admin-backup — nothing stops you from reading the files.',
          severity: 'High'
        },
        {
          id: 'traversal',
          title: 'Path / Directory Traversal',
          owasp: 'A01:2021 – Broken Access Control',
          endpoint: 'GET /api/vuln/download?file=...',
          summary:
            'The download handler joins the "file" parameter to a base directory without validation, so ../ sequences escape the intended folder.',
          hint: "Try file=database_backup.sql, then file=../config.js, then file=../../package.json",
          severity: 'High'
        }
      ]
    });
  });

  // ===========================================================================
  // SCENARIO 1 — SQL INJECTION (Authentication Bypass)
  // ===========================================================================
  //
  // WHY THE VULNERABILITY EXISTS:
  //   The SQL statement is built by string concatenation, mixing trusted query
  //   structure with untrusted user input. The database cannot tell the two
  //   apart, so input like  admin'--  turns into part of the SQL command.
  //
  // HOW AN ATTACKER FINDS IT:
  //   A single quote (') in a field often triggers a SQL error or changes the
  //   response, signalling that input reaches the query unescaped. From there
  //   they try boolean payloads (' OR '1'='1) or comment terminators (--).
  //
  // REAL-WORLD IMPACT:
  //   Authentication bypass, full data exfiltration, and sometimes remote code
  //   execution. SQL Injection has been behind many of the largest breaches on
  //   record.
  //
  // HOW TO FIX (see the /api/secure/login endpoint below for a working example):
  //   Use PARAMETERIZED QUERIES / prepared statements so input is always treated
  //   as data, never as code. Never concatenate user input into SQL.
  // ---------------------------------------------------------------------------
  router.post('/login', (req, res) => {
    const username = String(req.body.username ?? '');
    const password = String(req.body.password ?? '');

    // !!! VULNERABLE: user input is concatenated straight into the query. !!!
    const query =
      "SELECT id, username, role, email FROM users " +
      "WHERE username = '" + username + "' AND password = '" + password + "'";

    try {
      const results = db.exec(query); // sql.js executes the raw string
      const rows = toObjects(results);

      if (rows.length > 0) {
        return res.json({
          success: true,
          message: 'Authentication successful.',
          executedQuery: query, // echoed so students can SEE what they built
          user: rows[0],
          leakedRows: rows // an injection can return every user at once
        });
      }
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials.',
        executedQuery: query
      });
    } catch (err) {
      // A raw SQL error leaking to the client is itself an information leak,
      // and is exactly the signal an attacker uses to confirm injectability.
      return res.status(500).json({
        success: false,
        message: 'SQL error: ' + err.message,
        executedQuery: query
      });
    }
  });

  // ===========================================================================
  // SCENARIO 2 — REFLECTED CROSS-SITE SCRIPTING (XSS)
  // ===========================================================================
  //
  // WHY THE VULNERABILITY EXISTS:
  //   The "name" query parameter is inserted directly into the HTML response.
  //   The browser has no way to know the value was meant to be plain text, so
  //   any <script> or event-handler attribute runs with the site's privileges.
  //
  // HOW AN ATTACKER FINDS IT:
  //   They inject a harmless marker like <b>test</b>; if it renders bold instead
  //   of showing the literal tags, the input is reflected unencoded. They then
  //   escalate to <script> or <img onerror> payloads.
  //
  // REAL-WORLD IMPACT:
  //   Session/cookie theft, keylogging, phishing overlays, and full account
  //   takeover — all executed in the victim's browser under the trusted origin.
  //
  // HOW TO FIX:
  //   1) Contextually ENCODE output (e.g. escape <, >, &, ", ' before inserting
  //      into HTML). 2) Set a Content-Security-Policy that forbids inline script.
  //   3) Prefer templating engines / frameworks that auto-escape by default.
  //   (This demo deliberately omits all three so the payload executes.)
  // ---------------------------------------------------------------------------
  router.get('/profile', (req, res) => {
    const name = String(req.query.name ?? 'Guest');

    // !!! VULNERABLE: `name` is concatenated into HTML with no encoding. !!!
    const html =
      '<!doctype html>' +
      '<html lang="en"><head><meta charset="utf-8">' +
      '<title>User Profile</title>' +
      '<style>body{font-family:system-ui,sans-serif;background:#0b0f17;color:#e6edf3;' +
      'padding:2rem;line-height:1.6}.card{max-width:640px;margin:auto;background:#111826;' +
      'border:1px solid #1f2a3a;border-radius:12px;padding:2rem}code{color:#7ee787}' +
      'a{color:#58a6ff}</style></head><body><div class="card">' +
      '<h1>Welcome, ' + name + '!</h1>' + // <-- the sink
      '<p>This profile page reflects the <code>name</code> parameter straight ' +
      'into the HTML with no output encoding.</p>' +
      '<p>Reflected value: ' + name + '</p>' +
      '<p><a href="/#/training">&larr; Back to the Training Environment</a></p>' +
      '</div></body></html>';

    // Note: we intentionally do NOT send a Content-Security-Policy header here.
    res.type('html').send(html);
  });

  // ===========================================================================
  // SCENARIO 3 — SENSITIVE DATA EXPOSURE via a "hidden" /admin-backup route
  // ===========================================================================
  //
  // WHY THE VULNERABILITY EXISTS:
  //   Operators sometimes leave database dumps, .env backups, or exports on a
  //   web-reachable path and assume nobody will guess the URL ("security through
  //   obscurity"). There is no authentication and no access control here.
  //
  // HOW AN ATTACKER FINDS IT:
  //   Automated content discovery / wordlist scanning (dirb, gobuster, ffuf)
  //   brute-forces common paths like /backup, /admin-backup, /.git, /.env.bak.
  //
  // REAL-WORLD IMPACT:
  //   Instant leak of credentials, API keys, password hashes, and customer PII —
  //   frequently the first domino in a full compromise.
  //
  // HOW TO FIX:
  //   Never store backups/secrets under the web root. Require authentication &
  //   authorization for admin functionality. Serve static content from a
  //   dedicated public directory only. Add secrets/backups to deny-lists.
  //
  // NOTE: this handler is mounted at the top level (/admin-backup), not under
  // /api/vuln, precisely to mimic an "unlinked but reachable" path.
  // ---------------------------------------------------------------------------
  const adminBackupHandler = (_req, res) => {
    let files = [];
    try {
      files = fs.readdirSync(config.paths.labFiles);
    } catch (_e) {
      files = [];
    }

    const list = files
      .map(
        (f) =>
          '<li><a href="/api/vuln/download?file=' +
          encodeURIComponent(f) +
          '">' +
          escapeHtml(f) +
          '</a></li>'
      )
      .join('');

    res.type('html').send(
      '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
        '<title>admin-backup</title>' +
        '<style>body{font-family:ui-monospace,monospace;background:#0b0f17;color:#e6edf3;' +
        'padding:2rem}.warn{color:#ff7b72}a{color:#58a6ff}.card{max-width:720px;margin:auto;' +
        'background:#111826;border:1px solid #1f2a3a;border-radius:12px;padding:2rem}</style>' +
        '</head><body><div class="card">' +
        '<h1>Index of /admin-backup</h1>' +
        '<p class="warn">[MISCONFIGURATION] Unauthenticated backup directory exposed.</p>' +
        '<p>These are simulated, clearly-fake files left on the "server". In a real ' +
        'assessment, exposure of any of these would be a high-severity finding.</p>' +
        '<ul>' +
        list +
        '</ul>' +
        '<p><a href="/#/training">&larr; Back to the Training Environment</a></p>' +
        '</div></body></html>'
    );
  };

  // ===========================================================================
  // SCENARIO 4 — PATH / DIRECTORY TRAVERSAL
  // ===========================================================================
  //
  // WHY THE VULNERABILITY EXISTS:
  //   The requested filename is joined to a base directory without validation.
  //   path.join() resolves "../" segments, so the final path can escape the
  //   intended lab-files sandbox and reach other files this process can read.
  //
  // HOW AN ATTACKER FINDS IT:
  //   They notice a file/download parameter and probe with ../ sequences
  //   (e.g. ../../etc/passwd on Linux, ..\..\windows\win.ini on Windows).
  //
  // REAL-WORLD IMPACT:
  //   Disclosure of source code, configuration, credentials, and OS files —
  //   anything the web process has permission to read.
  //
  // HOW TO FIX:
  //   Resolve the requested path and verify it still starts with the intended
  //   base directory BEFORE reading. Reject absolute paths and any "..". Better:
  //   reference files by an allow-listed id, never by a client-supplied path.
  //   (A correct implementation is shown, commented out, at the bottom.)
  // ---------------------------------------------------------------------------
  router.get('/download', (req, res) => {
    const requested = String(req.query.file ?? '');
    if (!requested) {
      return res.status(400).type('text/plain').send('Provide ?file=<name>');
    }

    // !!! VULNERABLE: no check that the resolved path stays inside labFiles. !!!
    const target = path.join(config.paths.labFiles, requested);

    // --- SECURE VERSION (what the fix looks like) ------------------------------
    // const base = config.paths.labFiles;
    // const resolved = path.resolve(base, requested);
    // if (resolved !== base && !resolved.startsWith(base + path.sep)) {
    //   return res.status(403).type('text/plain').send('Access denied.');
    // }
    // ---------------------------------------------------------------------------

    fs.readFile(target, 'utf8', (err, data) => {
      if (err) {
        return res
          .status(404)
          .type('text/plain')
          .send('Could not read "' + requested + '": ' + err.code);
      }
      // Send as plain text so source/config is shown, not executed or downloaded.
      res
        .type('text/plain')
        .set('X-Resolved-Path', target) // echoed so students see where it landed
        .send(data);
    });
  });

  // Expose the admin-backup handler so server.js can mount it at the root path.
  router.adminBackupHandler = adminBackupHandler;

  return router;
};

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

/** Convert sql.js exec() output ([{columns, values}]) into an array of objects. */
function toObjects(execResult) {
  if (!execResult || execResult.length === 0) return [];
  const { columns, values } = execResult[0];
  return values.map((row) => {
    const obj = {};
    columns.forEach((col, i) => (obj[col] = row[i]));
    return obj;
  });
}

/** Minimal HTML escaper — used for the trusted parts of the admin-backup page. */
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
