'use strict';

/**
 * White Hat Lab — server entry point.
 *
 * Responsibilities:
 *   1. Serve the static Learning Center frontend.
 *   2. Mount the intentionally vulnerable training endpoints.
 *   3. Mount the secure reference endpoints (the "fixed" versions).
 *   4. Mount the report generator.
 *   5. Refuse to listen on anything except the loopback interface.
 *
 * Run with:  npm start     (then open http://127.0.0.1:3000)
 */

const express = require('express');
const config = require('./config');
const { initDb } = require('./db/init');
const createVulnerableRouter = require('./routes/vulnerable');
const createSecureRouter = require('./routes/secure');
const reportsRouter = require('./routes/reports');

// -----------------------------------------------------------------------------
// SAFETY GUARD
// -----------------------------------------------------------------------------
// A defence-in-depth assertion. Even if someone edits config.js, the process
// refuses to start on a non-loopback interface. The lab must never be reachable
// from another machine.
// -----------------------------------------------------------------------------
const LOOPBACK = new Set(['127.0.0.1', 'localhost', '::1']);
if (!LOOPBACK.has(config.HOST)) {
  console.error(
    '\n[ABORT] White Hat Lab may only bind to the loopback interface.\n' +
      `        Refusing to start on host "${config.HOST}".\n` +
      '        This server hosts intentionally vulnerable endpoints and must\n' +
      '        never be exposed to a network.\n'
  );
  process.exit(1);
}

async function main() {
  const db = await initDb();
  const app = express();

  // Body parsing for the JSON APIs and the classic form-encoded login demo.
  app.use(express.json({ limit: '256kb' }));
  app.use(express.urlencoded({ extended: false, limit: '256kb' }));

  // Extra belt-and-braces: reject any request that did not arrive over loopback.
  // If a reverse proxy were ever placed in front of the lab, this still blocks
  // remote clients from reaching the vulnerable routes.
  app.use((req, res, next) => {
    const ip = req.socket.remoteAddress || '';
    const isLocal =
      ip === '127.0.0.1' || ip === '::1' || ip === '::ffff:127.0.0.1';
    if (!isLocal) {
      return res
        .status(403)
        .type('text/plain')
        .send('White Hat Lab is restricted to local (loopback) access only.');
    }
    next();
  });

  // --- Static Learning Center frontend ---------------------------------------
  app.use(express.static(config.paths.frontend));

  // --- API routes -------------------------------------------------------------
  const vulnerableRouter = createVulnerableRouter(db);
  app.use('/api/vuln', vulnerableRouter);
  app.use('/api/secure', createSecureRouter(db));
  app.use('/api/reports', reportsRouter);

  // The "hidden" misconfiguration route lives at the top level on purpose, so it
  // looks like a forgotten directory rather than part of the documented API.
  app.get('/admin-backup', vulnerableRouter.adminBackupHandler);

  // Simple health/metadata endpoint — also gives the recon scanner something
  // meaningful to fingerprint.
  app.get('/api/health', (_req, res) => {
    res.json({
      status: 'ok',
      app: 'White Hat Lab',
      mode: 'local-training',
      boundTo: `${config.HOST}:${config.PORT}`
    });
  });

  // The frontend uses hash-based routing (e.g. #/training), so the server never
  // needs a path-based SPA catch-all: express.static already serves index.html
  // at "/". Returning a genuine 404 for unmatched paths keeps the recon
  // scanner's content-discovery output honest — /admin-backup is a real finding,
  // while /backup or /.env correctly 404 instead of masquerading as 200s.
  app.use((req, res) => {
    res
      .status(404)
      .type('text/plain')
      .send('404 Not Found: ' + req.method + ' ' + req.path);
  });

  app.listen(config.PORT, config.HOST, () => {
    console.log('\n  White Hat Lab — local training environment');
    console.log('  ------------------------------------------------');
    console.log(`  Learning Center : http://${config.HOST}:${config.PORT}/`);
    console.log(`  Bound to        : ${config.HOST} (loopback only)`);
    console.log('  Scope           : this machine only. Nothing else is in scope.');
    console.log('  ------------------------------------------------');
    console.log('  Training endpoints:');
    console.log('    POST /api/vuln/login          (SQL Injection)');
    console.log('    GET  /api/vuln/profile?name=  (Reflected XSS)');
    console.log('    GET  /admin-backup            (Sensitive Data Exposure)');
    console.log('    GET  /api/vuln/download?file= (Path Traversal)');
    console.log('    POST /api/secure/login        (the secure counterpart)\n');
  });
}

main().catch((err) => {
  console.error('[FATAL] Failed to start White Hat Lab:', err);
  process.exit(1);
});
