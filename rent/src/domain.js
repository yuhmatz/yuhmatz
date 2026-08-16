'use strict';

/* לוגיקת התחום: יצירת חיובים חודשיים, שיוך תשלומים ויתרות. */

const { run, all, get } = require('./db');
const U = require('./util');

const PAYMENT_METHODS = {
  cash: 'מזומן',
  check: 'צ׳ק',
  bank_transfer: 'העברה בנקאית',
  standing_order: 'הוראת קבע',
  bit: 'ביט',
  paybox: 'פייבוקס',
  credit_card: 'כרטיס אשראי',
  offset: 'קיזוז',
  other: 'אחר',
};

/** paid = נפרע בפועל, pending = התקבל וטרם נפרע (צ׳ק דחוי), bounced = חזר/בוטל. */
const PAYMENT_STATUSES = {
  paid: 'שולם',
  pending: 'ממתין לפירעון',
  bounced: 'חזר',
};

const CONTRACT_STATUSES = {
  active: 'פעיל',
  draft: 'טיוטה',
  ended: 'הסתיים',
};

const CHARGE_KINDS = {
  rent: 'שכר דירה',
  extra: 'תוספת קבועה',
  manual: 'חיוב חד־פעמי',
};

function normalizeMethod(m) {
  return Object.hasOwn(PAYMENT_METHODS, m) ? m : 'other';
}

function normalizeStatus(s) {
  return Object.hasOwn(PAYMENT_STATUSES, s) ? s : 'paid';
}

function normalizeContractStatus(s) {
  return Object.hasOwn(CONTRACT_STATUSES, s) ? s : 'active';
}

/** שורת חוזה מה-DB -> אובייקט עם extras מפורסר. */
function hydrateContract(row) {
  if (!row) return null;
  const extras = U.safeJSONParse(row.extras, []);
  return {
    ...row,
    prorate: !!row.prorate,
    extras: Array.isArray(extras)
      ? extras
          .filter((e) => e && typeof e === 'object')
          .map((e) => ({ label: String(e.label || 'תוספת'), amount_agorot: Math.round(Number(e.amount_agorot) || 0) }))
      : [],
  };
}

function getContract(db, id) {
  return hydrateContract(get(db, 'SELECT * FROM contracts WHERE id = ?', [id]));
}

/** התקופה האחרונה שיש לייצר עבורה חיובים: החודש הנוכחי + חודש קדימה. */
function defaultHorizon(now = new Date()) {
  return U.addMonths(U.currentPeriod(now), 1);
}

function contractFirstPeriod(contract) {
  return U.periodOf(contract.start_date);
}

function contractLastPeriod(contract) {
  return contract.end_date ? U.periodOf(contract.end_date) : null;
}

/**
 * החיובים האוטומטיים שאמורים להיווצר לחוזה בתקופה נתונה.
 * בחודש ראשון/אחרון מחושב חלק יחסי לפי ימים (אם prorate דלוק).
 */
function chargeSpecsForPeriod(contract, period) {
  const first = contractFirstPeriod(contract);
  const last = contractLastPeriod(contract);
  if (U.comparePeriods(period, first) < 0) return [];
  if (last && U.comparePeriods(period, last) > 0) return [];

  const totalDays = U.daysInPeriod(period);
  const activeDays = U.activeDaysInPeriod(period, contract.start_date, contract.end_date);
  if (activeDays <= 0) return [];
  const factor = contract.prorate ? activeDays / totalDays : 1;
  const partial = factor < 1;

  const specs = [];
  if (contract.rent_agorot > 0) {
    specs.push({
      source_key: 'rent',
      kind: 'rent',
      label: partial ? `שכר דירה (${activeDays}/${totalDays} ימים)` : 'שכר דירה',
      amount_agorot: Math.round(contract.rent_agorot * factor),
    });
  }
  contract.extras.forEach((extra, idx) => {
    if (!extra.amount_agorot) return;
    specs.push({
      source_key: `extra:${idx}`,
      kind: 'extra',
      label: partial ? `${extra.label} (${activeDays}/${totalDays} ימים)` : extra.label,
      amount_agorot: Math.round(extra.amount_agorot * factor),
    });
  });
  return specs;
}

/**
 * יוצר את החיובים החסרים לחוזה עד לתקופת האופק (כולל). אידמפוטנטי.
 * @returns {number} כמות החיובים שנוצרו
 */
function ensureCharges(db, contract, horizon = defaultHorizon()) {
  if (!contract || contract.status === 'draft') return 0;
  const first = contractFirstPeriod(contract);
  const last = contractLastPeriod(contract);
  let stop = horizon;
  if (last && U.comparePeriods(last, stop) < 0) stop = last;
  if (U.comparePeriods(first, stop) > 0) return 0;

  const now = U.nowISO();
  let created = 0;
  for (const period of U.periodsBetween(first, stop)) {
    for (const spec of chargeSpecsForPeriod(contract, period)) {
      const res = run(
        db,
        `INSERT INTO charges (contract_id, period, kind, label, amount_agorot, due_date, source_key, created_at)
         VALUES (?, ?, ?, ?, ?, ?, ?, ?)
         ON CONFLICT(contract_id, period, source_key) DO NOTHING`,
        [
          contract.id,
          period,
          spec.kind,
          spec.label,
          spec.amount_agorot,
          U.periodDueDate(period, contract.payment_day),
          spec.source_key,
          now,
        ],
      );
      created += res.changes;
    }
  }
  return created;
}

/** מייצר חיובים חסרים לכל החוזים הפעילים. */
function ensureAllCharges(db, horizon = defaultHorizon()) {
  const rows = all(db, "SELECT * FROM contracts WHERE status <> 'draft'");
  let created = 0;
  for (const row of rows) created += ensureCharges(db, hydrateContract(row), horizon);
  return created;
}

/**
 * לאחר עדכון חוזה: מעדכן חיובים אוטומטיים עתידיים (מהחודש הנוכחי והלאה)
 * שלא נערכו ידנית, ומוחק חיובים אוטומטיים שכבר לא רלוונטיים (למשל אחרי קיצור חוזה).
 */
function syncFutureCharges(db, contract, fromPeriod = U.currentPeriod()) {
  const rows = all(
    db,
    `SELECT * FROM charges
     WHERE contract_id = ? AND source_key IS NOT NULL AND manual_override = 0 AND period >= ?`,
    [contract.id, fromPeriod],
  );
  let updated = 0;
  let removed = 0;
  for (const row of rows) {
    const specs = chargeSpecsForPeriod(contract, row.period);
    const spec = specs.find((s) => s.source_key === row.source_key);
    const paid = get(
      db,
      `SELECT COALESCE(SUM(a.amount_agorot), 0) AS total
       FROM allocations a JOIN payments p ON p.id = a.payment_id
       WHERE a.period = ? AND p.contract_id = ?`,
      [row.period, contract.id],
    ).total;
    if (!spec) {
      // אין יותר חיוב כזה בתקופה הזו – מוחקים רק אם אין תשלומים משויכים.
      if (!paid) {
        run(db, 'DELETE FROM charges WHERE id = ?', [row.id]);
        removed += 1;
      }
      continue;
    }
    if (spec.amount_agorot !== row.amount_agorot || spec.label !== row.label) {
      run(db, 'UPDATE charges SET amount_agorot = ?, label = ? WHERE id = ?', [spec.amount_agorot, spec.label, row.id]);
      updated += 1;
    }
    const due = U.periodDueDate(row.period, contract.payment_day);
    if (due !== row.due_date) run(db, 'UPDATE charges SET due_date = ? WHERE id = ?', [due, row.id]);
  }
  const created = ensureCharges(db, contract);
  return { updated, removed, created };
}

/** סיכום לפי תקופה עבור חוזה. */
function contractPeriods(db, contractId, today = U.todayISO()) {
  const charges = all(
    db,
    `SELECT period, MIN(due_date) AS due_date, SUM(amount_agorot) AS charged
     FROM charges WHERE contract_id = ? AND canceled = 0 GROUP BY period`,
    [contractId],
  );
  const payments = all(
    db,
    `SELECT a.period AS period, p.status AS status, SUM(a.amount_agorot) AS total
     FROM allocations a JOIN payments p ON p.id = a.payment_id
     WHERE p.contract_id = ? GROUP BY a.period, p.status`,
    [contractId],
  );

  const notices = new Map(
    all(db, 'SELECT period, note, promised_date FROM notices WHERE contract_id = ?', [contractId]).map((n) => [n.period, n]),
  );

  const map = new Map();
  const touch = (period) => {
    if (!map.has(period)) {
      map.set(period, { period, due_date: U.periodDueDate(period, 1), charged: 0, paid: 0, pending: 0, bounced: 0 });
    }
    return map.get(period);
  };
  for (const c of charges) {
    const row = touch(c.period);
    row.charged = c.charged;
    row.due_date = c.due_date;
  }
  for (const p of payments) {
    const row = touch(p.period);
    if (p.status === 'paid') row.paid += p.total;
    else if (p.status === 'pending') row.pending += p.total;
    else row.bounced += p.total;
  }

  const out = [...map.values()].sort((a, b) => U.comparePeriods(a.period, b.period));
  for (const row of out) {
    row.balance = row.charged - row.paid;
    row.label = U.periodLabel(row.period);
    const notice = notices.get(row.period);
    row.notice = notice ? { note: notice.note, promised_date: notice.promised_date } : null;
    // סכום שחסר בפועל, אחרי שמנכים צ׳קים/תשלומים שממתינים לפירעון
    const missing = row.balance - row.pending;
    if (row.balance <= 0) row.state = row.charged === 0 && row.paid > 0 ? 'credit' : 'paid';
    else if (row.due_date < today && missing > 0) row.state = row.notice ? 'notified' : 'overdue';
    else if (row.pending > 0) row.state = 'pending';
    else if (row.paid > 0) row.state = 'partial';
    else row.state = 'open';
  }
  return out;
}

/** סכומי-על לחוזה: סה״כ חויב/שולם/ממתין/יתרה/פיגור/יתרת זכות. */
function contractSummary(db, contractId, today = U.todayISO()) {
  const periods = contractPeriods(db, contractId, today);
  const totals = { charged: 0, paid: 0, pending: 0, balance: 0, overdue: 0, notified: 0 };
  for (const p of periods) {
    totals.charged += p.charged;
    totals.paid += p.paid;
    totals.pending += p.pending;
    totals.balance += p.balance;
    // פיגור = מה שהיה אמור להתקבל, לא התקבל, ואין צ׳ק שממתין לפירעון שמכסה אותו
    if (p.due_date <= today) {
      const late = Math.max(0, p.balance - p.pending);
      totals.overdue += late;
      if (p.notice) totals.notified += late;
    }
  }
  totals.unallocated = unallocatedTotal(db, contractId);
  return { totals, periods };
}

/** סכום תשלומים שנרשמו ולא שויכו לחודש (מקדמה/יתרת זכות). */
function unallocatedTotal(db, contractId) {
  const row = get(
    db,
    `SELECT
       (SELECT COALESCE(SUM(amount_agorot), 0) FROM payments
         WHERE contract_id = ? AND status <> 'bounced')
       -
       (SELECT COALESCE(SUM(a.amount_agorot), 0) FROM allocations a
          JOIN payments p ON p.id = a.payment_id
         WHERE p.contract_id = ? AND p.status <> 'bounced') AS total`,
    [contractId, contractId],
  );
  return Math.max(0, row ? row.total : 0);
}

/**
 * פריסה אוטומטית של תשלום על החודשים הפתוחים הישנים ביותר.
 * @returns {{period:string, amount_agorot:number}[]}
 */
function autoAllocate(db, contractId, amount, opts = {}) {
  const { excludePaymentId = null, today = U.todayISO() } = opts;
  let periods = contractPeriods(db, contractId, today);
  if (excludePaymentId) {
    // מתעלמים מהשיוכים של התשלום שנערך כרגע
    const own = all(db, 'SELECT period, amount_agorot FROM allocations WHERE payment_id = ?', [excludePaymentId]);
    const paymentRow = get(db, 'SELECT status FROM payments WHERE id = ?', [excludePaymentId]);
    if (paymentRow && paymentRow.status !== 'bounced') {
      const byPeriod = new Map(periods.map((p) => [p.period, p]));
      for (const a of own) {
        const row = byPeriod.get(a.period);
        if (row) {
          if (paymentRow.status === 'paid') row.paid -= a.amount_agorot;
          else row.pending -= a.amount_agorot;
          row.balance = row.charged - row.paid;
        }
      }
      periods = [...byPeriod.values()];
    }
  }
  const out = [];
  let left = Math.round(amount);
  for (const p of periods.sort((a, b) => U.comparePeriods(a.period, b.period))) {
    if (left <= 0) break;
    const open = p.charged - p.paid - p.pending;
    if (open <= 0) continue;
    const take = Math.min(open, left);
    out.push({ period: p.period, amount_agorot: take });
    left -= take;
  }
  return out;
}

function replaceAllocations(db, paymentId, allocations) {
  run(db, 'DELETE FROM allocations WHERE payment_id = ?', [paymentId]);
  for (const a of allocations) {
    if (!U.isValidPeriod(a.period) || !a.amount_agorot) continue;
    run(db, 'INSERT INTO allocations (payment_id, period, amount_agorot) VALUES (?, ?, ?)', [
      paymentId,
      a.period,
      Math.round(a.amount_agorot),
    ]);
  }
}

/** תמונת מצב חודשית לכל החוזים. */
function dashboard(db, period, today = U.todayISO()) {
  const contracts = all(
    db,
    `SELECT c.*, t.name AS tenant_name, p.name AS property_name, p.address AS property_address
     FROM contracts c
     LEFT JOIN tenants t ON t.id = c.tenant_id
     LEFT JOIN properties p ON p.id = c.property_id
     WHERE c.status <> 'draft'
     ORDER BY t.name COLLATE NOCASE`,
  );

  const rows = [];
  const totals = { expected: 0, paid: 0, pending: 0, outstanding: 0, overdue_all: 0, notified_all: 0, credit: 0 };

  for (const raw of contracts) {
    const contract = hydrateContract(raw);
    const summary = contractSummary(db, contract.id, today);
    const month = summary.periods.find((p) => p.period === period) || {
      period,
      due_date: U.periodDueDate(period, contract.payment_day),
      charged: 0,
      paid: 0,
      pending: 0,
      balance: 0,
      state: 'none',
    };
    const methodsUsed = all(
      db,
      `SELECT p.method AS method, SUM(a.amount_agorot) AS total, p.status AS status
       FROM allocations a JOIN payments p ON p.id = a.payment_id
       WHERE p.contract_id = ? AND a.period = ? GROUP BY p.method, p.status`,
      [contract.id, period],
    );
    const startsAfter = U.comparePeriods(period, U.periodOf(contract.start_date)) < 0;
    const endedBefore = contract.end_date && U.comparePeriods(period, U.periodOf(contract.end_date)) > 0;
    rows.push({
      active_in_period: !startsAfter && !endedBefore,
      period_note: endedBefore ? `הסתיים ב-${U.periodLabel(U.periodOf(contract.end_date))}` : startsAfter ? `מתחיל ב-${U.periodLabel(U.periodOf(contract.start_date))}` : '',
      contract_id: contract.id,
      tenant_id: contract.tenant_id,
      tenant_name: raw.tenant_name || '—',
      property_name: raw.property_name || '—',
      property_address: raw.property_address || '',
      title: contract.title,
      status: contract.status,
      rent_agorot: contract.rent_agorot,
      default_method: contract.default_method,
      payment_day: contract.payment_day,
      month: { ...month, label: U.periodLabel(period) },
      methods: methodsUsed,
      totals: summary.totals,
    });
    totals.expected += month.charged;
    totals.paid += month.paid;
    totals.pending += month.pending;
    totals.outstanding += Math.max(0, month.charged - month.paid);
    totals.overdue_all += summary.totals.overdue;
    totals.notified_all += summary.totals.notified;
    totals.credit += summary.totals.unallocated;
  }

  const checks = all(
    db,
    `SELECT p.*, t.name AS tenant_name
     FROM payments p
     LEFT JOIN contracts c ON c.id = p.contract_id
     LEFT JOIN tenants t ON t.id = c.tenant_id
     WHERE p.method = 'check' AND p.status = 'pending'
     ORDER BY COALESCE(p.due_date, p.paid_date)`,
  );

  return { period, period_label: U.periodLabel(period), today, totals, rows, checks };
}

module.exports = {
  PAYMENT_METHODS,
  PAYMENT_STATUSES,
  CONTRACT_STATUSES,
  CHARGE_KINDS,
  normalizeMethod,
  normalizeStatus,
  normalizeContractStatus,
  hydrateContract,
  getContract,
  defaultHorizon,
  chargeSpecsForPeriod,
  ensureCharges,
  ensureAllCharges,
  syncFutureCharges,
  contractPeriods,
  contractSummary,
  unallocatedTotal,
  autoAllocate,
  replaceAllocations,
  dashboard,
};
