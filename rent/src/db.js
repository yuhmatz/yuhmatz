'use strict';

/* שכבת בסיס הנתונים – SQLite המובנה של Node (ללא התקנות). */

const fs = require('node:fs');
const path = require('node:path');

// node:sqlite מסומן כ"ניסיוני" ומדפיס אזהרה בכל הרצה – היא לא רלוונטית למשתמש.
const emitWarning = process.emitWarning;
process.emitWarning = (warning, ...rest) => {
  if (String(warning).includes('SQLite is an experimental feature')) return;
  return emitWarning.call(process, warning, ...rest);
};

const { DatabaseSync } = require('node:sqlite');

const SCHEMA = `
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS properties (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  address     TEXT NOT NULL DEFAULT '',
  city        TEXT NOT NULL DEFAULT '',
  unit        TEXT NOT NULL DEFAULT '',
  notes       TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tenants (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT NOT NULL,
  phone       TEXT NOT NULL DEFAULT '',
  email       TEXT NOT NULL DEFAULT '',
  national_id TEXT NOT NULL DEFAULT '',
  notes       TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contracts (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  property_id    INTEGER REFERENCES properties(id) ON DELETE SET NULL,
  tenant_id      INTEGER REFERENCES tenants(id) ON DELETE SET NULL,
  title          TEXT NOT NULL DEFAULT '',
  start_date     TEXT NOT NULL,
  end_date       TEXT,
  rent_agorot    INTEGER NOT NULL DEFAULT 0,
  payment_day    INTEGER NOT NULL DEFAULT 1,
  default_method TEXT NOT NULL DEFAULT 'bank_transfer',
  deposit_agorot INTEGER NOT NULL DEFAULT 0,
  deposit_kind   TEXT NOT NULL DEFAULT '',
  extras         TEXT NOT NULL DEFAULT '[]',
  prorate        INTEGER NOT NULL DEFAULT 1,
  status         TEXT NOT NULL DEFAULT 'active',
  notes          TEXT NOT NULL DEFAULT '',
  contract_text  TEXT NOT NULL DEFAULT '',
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contract_files (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id   INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,
  mime          TEXT NOT NULL DEFAULT '',
  size          INTEGER NOT NULL DEFAULT 0,
  stored_name   TEXT NOT NULL,
  text          TEXT NOT NULL DEFAULT '',
  extract_status TEXT NOT NULL DEFAULT 'none',
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_contract ON contract_files(contract_id);

CREATE TABLE IF NOT EXISTS charges (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id     INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  period          TEXT NOT NULL,
  kind            TEXT NOT NULL DEFAULT 'rent',
  label           TEXT NOT NULL DEFAULT '',
  amount_agorot   INTEGER NOT NULL DEFAULT 0,
  due_date        TEXT NOT NULL,
  source_key      TEXT,
  manual_override INTEGER NOT NULL DEFAULT 0,
  canceled        INTEGER NOT NULL DEFAULT 0,
  notes           TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_charges_contract ON charges(contract_id, period);
-- מונע כפילות של חיובים אוטומטיים. ב-SQLite ערכי NULL נחשבים שונים זה מזה,
-- ולכן חיובים ידניים (source_key = NULL) אינם מתנגשים.
CREATE UNIQUE INDEX IF NOT EXISTS idx_charges_auto
  ON charges(contract_id, period, source_key);

CREATE TABLE IF NOT EXISTS payments (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id   INTEGER NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
  amount_agorot INTEGER NOT NULL DEFAULT 0,
  method        TEXT NOT NULL DEFAULT 'bank_transfer',
  status        TEXT NOT NULL DEFAULT 'paid',
  paid_date     TEXT NOT NULL,
  due_date      TEXT,
  reference     TEXT NOT NULL DEFAULT '',
  bank          TEXT NOT NULL DEFAULT '',
  branch        TEXT NOT NULL DEFAULT '',
  account       TEXT NOT NULL DEFAULT '',
  check_number  TEXT NOT NULL DEFAULT '',
  notes         TEXT NOT NULL DEFAULT '',
  created_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_payments_contract ON payments(contract_id);
CREATE INDEX IF NOT EXISTS idx_payments_date ON payments(paid_date);

CREATE TABLE IF NOT EXISTS allocations (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id    INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
  period        TEXT NOT NULL,
  amount_agorot INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alloc_payment ON allocations(payment_id);
CREATE INDEX IF NOT EXISTS idx_alloc_period ON allocations(period);

CREATE TABLE IF NOT EXISTS settings (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
`;

/**
 * פותח (ויוצר במידת הצורך) את מסד הנתונים.
 * @param {string} file נתיב לקובץ, או ':memory:' לבדיקות.
 */
function open(file) {
  if (file !== ':memory:') {
    fs.mkdirSync(path.dirname(file), { recursive: true });
  }
  const db = new DatabaseSync(file);
  db.exec(SCHEMA);
  return db;
}

/** run/get/all עם המרה בטוחה של lastInsertRowid (יכול לחזור כ-BigInt). */
function run(db, sql, params = []) {
  const res = db.prepare(sql).run(...params);
  return {
    changes: Number(res.changes),
    lastInsertRowid: Number(res.lastInsertRowid),
  };
}

function all(db, sql, params = []) {
  return db.prepare(sql).all(...params);
}

function get(db, sql, params = []) {
  return db.prepare(sql).get(...params);
}

function tx(db, fn) {
  db.exec('BEGIN');
  try {
    const out = fn();
    db.exec('COMMIT');
    return out;
  } catch (err) {
    try {
      db.exec('ROLLBACK');
    } catch {
      /* ignore */
    }
    throw err;
  }
}

function getSetting(db, key, fallback = null) {
  const row = get(db, 'SELECT value FROM settings WHERE key = ?', [key]);
  return row ? row.value : fallback;
}

function setSetting(db, key, value) {
  run(db, 'INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value', [
    key,
    String(value),
  ]);
}

module.exports = { open, run, all, get, tx, getSetting, setSetting, SCHEMA };
