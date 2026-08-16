'use strict';

/* עזרי כסף, תאריכים ותקופות. כל סכומי הכסף נשמרים באגורות (מספר שלם). */

const HE_MONTHS = [
  'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
  'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר',
];

/** "4,500" / "₪4500.50" / 4500 -> אגורות. מחזיר null אם לא מספר. */
function parseMoney(input) {
  if (input === null || input === undefined || input === '') return null;
  if (typeof input === 'number') {
    if (!Number.isFinite(input)) return null;
    return Math.round(input * 100);
  }
  const cleaned = String(input)
    .replace(/[₪\s,‎‏]/g, '')
    .replace(/^\+/, '');
  if (!/^-?\d*(\.\d+)?$/.test(cleaned) || cleaned === '' || cleaned === '-') return null;
  return Math.round(parseFloat(cleaned) * 100);
}

function formatMoney(agorot) {
  const n = (Number(agorot) || 0) / 100;
  return '₪' + n.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

/** תאריך מקומי כ-YYYY-MM-DD */
function todayISO(now = new Date()) {
  return `${now.getFullYear()}-${pad2(now.getMonth() + 1)}-${pad2(now.getDate())}`;
}

function isValidDate(s) {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const [y, m, d] = s.split('-').map(Number);
  if (m < 1 || m > 12) return false;
  return d >= 1 && d <= daysInMonthYM(y, m);
}

function isValidPeriod(s) {
  return typeof s === 'string' && /^\d{4}-(0[1-9]|1[0-2])$/.test(s);
}

function periodOf(dateISO) {
  return String(dateISO).slice(0, 7);
}

function currentPeriod(now = new Date()) {
  return periodOf(todayISO(now));
}

function daysInMonthYM(year, month) {
  return new Date(year, month, 0).getDate();
}

function daysInPeriod(period) {
  const [y, m] = period.split('-').map(Number);
  return daysInMonthYM(y, m);
}

function addMonths(period, delta) {
  const [y, m] = period.split('-').map(Number);
  const total = y * 12 + (m - 1) + delta;
  const ny = Math.floor(total / 12);
  const nm = (total % 12 + 12) % 12 + 1;
  return `${ny}-${pad2(nm)}`;
}

function comparePeriods(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** רשימת תקופות כולל הקצוות. מוגבל ל-600 חודשים כהגנה. */
function periodsBetween(from, to) {
  const out = [];
  let p = from;
  let guard = 0;
  while (comparePeriods(p, to) <= 0 && guard++ < 600) {
    out.push(p);
    p = addMonths(p, 1);
  }
  return out;
}

/** יום החיוב בתוך התקופה, עם קיצוץ ליום האחרון בחודש (למשל 31 בפברואר). */
function periodDueDate(period, day) {
  const d = Math.min(Math.max(Number(day) || 1, 1), daysInPeriod(period));
  return `${period}-${pad2(d)}`;
}

function periodLabel(period) {
  if (!isValidPeriod(period)) return period || '';
  const [y, m] = period.split('-').map(Number);
  return `${HE_MONTHS[m - 1]} ${y}`;
}

function dayOfMonth(dateISO) {
  return Number(String(dateISO).slice(8, 10));
}

/** מספר הימים בתקופה שהחוזה פעיל בהם (לחישוב יחסי בחודש ראשון/אחרון). */
function activeDaysInPeriod(period, startDate, endDate) {
  const total = daysInPeriod(period);
  let first = 1;
  let last = total;
  if (startDate && periodOf(startDate) === period) first = dayOfMonth(startDate);
  if (endDate && periodOf(endDate) === period) last = dayOfMonth(endDate);
  if (startDate && periodOf(startDate) > period) return 0;
  if (endDate && periodOf(endDate) < period) return 0;
  return Math.max(0, last - first + 1);
}

function clampInt(value, min, max, fallback) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.min(max, Math.max(min, Math.round(n)));
}

function safeJSONParse(text, fallback) {
  try {
    const v = JSON.parse(text);
    return v === null || v === undefined ? fallback : v;
  } catch {
    return fallback;
  }
}

function nowISO() {
  const d = new Date();
  return `${todayISO(d)} ${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;
}

module.exports = {
  HE_MONTHS,
  parseMoney,
  formatMoney,
  pad2,
  todayISO,
  nowISO,
  isValidDate,
  isValidPeriod,
  periodOf,
  currentPeriod,
  daysInPeriod,
  daysInMonthYM,
  addMonths,
  comparePeriods,
  periodsBetween,
  periodDueDate,
  periodLabel,
  dayOfMonth,
  activeDaysInPeriod,
  clampInt,
  safeJSONParse,
};
