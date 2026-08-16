'use strict';

const test = require('node:test');
const assert = require('node:assert');
const U = require('../src/util');

test('parseMoney מקבל פורמטים שונים', () => {
  assert.equal(U.parseMoney('4500'), 450000);
  assert.equal(U.parseMoney('4,500.50'), 450050);
  assert.equal(U.parseMoney('₪ 4500'), 450000);
  assert.equal(U.parseMoney(4500), 450000);
  assert.equal(U.parseMoney('-250'), -25000);
  assert.equal(U.parseMoney('abc'), null);
  assert.equal(U.parseMoney(''), null);
});

test('חישובי תקופות', () => {
  assert.equal(U.addMonths('2026-01', 1), '2026-02');
  assert.equal(U.addMonths('2026-12', 1), '2027-01');
  assert.equal(U.addMonths('2026-01', -1), '2025-12');
  assert.deepEqual(U.periodsBetween('2026-11', '2027-02'), ['2026-11', '2026-12', '2027-01', '2027-02']);
  assert.equal(U.periodsBetween('2026-05', '2026-01').length, 0);
});

test('תאריך יעד נחתך ליום האחרון בחודש', () => {
  assert.equal(U.periodDueDate('2026-02', 31), '2026-02-28');
  assert.equal(U.periodDueDate('2024-02', 31), '2024-02-29');
  assert.equal(U.periodDueDate('2026-03', 10), '2026-03-10');
  assert.equal(U.periodDueDate('2026-03', 0), '2026-03-01');
});

test('ימים פעילים בתקופה לצורך חישוב יחסי', () => {
  assert.equal(U.activeDaysInPeriod('2026-03', '2026-03-10', null), 22);
  assert.equal(U.activeDaysInPeriod('2026-04', '2026-03-10', null), 30);
  assert.equal(U.activeDaysInPeriod('2026-06', '2026-01-01', '2026-06-15'), 15);
  assert.equal(U.activeDaysInPeriod('2026-07', '2026-01-01', '2026-06-15'), 0);
  assert.equal(U.activeDaysInPeriod('2025-12', '2026-01-01', null), 0);
});

test('אימות תאריכים וחודשים', () => {
  assert.ok(U.isValidDate('2026-02-28'));
  assert.ok(!U.isValidDate('2026-02-30'));
  assert.ok(!U.isValidDate('2026-13-01'));
  assert.ok(U.isValidPeriod('2026-08'));
  assert.ok(!U.isValidPeriod('2026-13'));
});
