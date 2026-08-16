'use strict';

const test = require('node:test');
const assert = require('node:assert');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const dbLib = require('../src/db');
const { createRouter, ApiError } = require('../src/api');
const U = require('../src/util');

function setup() {
  const db = dbLib.open(':memory:');
  const uploadsDir = fs.mkdtempSync(path.join(os.tmpdir(), 'rent-test-'));
  const router = createRouter({ db, uploadsDir });
  const call = (method, pathname, query = {}, body = {}) => router.dispatch(method, pathname, query, body);
  return { db, router, call, uploadsDir };
}

const THIS_MONTH = U.currentPeriod();
const LAST_MONTH = U.addMonths(THIS_MONTH, -1);
const TWO_AGO = U.addMonths(THIS_MONTH, -2);

function baseData(call) {
  const property = call('POST', '/api/properties', {}, { name: 'דירה בהרצל 12', address: 'הרצל 12', city: 'תל אביב' });
  const tenant = call('POST', '/api/tenants', {}, { name: 'דנה כהן', phone: '052-1112233' });
  const contract = call('POST', '/api/contracts', {}, {
    property_id: property.id,
    tenant_id: tenant.id,
    title: 'שכירות דירה',
    start_date: `${TWO_AGO}-01`,
    rent: '5,000',
    payment_day: 1,
    default_method: 'bank_transfer',
    deposit: '10000',
    extras: [{ label: 'ועד בית', amount: '150' }],
    contract_text: 'השוכר ישלם דמי שכירות בסך 5,000 ש"ח. לשוכר אופציה להארכת החוזה בשנה נוספת בהודעה מראש של 60 יום.',
  });
  return { property, tenant, contract };
}

test('יצירת חוזה מייצרת חיובים חודשיים אוטומטית', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  const full = call('GET', `/api/contracts/${contract.id}`);
  const periods = [...new Set(full.charges.map((c) => c.period))];
  assert.ok(periods.includes(TWO_AGO) && periods.includes(LAST_MONTH) && periods.includes(THIS_MONTH));
  const monthCharges = full.charges.filter((c) => c.period === THIS_MONTH);
  assert.equal(monthCharges.reduce((a, c) => a + c.amount_agorot, 0), 515000, 'שכר דירה + ועד בית');
  assert.equal(full.summary.balance, full.summary.charged, 'טרם שולם דבר');
});

test('רישום תשלום נזקף אוטומטית לחוב הישן ביותר', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'cash', paid_date: `${TWO_AGO}-03` });
  const full = call('GET', `/api/contracts/${contract.id}`);
  const oldest = full.periods.find((p) => p.period === TWO_AGO);
  assert.equal(oldest.paid, 515000);
  assert.equal(oldest.state, 'paid');
  assert.equal(full.payments[0].allocations[0].period, TWO_AGO);
});

test('תשלום גדול נפרס על כמה חודשים', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '10300', method: 'bank_transfer', reference: 'אסמכתא 55' });
  const payment = call('GET', '/api/payments')[0];
  assert.equal(payment.allocations.length, 2);
  assert.deepEqual(payment.allocations.map((a) => a.period), [TWO_AGO, LAST_MONTH]);
});

test('שיוך ידני לחודש מסוים', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'bit', period: THIS_MONTH });
  const full = call('GET', `/api/contracts/${contract.id}`);
  assert.equal(full.periods.find((p) => p.period === THIS_MONTH).paid, 515000);
  assert.equal(full.periods.find((p) => p.period === TWO_AGO).paid, 0);
});

test('צ׳ק דחוי נספר כממתין ורק לאחר פירעון כשולם', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  const check = call('POST', '/api/payments', {}, {
    contract_id: contract.id,
    amount: '5150',
    method: 'check',
    check_number: '1042',
    bank: 'הפועלים',
    due_date: `${THIS_MONTH}-01`,
    period: THIS_MONTH,
  });
  assert.equal(check.status, 'pending', 'ברירת המחדל לצ׳ק היא ממתין לפירעון');

  let dash = call('GET', '/api/dashboard', { period: THIS_MONTH });
  assert.equal(dash.totals.pending, 515000);
  assert.equal(dash.totals.paid, 0);
  assert.equal(dash.checks.length, 1);

  call('PUT', `/api/payments/${check.id}`, {}, {
    amount_agorot: check.amount_agorot,
    method: 'check',
    status: 'paid',
    paid_date: check.paid_date,
    allocations: [{ period: THIS_MONTH, amount_agorot: check.amount_agorot }],
  });
  dash = call('GET', '/api/dashboard', { period: THIS_MONTH });
  assert.equal(dash.totals.paid, 515000);
  assert.equal(dash.totals.pending, 0);
  assert.equal(dash.checks.length, 0);
});

test('צ׳ק שחזר אינו נספר בגבייה', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  const check = call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'check', period: THIS_MONTH });
  call('PUT', `/api/payments/${check.id}`, {}, {
    amount_agorot: check.amount_agorot,
    method: 'check',
    status: 'bounced',
    paid_date: check.paid_date,
    allocations: [{ period: THIS_MONTH, amount_agorot: check.amount_agorot }],
  });
  const dash = call('GET', '/api/dashboard', { period: THIS_MONTH });
  assert.equal(dash.totals.paid, 0);
  assert.equal(dash.totals.pending, 0);
});

test('חיוב חד־פעמי מתווסף ליתרה', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  const before = call('GET', `/api/contracts/${contract.id}`).summary.charged;
  call('POST', '/api/charges', {}, { contract_id: contract.id, period: THIS_MONTH, label: 'תיקון דוד שמש', amount: '480' });
  const after = call('GET', `/api/contracts/${contract.id}`);
  assert.equal(after.summary.charged, before + 48000);
  const charge = after.charges.find((c) => c.label === 'תיקון דוד שמש');
  assert.equal(charge.kind, 'manual');

  call('PUT', `/api/charges/${charge.id}`, {}, { canceled: true, label: charge.label });
  assert.equal(call('GET', `/api/contracts/${contract.id}`).summary.charged, before, 'חיוב מבוטל יורד מהיתרה');
});

test('עדכון שכר הדירה לא משנה חודשים ששולמו', () => {
  const { call } = setup();
  const { property, tenant, contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', period: TWO_AGO, method: 'cash' });
  call('PUT', `/api/contracts/${contract.id}`, {}, {
    property_id: property.id,
    tenant_id: tenant.id,
    start_date: `${TWO_AGO}-01`,
    rent: '5500',
    payment_day: 1,
    extras: [{ label: 'ועד בית', amount: '150' }],
  });
  const full = call('GET', `/api/contracts/${contract.id}`);
  const oldRent = full.charges.find((c) => c.period === TWO_AGO && c.kind === 'rent');
  const newRent = full.charges.find((c) => c.period === THIS_MONTH && c.kind === 'rent');
  assert.equal(oldRent.amount_agorot, 500000);
  assert.equal(newRent.amount_agorot, 550000);
});

test('חיפוש מוצא ביטוי בנוסח החוזה ומחזיר קטע מסומן', () => {
  const { call } = setup();
  baseData(call);
  const res = call('GET', '/api/search', { q: 'אופציה' });
  assert.equal(res.count, 1);
  const match = res.results[0].matches[0];
  const snippet = match.snippets[0];
  const [start, end] = snippet.ranges[0];
  assert.equal(snippet.text.slice(start, end), 'אופציה');
  assert.equal(call('GET', '/api/search', { q: 'מרפסת' }).count, 0);
  assert.equal(call('GET', '/api/search', { q: 'דנה' }).count, 1, 'חיפוש גם בפרטי הדייר');
});

test('חיפוש בתוך קובץ שהועלה', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  const text = 'נספח לחוזה: השוכר רשאי להחזיק חיית מחמד אחת בדירה.';
  const upload = call('POST', `/api/contracts/${contract.id}/files`, {}, {
    filename: 'נספח.txt',
    mime: 'text/plain',
    data_base64: Buffer.from(text, 'utf8').toString('base64'),
  });
  assert.equal(upload.extract_status, 'ok');
  const res = call('GET', '/api/search', { q: '"חיית מחמד"' });
  assert.equal(res.count, 1);
  assert.match(res.results[0].matches[0].label, /נספח\.txt/);
});

test('כרטסת מציגה יתרה רצה', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', period: TWO_AGO, method: 'cash' });
  const statement = call('GET', '/api/statement', { contract_id: contract.id });
  assert.ok(statement.events.length >= 4);
  const last = statement.events[statement.events.length - 1];
  assert.equal(last.balance, statement.summary.balance);
});

test('ייצוא CSV כולל כותרות בעברית ו-BOM', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'cash' });
  const csv = call('GET', '/api/export/payments.csv');
  assert.ok(csv.__raw.startsWith('﻿'));
  assert.match(csv.__raw, /דייר/);
  assert.match(csv.__raw, /מזומן/);
  assert.match(call('GET', '/api/export/balances.csv', { period: THIS_MONTH }).__raw, /דנה כהן/);
});

test('גיבוי ושחזור משמרים את הנתונים', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'cash' });
  const backup = JSON.parse(call('GET', '/api/backup').__raw);
  call('POST', '/api/reset', {}, { confirm: 'מחק הכל' });
  assert.equal(call('GET', '/api/contracts').length, 0);
  const restored = call('POST', '/api/restore', {}, { data: backup });
  assert.equal(restored.counts.contracts, 1);
  const contracts = call('GET', '/api/contracts');
  assert.equal(contracts.length, 1);
  assert.equal(contracts[0].summary.paid, 515000);
});

test('נתוני דמו נטענים ורק על מסד ריק', () => {
  const { call } = setup();
  const res = call('POST', '/api/demo');
  assert.equal(res.contracts, 3);
  const dash = call('GET', '/api/dashboard', { period: THIS_MONTH });
  assert.equal(dash.rows.length, 3);
  assert.ok(dash.totals.expected > 0);
  assert.throws(() => call('POST', '/api/demo'), /כבר קיימים/);
});

test('אימות קלט מחזיר שגיאות ברורות', () => {
  const { call } = setup();
  const { property, contract } = baseData(call);
  assert.throws(() => call('POST', '/api/properties', {}, {}), (e) => e instanceof ApiError && e.status === 400);
  assert.throws(() => call('POST', '/api/payments', {}, { contract_id: contract.id, amount: 'הרבה' }), /סכום לא תקין/);
  assert.throws(() => call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '0' }), /גדול מאפס/);
  assert.throws(() => call('DELETE', `/api/properties/${property.id}`), /משויך לחוזה/);
  assert.throws(() => call('POST', '/api/contracts', {}, { start_date: '2026-01-01', end_date: '2025-01-01', rent: '1000' }), /מוקדם/);
  assert.throws(() => call('GET', '/api/contracts/9999'), (e) => e.status === 404);
  assert.throws(() => call('POST', '/api/charges', {}, { contract_id: contract.id, period: '2026-13', amount: '10' }), /חודש לא תקין/);
});

test('סינון תשלומים לפי אמצעי, סטטוס וחודש', () => {
  const { call } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'cash', period: TWO_AGO });
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'check', period: LAST_MONTH });
  assert.equal(call('GET', '/api/payments', { method: 'cash' }).length, 1);
  assert.equal(call('GET', '/api/payments', { status: 'pending' }).length, 1);
  assert.equal(call('GET', '/api/payments', { period: LAST_MONTH }).length, 1);
  assert.equal(call('GET', '/api/payments').length, 2);
});

test('מחיקת חוזה מוחקת גם חיובים ותשלומים', () => {
  const { call, db } = setup();
  const { contract } = baseData(call);
  call('POST', '/api/payments', {}, { contract_id: contract.id, amount: '5150', method: 'cash' });
  call('DELETE', `/api/contracts/${contract.id}`);
  assert.equal(dbLib.get(db, 'SELECT COUNT(*) AS n FROM charges').n, 0);
  assert.equal(dbLib.get(db, 'SELECT COUNT(*) AS n FROM payments').n, 0);
  assert.equal(dbLib.get(db, 'SELECT COUNT(*) AS n FROM allocations').n, 0);
});
