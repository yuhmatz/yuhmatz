'use strict';

/**
 * SECURE reference implementations.
 *
 * The Training Environment is about seeing flaws; this file is the counterpart
 * that shows what "done right" looks like, so students can compare the two side
 * by side. The frontend calls /api/secure/login to prove that the very same
 * injection payloads that bypass /api/vuln/login FAIL here.
 */

const express = require('express');

module.exports = function createSecureRouter(db) {
  const router = express.Router();

  // SECURE LOGIN — parameterized query.
  //
  // The "?" placeholders are bound as DATA by the SQLite engine. User input can
  // never change the structure of the statement, so  admin'--  is treated as a
  // literal (nonexistent) username and the login simply fails. This is the fix
  // for the SQL Injection scenario.
  router.post('/login', (req, res) => {
    const username = String(req.body.username ?? '');
    const password = String(req.body.password ?? '');

    try {
      const stmt = db.prepare(
        'SELECT id, username, role, email FROM users WHERE username = ? AND password = ?'
      );
      stmt.bind([username, password]); // <-- input bound as parameters, not code
      const rows = [];
      while (stmt.step()) rows.push(stmt.getAsObject());
      stmt.free();

      if (rows.length > 0) {
        return res.json({
          success: true,
          message: 'Authentication successful (parameterized query).',
          user: rows[0]
        });
      }
      return res.status(401).json({
        success: false,
        message: 'Invalid credentials. Injection payloads are neutralized here.'
      });
    } catch (err) {
      // Note: we return a generic message and do NOT leak the SQL error.
      return res.status(500).json({ success: false, message: 'Server error.' });
    }
  });

  return router;
};
