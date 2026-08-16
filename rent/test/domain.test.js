'use strict';

const test = require('node:test');
const assert = require('node:assert');

const dbLib = require('../src/db');
const D = require('../src/domain');
const U = require('../src/util');

function makeDb() {
  return dbLib.open(':memory:');
}

function addContract(db, overrides = {}) {
  const now = U.nowISO();
  const values = {
    start_date: '2026-01-01',
    end_date: null,
    rent_agorot: 500000,
    payment_day: 1,
    extras: '[]',
    prorate: 1,
    status: 'active',
    ...overrides,
  };
  const res = dbLib.run(
    db,
    `INSERT INTO contracts (property_id,tenant_id,title,start_date,end_date,rent_agorot,payment_day,default_method,
                            deposit_agorot,deposit_kind,extras,prorate,status,notes,contract_text,created_at,updated_at)
     VALUES (NULL,NULL,'',?,?,?,?,'bank_transfer',0,'',?,?,?,'','',?,?)`,
    [values.start_date, values.end_date, values.rent_agorot, values.payment_day, values.extras, values.prorate, values.status, now, now],
  );
  return D.getContract(db, res.lastInsertRowid);
}

function addPayment(db, contractId, amount, period, status = 'paid') {
  const res = dbLib.run(
    db,
    `INSERT INTO payments (contract_id, amount_agorot, method, status, paid_date, created_at)
     VALUES (?,?,'bank_transfer',?,?,?)`,
    [contractId, amount, status, `${period}-05`, U.nowISO()],
  );
  dbLib.run(db, 'INSERT INTO allocations (payment_id, period, amount_agorot) VALUES (?,?,?)', [res.lastInsertRowid, period, amount]);
  return res.lastInsertRowid;
}

test('נוצר חיוב אחד לכל חודש והפעולה אידמפוטנטית', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  const created = D.ensureCharges(db, contract, '2026-04');
  assert.equal(created, 4);
  assert.equal(D.ensureCharges(db, contract, '2026-04'), 0, 'ריצה שנייה לא מייצרת כפילויות');
  const rows = dbLib.all(db, 'SELECT period, amount_agorot FROM charges ORDER BY period');
  assert.deepEqual(rows.map((r) => r.period), ['2026-01', '2026-02', '2026-03', '2026-04']);
  assert.ok(rows.every((r) => r.amount_agorot === 500000));
});

test('חודש ראשון מחושב יחסית לימים בפועל', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-03-10', rent_agorot: 310000 });
  D.ensureCharges(db, contract, '2026-04');
  const first = dbLib.get(db, "SELECT * FROM charges WHERE period = '2026-03'");
  assert.equal(first.amount_agorot, Math.round((310000 * 22) / 31));
  assert.match(first.label, /22\/31/);
  const second = dbLib.get(db, "SELECT * FROM charges WHERE period = '2026-04'");
  assert.equal(second.amount_agorot, 310000);
});

test('ללא חישוב יחסי מחויב חודש מלא', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-03-10', rent_agorot: 310000, prorate: 0 });
  D.ensureCharges(db, contract, '2026-03');
  assert.equal(dbLib.get(db, "SELECT amount_agorot AS a FROM charges WHERE period = '2026-03'").a, 310000);
});

test('תוספות קבועות נוספות לחיוב החודשי', () => {
  const db = makeDb();
  const contract = addContract(db, { extras: JSON.stringify([{ label: 'ועד בית', amount_agorot: 15000 }]) });
  D.ensureCharges(db, contract, '2026-02');
  const feb = dbLib.all(db, "SELECT * FROM charges WHERE period = '2026-02' ORDER BY kind");
  assert.equal(feb.length, 2);
  assert.equal(feb.reduce((a, c) => a + c.amount_agorot, 0), 515000);
});

test('אין חיובים אחרי תום החוזה', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01', end_date: '2026-02-28' });
  D.ensureCharges(db, contract, '2026-06');
  const periods = dbLib.all(db, 'SELECT DISTINCT period FROM charges ORDER BY period').map((r) => r.period);
  assert.deepEqual(periods, ['2026-01', '2026-02']);
});

test('יתרות: שולם, חלקי, פיגור וממתין', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  D.ensureCharges(db, contract, '2026-03');
  addPayment(db, contract.id, 500000, '2026-01');
  addPayment(db, contract.id, 200000, '2026-02');
  addPayment(db, contract.id, 500000, '2026-03', 'pending');

  const periods = D.contractPeriods(db, contract.id, '2026-03-20');
  const byPeriod = Object.fromEntries(periods.map((p) => [p.period, p]));
  assert.equal(byPeriod['2026-01'].state, 'paid');
  assert.equal(byPeriod['2026-02'].balance, 300000);
  assert.equal(byPeriod['2026-02'].state, 'overdue');
  assert.equal(byPeriod['2026-03'].pending, 500000);
  assert.equal(byPeriod['2026-03'].paid, 0);
  assert.equal(byPeriod['2026-03'].state, 'pending', 'חודש שמכוסה בצ׳ק דחוי אינו בפיגור');

  const summary = D.contractSummary(db, contract.id, '2026-03-20');
  assert.equal(summary.totals.charged, 1500000);
  assert.equal(summary.totals.paid, 700000);
  assert.equal(summary.totals.pending, 500000);
  assert.equal(summary.totals.balance, 800000);
  assert.equal(summary.totals.overdue, 300000, 'רק החוב שאינו מכוסה בצ׳ק נחשב פיגור');
});

test('תשלום שחזר אינו נספר כתשלום', () => {
  const db = makeDb();
  const contract = addContract(db);
  D.ensureCharges(db, contract, '2026-01');
  addPayment(db, contract.id, 500000, '2026-01', 'bounced');
  const summary = D.contractSummary(db, contract.id, '2026-01-20');
  assert.equal(summary.totals.paid, 0);
  assert.equal(summary.totals.balance, 500000);
});

test('פריסה אוטומטית זוקפת לחוב הישן ביותר', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  D.ensureCharges(db, contract, '2026-03');
  const allocations = D.autoAllocate(db, contract.id, 1200000, { today: '2026-03-20' });
  assert.deepEqual(allocations, [
    { period: '2026-01', amount_agorot: 500000 },
    { period: '2026-02', amount_agorot: 500000 },
    { period: '2026-03', amount_agorot: 200000 },
  ]);
});

test('עודף בפריסה אוטומטית נשאר כיתרת זכות', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  D.ensureCharges(db, contract, '2026-01');
  const allocations = D.autoAllocate(db, contract.id, 800000, { today: '2026-01-20' });
  assert.deepEqual(allocations, [{ period: '2026-01', amount_agorot: 500000 }]);
});

test('עדכון שכר דירה משנה רק חיובים עתידיים שלא נערכו ידנית', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  D.ensureCharges(db, contract, '2026-06');
  dbLib.run(db, 'UPDATE contracts SET rent_agorot = 600000 WHERE id = ?', [contract.id]);
  const updated = D.getContract(db, contract.id);
  D.syncFutureCharges(db, updated, '2026-04');
  const rows = dbLib.all(db, 'SELECT period, amount_agorot FROM charges ORDER BY period');
  const byPeriod = Object.fromEntries(rows.map((r) => [r.period, r.amount_agorot]));
  assert.equal(byPeriod['2026-03'], 500000, 'חודשים שעברו נשארים');
  assert.equal(byPeriod['2026-04'], 600000);
  assert.equal(byPeriod['2026-06'], 600000);
});

test('קיצור חוזה מוחק חיובים עתידיים ללא תשלום', () => {
  const db = makeDb();
  const contract = addContract(db, { start_date: '2026-01-01' });
  D.ensureCharges(db, contract, '2026-06');
  addPayment(db, contract.id, 500000, '2026-05');
  dbLib.run(db, "UPDATE contracts SET end_date = '2026-04-30' WHERE id = ?", [contract.id]);
  D.syncFutureCharges(db, D.getContract(db, contract.id), '2026-01');
  const periods = dbLib.all(db, 'SELECT DISTINCT period FROM charges ORDER BY period').map((r) => r.period);
  assert.ok(!periods.includes('2026-06'), 'חודש ללא תשלום נמחק');
  assert.ok(periods.includes('2026-05'), 'חודש עם תשלום נשמר לבדיקה ידנית');
});

test('לוח הבקרה מסכם את כל החוזים לחודש', () => {
  const db = makeDb();
  const a = addContract(db, { start_date: '2026-01-01', rent_agorot: 500000 });
  const b = addContract(db, { start_date: '2026-01-01', rent_agorot: 300000 });
  D.ensureCharges(db, a, '2026-02');
  D.ensureCharges(db, b, '2026-02');
  addPayment(db, a.id, 500000, '2026-02');
  addPayment(db, b.id, 100000, '2026-02');
  const data = D.dashboard(db, '2026-02', '2026-02-20');
  assert.equal(data.totals.expected, 800000);
  assert.equal(data.totals.paid, 600000);
  assert.equal(data.totals.outstanding, 200000);
  assert.equal(data.rows.length, 2);
});
