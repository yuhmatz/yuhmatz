'use strict';

/**
 * Database bootstrap for the training environment.
 *
 * We use sql.js — SQLite compiled to WebAssembly. It is a *real* SQL engine, so
 * the SQL Injection scenario behaves exactly like a vulnerable production
 * database would. We chose the WASM build (instead of a native module such as
 * better-sqlite3) so the lab installs and runs on any student's machine with no
 * C++ compiler or platform-specific binaries — `npm install` is enough.
 *
 * The database lives entirely in memory and is re-seeded every time the server
 * starts. Nothing here is a secret; the "passwords" below are obviously fake and
 * exist only so the injection demo has something to leak.
 */

const path = require('path');
const initSqlJs = require('sql.js');

/**
 * Initialise an in-memory SQLite database and seed a `users` table.
 * @returns {Promise<import('sql.js').Database>}
 */
async function initDb() {
  const SQL = await initSqlJs({
    // Tell sql.js where to find its .wasm file when running under Node.
    locateFile: (file) =>
      path.join(__dirname, '..', '..', 'node_modules', 'sql.js', 'dist', file)
  });

  const db = new SQL.Database();

  db.run(`
    CREATE TABLE users (
      id       INTEGER PRIMARY KEY,
      username TEXT NOT NULL,
      password TEXT NOT NULL,
      role     TEXT NOT NULL,
      email    TEXT NOT NULL
    );
  `);

  // Seed data. These credentials are intentionally trivial and completely fake.
  // The "secret" the student is meant to discover via SQLi is the admin row.
  const seed = [
    [1, 'admin', 'S3cr3t-Admin-Pw!', 'administrator', 'admin@whitehatlab.local'],
    [2, 'alice', 'password123', 'user', 'alice@whitehatlab.local'],
    [3, 'bob', 'hunter2', 'user', 'bob@whitehatlab.local'],
    [4, 'auditor', 'letmein', 'auditor', 'auditor@whitehatlab.local']
  ];

  const insert = db.prepare(
    'INSERT INTO users (id, username, password, role, email) VALUES (?, ?, ?, ?, ?)'
  );
  for (const row of seed) insert.run(row);
  insert.free();

  return db;
}

module.exports = { initDb };
