'use strict';

/* כל נקודות ה-API של המערכת. */

const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const { run, all, get, tx, getSetting, setSetting } = require('./db');
const U = require('./util');
const D = require('./domain');
const S = require('./search');
const { extractText } = require('./extract');

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const bad = (msg) => {
  throw new ApiError(400, msg);
};
const notFound = (msg = 'לא נמצא') => {
  throw new ApiError(404, msg);
};

/* ---------- עזרי קלט ---------- */

function str(body, key, { max = 4000, required = false, fallback = '' } = {}) {
  const v = body[key];
  if (v === undefined || v === null || v === '') {
    if (required) bad(`שדה חובה חסר: ${key}`);
    return fallback;
  }
  const s = String(v).trim();
  if (s.length > max) bad(`השדה ${key} ארוך מדי`);
  return s;
}

function money(body, key, fallback = 0) {
  if (body[`${key}_agorot`] !== undefined && body[`${key}_agorot`] !== null && body[`${key}_agorot`] !== '') {
    const n = Number(body[`${key}_agorot`]);
    if (!Number.isFinite(n)) bad(`סכום לא תקין: ${key}`);
    return Math.round(n);
  }
  if (body[key] === undefined || body[key] === null || body[key] === '') return fallback;
  const parsed = U.parseMoney(body[key]);
  if (parsed === null) bad(`סכום לא תקין: ${key}`);
  return parsed;
}

function dateField(body, key, { required = false, fallback = null } = {}) {
  const v = body[key];
  if (v === undefined || v === null || v === '') {
    if (required) bad(`חסר תאריך: ${key}`);
    return fallback;
  }
  const s = String(v).slice(0, 10);
  if (!U.isValidDate(s)) bad(`תאריך לא תקין: ${key}`);
  return s;
}

function periodField(body, key, { required = false, fallback = null } = {}) {
  const v = body[key];
  if (v === undefined || v === null || v === '') {
    if (required) bad(`חסר חודש: ${key}`);
    return fallback;
  }
  const s = String(v).slice(0, 7);
  if (!U.isValidPeriod(s)) bad(`חודש לא תקין (YYYY-MM): ${key}`);
  return s;
}

function refId(db, table, value, { required = false } = {}) {
  if (value === undefined || value === null || value === '') {
    if (required) bad('חסר שיוך');
    return null;
  }
  const id = Number(value);
  if (!Number.isInteger(id) || id <= 0) bad('מזהה לא תקין');
  const row = get(db, `SELECT id FROM ${table} WHERE id = ?`, [id]);
  if (!row) notFound(`הרשומה המשויכת (${table}) לא נמצאה`);
  return id;
}

function csvEscape(value) {
  const s = value === null || value === undefined ? '' : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function toCSV(headers, rows) {
  const lines = [headers.map(csvEscape).join(',')];
  for (const row of rows) lines.push(row.map(csvEscape).join(','));
  return '﻿' + lines.join('\r\n') + '\r\n';
}

const shekels = (agorot) => (Number(agorot || 0) / 100).toFixed(2);

/* ---------- שאילתות משותפות ---------- */

const CONTRACT_SELECT = `
  SELECT c.*, t.name AS tenant_name, t.phone AS tenant_phone, t.email AS tenant_email,
         p.name AS property_name, p.address AS property_address, p.city AS property_city, p.unit AS property_unit
  FROM contracts c
  LEFT JOIN tenants t ON t.id = c.tenant_id
  LEFT JOIN properties p ON p.id = c.property_id`;

function contractRow(db, id) {
  const row = get(db, `${CONTRACT_SELECT} WHERE c.id = ?`, [id]);
  if (!row) notFound('החוזה לא נמצא');
  return row;
}

function contractLabel(row) {
  const place = row.property_name || row.property_address || 'נכס';
  return `${row.tenant_name || 'ללא דייר'} · ${place}`;
}

function paymentsForContract(db, contractId) {
  const rows = all(db, 'SELECT * FROM payments WHERE contract_id = ? ORDER BY paid_date DESC, id DESC', [contractId]);
  return rows.map((p) => ({
    ...p,
    allocations: all(db, 'SELECT period, amount_agorot FROM allocations WHERE payment_id = ? ORDER BY period', [p.id]),
  }));
}

/* ---------- טיפול בתשלומים ---------- */

function writePayment(db, id, body, { isNew }) {
  const contractId = refId(db, 'contracts', body.contract_id, { required: isNew });
  const amount = money(body, 'amount');
  if (!Number.isFinite(amount) || amount <= 0) bad('יש להזין סכום גדול מאפס');
  const method = D.normalizeMethod(str(body, 'method', { fallback: 'bank_transfer' }));
  const status = D.normalizeStatus(str(body, 'status', { fallback: method === 'check' ? 'pending' : 'paid' }));
  const paidDate = dateField(body, 'paid_date', { fallback: U.todayISO() });
  const dueDate = dateField(body, 'due_date');
  const fields = {
    amount_agorot: amount,
    method,
    status,
    paid_date: paidDate,
    due_date: dueDate,
    reference: str(body, 'reference', { max: 200 }),
    bank: str(body, 'bank', { max: 100 }),
    branch: str(body, 'branch', { max: 50 }),
    account: str(body, 'account', { max: 60 }),
    check_number: str(body, 'check_number', { max: 60 }),
    notes: str(body, 'notes', { max: 2000 }),
  };

  let paymentId = id;
  if (isNew) {
    const res = run(
      db,
      `INSERT INTO payments (contract_id, amount_agorot, method, status, paid_date, due_date, reference, bank,
                             branch, account, check_number, notes, created_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      [
        contractId,
        fields.amount_agorot,
        fields.method,
        fields.status,
        fields.paid_date,
        fields.due_date,
        fields.reference,
        fields.bank,
        fields.branch,
        fields.account,
        fields.check_number,
        fields.notes,
        U.nowISO(),
      ],
    );
    paymentId = res.lastInsertRowid;
  } else {
    run(
      db,
      `UPDATE payments SET amount_agorot=?, method=?, status=?, paid_date=?, due_date=?, reference=?, bank=?,
                           branch=?, account=?, check_number=?, notes=? WHERE id=?`,
      [
        fields.amount_agorot,
        fields.method,
        fields.status,
        fields.paid_date,
        fields.due_date,
        fields.reference,
        fields.bank,
        fields.branch,
        fields.account,
        fields.check_number,
        fields.notes,
        paymentId,
      ],
    );
  }

  const targetContract = isNew ? contractId : get(db, 'SELECT contract_id FROM payments WHERE id = ?', [paymentId]).contract_id;

  // שיוך לחודשים
  let allocations = null;
  if (Array.isArray(body.allocations)) {
    allocations = body.allocations
      .map((a) => ({ period: periodField(a, 'period', { required: true }), amount_agorot: money(a, 'amount') }))
      .filter((a) => a.amount_agorot > 0);
    const sum = allocations.reduce((acc, a) => acc + a.amount_agorot, 0);
    if (sum > amount) bad('סכום השיוך לחודשים גדול מסכום התשלום');
  } else if (body.period) {
    allocations = [{ period: periodField(body, 'period', { required: true }), amount_agorot: amount }];
  } else if (body.auto_allocate !== false) {
    allocations = D.autoAllocate(db, targetContract, amount, { excludePaymentId: isNew ? null : paymentId });
  }
  if (allocations) D.replaceAllocations(db, paymentId, allocations);
  return paymentId;
}

/* ---------- מסמכי חיפוש ---------- */

function searchDocsFor(db) {
  const contracts = all(db, `${CONTRACT_SELECT} ORDER BY c.id`);
  const files = all(db, 'SELECT id, contract_id, filename, text FROM contract_files');
  const byContract = new Map();
  for (const f of files) {
    if (!byContract.has(f.contract_id)) byContract.set(f.contract_id, []);
    byContract.get(f.contract_id).push(f);
  }
  return contracts.map((c) => {
    const fields = [
      { key: 'meta', label: 'פרטי החוזה', weight: 3, text: [c.title, c.tenant_name, c.property_name, c.property_address, c.property_city, c.property_unit, c.tenant_phone, c.tenant_email].filter(Boolean).join(' | ') },
      { key: 'notes', label: 'הערות', weight: 2, text: c.notes },
      { key: 'text', label: 'נוסח החוזה', weight: 1, text: c.contract_text },
    ];
    for (const f of byContract.get(c.id) || []) {
      fields.push({ key: `file:${f.id}`, label: `קובץ: ${f.filename}`, weight: 1, text: f.text });
    }
    return {
      contract_id: c.id,
      title: c.title || contractLabel(c),
      tenant_name: c.tenant_name || '',
      property_name: c.property_name || '',
      status: c.status,
      start_date: c.start_date,
      end_date: c.end_date,
      fields,
    };
  });
}

/* ---------- נתוני דמו ---------- */

function seedDemo(db) {
  const now = U.nowISO();
  const today = U.todayISO();
  const thisMonth = U.currentPeriod();
  const startA = `${U.addMonths(thisMonth, -7)}-01`;
  const startB = `${U.addMonths(thisMonth, -3)}-15`;
  const startC = `${U.addMonths(thisMonth, -14)}-01`;

  const props = [
    ['דירה ברחוב הרצל 12', 'הרצל 12, דירה 4', 'תל אביב', '4'],
    ['דירת גן ביסמין', 'יסמין 8', 'רעננה', ''],
    ['חנות במרכז המסחרי', 'ויצמן 30, חנות 2', 'כפר סבא', '2'],
  ].map(([name, address, city, unit]) => {
    const res = run(db, 'INSERT INTO properties (name,address,city,unit,notes,created_at) VALUES (?,?,?,?,?,?)', [name, address, city, unit, '', now]);
    return res.lastInsertRowid;
  });

  const tenants = [
    ['דנה כהן', '052-1112233', 'dana@example.com', '011223344'],
    ['משה לוי', '054-9998877', 'moshe@example.com', '055667788'],
    ['שרה אברהם', '053-4445566', 'sara@example.com', '099887766'],
  ].map(([name, phone, email, nid]) => {
    const res = run(db, 'INSERT INTO tenants (name,phone,email,national_id,notes,created_at) VALUES (?,?,?,?,?,?)', [name, phone, email, nid, '', now]);
    return res.lastInsertRowid;
  });

  const contractText = (tenant, rent, day) => `הסכם שכירות בלתי מוגנת

שנערך ונחתם ב${today} בין המשכיר לבין ${tenant} (להלן: "השוכר").

1. תקופת השכירות: 12 חודשים, עם אופציה להארכה ב-12 חודשים נוספים בהודעה מראש של 60 יום.
2. דמי השכירות: ${rent} ש"ח לחודש, ישולמו עד ה-${day} לכל חודש קלנדרי מראש.
3. אמצעי תשלום: העברה בנקאית לחשבון המשכיר או 12 צ'קים דחויים מראש.
4. הצמדה: דמי השכירות יוצמדו למדד המחירים לצרכן, עדכון אחת לשנה.
5. ביטחונות: שטר חוב בסך שלושה חודשי שכירות וערבות אישית של ערב אחד.
6. תשלומי חובה: ארנונה, מים, חשמל וועד בית יחולו על השוכר.
7. תיקונים: תיקוני בלאי סביר על המשכיר; נזק שנגרם ברשלנות השוכר – על השוכר.
8. איסור העברת זכויות: אין להשכיר בשכירות משנה ללא הסכמה בכתב.
9. פינוי: השוכר יפנה את המושכר בתום התקופה כשהוא נקי ותקין.
10. הודעות: כל הודעה תישלח בדואר רשום או בדוא"ל לכתובות שבמבוא.`;

  const contracts = [
    { property_id: props[0], tenant_id: tenants[0], title: 'שכירות דירה – הרצל 12', start_date: startA, rent: 550000, day: 1, method: 'bank_transfer', extras: [{ label: 'ועד בית', amount_agorot: 15000 }] },
    { property_id: props[1], tenant_id: tenants[1], title: 'שכירות דירת גן – רעננה', start_date: startB, rent: 720000, day: 10, method: 'check', extras: [] },
    { property_id: props[2], tenant_id: tenants[2], title: 'שכירות חנות – כפר סבא', start_date: startC, rent: 980000, day: 5, method: 'standing_order', months: 24, extras: [{ label: 'דמי ניהול', amount_agorot: 45000 }] },
  ].map((c) => {
    const res = run(
      db,
      `INSERT INTO contracts (property_id,tenant_id,title,start_date,end_date,rent_agorot,payment_day,default_method,
                              deposit_agorot,deposit_kind,extras,prorate,status,notes,contract_text,created_at,updated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      [
        c.property_id,
        c.tenant_id,
        c.title,
        c.start_date,
        `${U.addMonths(U.periodOf(c.start_date), c.months || 12)}-${c.start_date.slice(8, 10)}`,
        c.rent,
        c.day,
        c.method,
        c.rent * 2,
        'שטר חוב',
        JSON.stringify(c.extras),
        1,
        'active',
        '',
        contractText(get(db, 'SELECT name FROM tenants WHERE id = ?', [c.tenant_id]).name, c.rent / 100, c.day),
        now,
        now,
      ],
    );
    return { id: res.lastInsertRowid, ...c };
  });

  for (const c of contracts) D.ensureCharges(db, D.getContract(db, c.id));

  // תשלומים לדוגמה: חודשים קודמים שולמו, החודש הנוכחי חלקי
  for (const c of contracts) {
    const periods = D.contractPeriods(db, c.id);
    for (const p of periods) {
      if (p.period >= thisMonth) continue;
      const method = c.method;
      run(
        db,
        `INSERT INTO payments (contract_id, amount_agorot, method, status, paid_date, due_date, reference, bank, branch,
                               account, check_number, notes, created_at)
         VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)`,
        [
          c.id,
          p.charged,
          method,
          'paid',
          p.due_date,
          method === 'check' ? p.due_date : null,
          method === 'bank_transfer' ? `אסמכתא ${Math.floor(100000 + Math.random() * 899999)}` : '',
          method === 'bank_transfer' ? 'לאומי' : '',
          method === 'bank_transfer' ? '941' : '',
          '',
          method === 'check' ? String(1000 + periods.indexOf(p)) : '',
          '',
          now,
        ],
      );
      const paymentId = get(db, 'SELECT last_insert_rowid() AS id').id;
      run(db, 'INSERT INTO allocations (payment_id, period, amount_agorot) VALUES (?,?,?)', [paymentId, p.period, p.charged]);
    }
  }

  // דנה שילמה חלקית החודש; שרה טרם שילמה; משה מסר צ׳ק דחוי
  const dana = contracts[0];
  const danaMonth = D.contractPeriods(db, dana.id).find((p) => p.period === thisMonth);
  if (danaMonth) {
    run(
      db,
      `INSERT INTO payments (contract_id, amount_agorot, method, status, paid_date, reference, notes, created_at)
       VALUES (?,?,?,?,?,?,?,?)`,
      [dana.id, Math.round(danaMonth.charged * 0.6), 'bit', 'paid', today, '', 'תשלום חלקי – היתרה סוכם עד סוף החודש', now],
    );
    const pid = get(db, 'SELECT last_insert_rowid() AS id').id;
    run(db, 'INSERT INTO allocations (payment_id, period, amount_agorot) VALUES (?,?,?)', [pid, thisMonth, Math.round(danaMonth.charged * 0.6)]);
  }
  const moshe = contracts[1];
  const mosheMonth = D.contractPeriods(db, moshe.id).find((p) => p.period === thisMonth);
  if (mosheMonth) {
    run(
      db,
      `INSERT INTO payments (contract_id, amount_agorot, method, status, paid_date, due_date, check_number, bank, notes, created_at)
       VALUES (?,?,?,?,?,?,?,?,?,?)`,
      [moshe.id, mosheMonth.charged, 'check', 'pending', today, mosheMonth.due_date, '1043', 'הפועלים', 'צ׳ק דחוי שנמסר מראש', now],
    );
    const pid = get(db, 'SELECT last_insert_rowid() AS id').id;
    run(db, 'INSERT INTO allocations (payment_id, period, amount_agorot) VALUES (?,?,?)', [pid, thisMonth, mosheMonth.charged]);
  }
  return { properties: props.length, tenants: tenants.length, contracts: contracts.length };
}

/* ---------- ניתוב ---------- */

function createRouter(ctx) {
  const { db, uploadsDir } = ctx;

  const routes = [];
  const on = (method, pattern, handler) => {
    const keys = [];
    const re = new RegExp(
      '^' +
        pattern.replace(/:([a-zA-Z_]+)/g, (_, k) => {
          keys.push(k);
          return '([^/]+)';
        }) +
        '$',
    );
    routes.push({ method, re, keys, handler });
  };

  /* --- אתחול ותצוגה כללית --- */

  on('GET', '/api/bootstrap', () => {
    D.ensureAllCharges(db);
    return {
      today: U.todayISO(),
      current_period: U.currentPeriod(),
      methods: D.PAYMENT_METHODS,
      payment_statuses: D.PAYMENT_STATUSES,
      contract_statuses: D.CONTRACT_STATUSES,
      charge_kinds: D.CHARGE_KINDS,
      owner_name: getSetting(db, 'owner_name', ''),
      properties: all(db, 'SELECT * FROM properties ORDER BY name COLLATE NOCASE'),
      tenants: all(db, 'SELECT * FROM tenants ORDER BY name COLLATE NOCASE'),
      contracts: all(db, `${CONTRACT_SELECT} ORDER BY c.status, t.name COLLATE NOCASE`).map((c) => ({
        ...D.hydrateContract(c),
        label: contractLabel(c),
      })),
    };
  });

  on('GET', '/api/dashboard', (_p, query) => {
    D.ensureAllCharges(db);
    const period = U.isValidPeriod(query.period) ? query.period : U.currentPeriod();
    return D.dashboard(db, period);
  });

  on('POST', '/api/settings', (_p, _q, body) => {
    if (body.owner_name !== undefined) setSetting(db, 'owner_name', str(body, 'owner_name', { max: 120 }));
    return { ok: true };
  });

  /* --- נכסים --- */

  on('GET', '/api/properties', () => all(db, 'SELECT * FROM properties ORDER BY name COLLATE NOCASE'));

  on('POST', '/api/properties', (_p, _q, body) => {
    const res = run(db, 'INSERT INTO properties (name,address,city,unit,notes,created_at) VALUES (?,?,?,?,?,?)', [
      str(body, 'name', { required: true, max: 200 }),
      str(body, 'address', { max: 300 }),
      str(body, 'city', { max: 100 }),
      str(body, 'unit', { max: 50 }),
      str(body, 'notes', { max: 2000 }),
      U.nowISO(),
    ]);
    return get(db, 'SELECT * FROM properties WHERE id = ?', [res.lastInsertRowid]);
  });

  on('PUT', '/api/properties/:id', (params, _q, body) => {
    const id = refId(db, 'properties', params.id, { required: true });
    run(db, 'UPDATE properties SET name=?, address=?, city=?, unit=?, notes=? WHERE id=?', [
      str(body, 'name', { required: true, max: 200 }),
      str(body, 'address', { max: 300 }),
      str(body, 'city', { max: 100 }),
      str(body, 'unit', { max: 50 }),
      str(body, 'notes', { max: 2000 }),
      id,
    ]);
    return get(db, 'SELECT * FROM properties WHERE id = ?', [id]);
  });

  on('DELETE', '/api/properties/:id', (params) => {
    const id = refId(db, 'properties', params.id, { required: true });
    const used = get(db, 'SELECT COUNT(*) AS n FROM contracts WHERE property_id = ?', [id]).n;
    if (used) bad('לא ניתן למחוק נכס שמשויך לחוזה. יש למחוק/לשנות קודם את החוזים.');
    run(db, 'DELETE FROM properties WHERE id = ?', [id]);
    return { ok: true };
  });

  /* --- דיירים --- */

  on('GET', '/api/tenants', () => all(db, 'SELECT * FROM tenants ORDER BY name COLLATE NOCASE'));

  on('POST', '/api/tenants', (_p, _q, body) => {
    const res = run(db, 'INSERT INTO tenants (name,phone,email,national_id,notes,created_at) VALUES (?,?,?,?,?,?)', [
      str(body, 'name', { required: true, max: 200 }),
      str(body, 'phone', { max: 60 }),
      str(body, 'email', { max: 200 }),
      str(body, 'national_id', { max: 40 }),
      str(body, 'notes', { max: 2000 }),
      U.nowISO(),
    ]);
    return get(db, 'SELECT * FROM tenants WHERE id = ?', [res.lastInsertRowid]);
  });

  on('PUT', '/api/tenants/:id', (params, _q, body) => {
    const id = refId(db, 'tenants', params.id, { required: true });
    run(db, 'UPDATE tenants SET name=?, phone=?, email=?, national_id=?, notes=? WHERE id=?', [
      str(body, 'name', { required: true, max: 200 }),
      str(body, 'phone', { max: 60 }),
      str(body, 'email', { max: 200 }),
      str(body, 'national_id', { max: 40 }),
      str(body, 'notes', { max: 2000 }),
      id,
    ]);
    return get(db, 'SELECT * FROM tenants WHERE id = ?', [id]);
  });

  on('DELETE', '/api/tenants/:id', (params) => {
    const id = refId(db, 'tenants', params.id, { required: true });
    const used = get(db, 'SELECT COUNT(*) AS n FROM contracts WHERE tenant_id = ?', [id]).n;
    if (used) bad('לא ניתן למחוק דייר שמשויך לחוזה.');
    run(db, 'DELETE FROM tenants WHERE id = ?', [id]);
    return { ok: true };
  });

  /* --- חוזים --- */

  on('GET', '/api/contracts', () =>
    all(db, `${CONTRACT_SELECT} ORDER BY c.status, c.start_date DESC`).map((c) => ({
      ...D.hydrateContract(c),
      label: contractLabel(c),
      summary: D.contractSummary(db, c.id).totals,
    })),
  );

  on('GET', '/api/contracts/:id', (params) => {
    const id = refId(db, 'contracts', params.id, { required: true });
    const row = contractRow(db, id);
    const contract = D.hydrateContract(row);
    D.ensureCharges(db, contract);
    const summary = D.contractSummary(db, id);
    return {
      ...contract,
      label: contractLabel(row),
      tenant_name: row.tenant_name,
      tenant_phone: row.tenant_phone,
      tenant_email: row.tenant_email,
      property_name: row.property_name,
      property_address: row.property_address,
      property_city: row.property_city,
      property_unit: row.property_unit,
      summary: summary.totals,
      periods: summary.periods,
      charges: all(db, 'SELECT * FROM charges WHERE contract_id = ? ORDER BY period, kind, id', [id]),
      payments: paymentsForContract(db, id),
      files: all(db, 'SELECT id, filename, mime, size, extract_status, created_at, LENGTH(text) AS text_length FROM contract_files WHERE contract_id = ? ORDER BY id DESC', [id]),
    };
  });

  const contractFields = (body) => ({
    title: str(body, 'title', { max: 200 }),
    start_date: dateField(body, 'start_date', { required: true }),
    end_date: dateField(body, 'end_date'),
    rent_agorot: money(body, 'rent'),
    payment_day: U.clampInt(body.payment_day, 1, 31, 1),
    default_method: D.normalizeMethod(str(body, 'default_method', { fallback: 'bank_transfer' })),
    deposit_agorot: money(body, 'deposit'),
    deposit_kind: str(body, 'deposit_kind', { max: 120 }),
    prorate: body.prorate === false || body.prorate === 0 ? 0 : 1,
    status: D.normalizeContractStatus(str(body, 'status', { fallback: 'active' })),
    notes: str(body, 'notes', { max: 20000 }),
    contract_text: str(body, 'contract_text', { max: 2000000 }),
    extras: JSON.stringify(
      (Array.isArray(body.extras) ? body.extras : [])
        .map((e) => ({ label: String(e.label || 'תוספת').slice(0, 120), amount_agorot: money(e, 'amount') }))
        .filter((e) => e.amount_agorot > 0),
    ),
  });

  on('POST', '/api/contracts', (_p, _q, body) => {
    const f = contractFields(body);
    if (f.end_date && f.end_date < f.start_date) bad('תאריך הסיום מוקדם מתאריך ההתחלה');
    const propertyId = refId(db, 'properties', body.property_id);
    const tenantId = refId(db, 'tenants', body.tenant_id);
    const res = run(
      db,
      `INSERT INTO contracts (property_id,tenant_id,title,start_date,end_date,rent_agorot,payment_day,default_method,
                              deposit_agorot,deposit_kind,extras,prorate,status,notes,contract_text,created_at,updated_at)
       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
      [propertyId, tenantId, f.title, f.start_date, f.end_date, f.rent_agorot, f.payment_day, f.default_method,
       f.deposit_agorot, f.deposit_kind, f.extras, f.prorate, f.status, f.notes, f.contract_text, U.nowISO(), U.nowISO()],
    );
    const contract = D.getContract(db, res.lastInsertRowid);
    D.ensureCharges(db, contract);
    return { ...contract, label: contractLabel(contractRow(db, contract.id)) };
  });

  on('PUT', '/api/contracts/:id', (params, _q, body) => {
    const id = refId(db, 'contracts', params.id, { required: true });
    const f = contractFields(body);
    if (f.end_date && f.end_date < f.start_date) bad('תאריך הסיום מוקדם מתאריך ההתחלה');
    const propertyId = refId(db, 'properties', body.property_id);
    const tenantId = refId(db, 'tenants', body.tenant_id);
    run(
      db,
      `UPDATE contracts SET property_id=?, tenant_id=?, title=?, start_date=?, end_date=?, rent_agorot=?, payment_day=?,
                            default_method=?, deposit_agorot=?, deposit_kind=?, extras=?, prorate=?, status=?, notes=?,
                            contract_text=?, updated_at=? WHERE id=?`,
      [propertyId, tenantId, f.title, f.start_date, f.end_date, f.rent_agorot, f.payment_day, f.default_method,
       f.deposit_agorot, f.deposit_kind, f.extras, f.prorate, f.status, f.notes, f.contract_text, U.nowISO(), id],
    );
    const contract = D.getContract(db, id);
    const sync = D.syncFutureCharges(db, contract);
    return { ...contract, label: contractLabel(contractRow(db, id)), sync };
  });

  on('DELETE', '/api/contracts/:id', (params) => {
    const id = refId(db, 'contracts', params.id, { required: true });
    for (const f of all(db, 'SELECT stored_name FROM contract_files WHERE contract_id = ?', [id])) {
      try {
        fs.unlinkSync(path.join(uploadsDir, f.stored_name));
      } catch {
        /* הקובץ כבר לא קיים */
      }
    }
    run(db, 'DELETE FROM contracts WHERE id = ?', [id]);
    return { ok: true };
  });

  /* --- קבצי חוזה --- */

  on('POST', '/api/contracts/:id/files', (params, _q, body) => {
    const id = refId(db, 'contracts', params.id, { required: true });
    const filename = str(body, 'filename', { required: true, max: 260 });
    const b64 = String(body.data_base64 || '');
    if (!b64) bad('לא התקבל תוכן הקובץ');
    const buf = Buffer.from(b64, 'base64');
    if (buf.length === 0) bad('הקובץ ריק');
    if (buf.length > 25 * 1024 * 1024) bad('הקובץ גדול מדי (מקסימום 25MB)');

    const safeExt = (filename.split('.').pop() || 'bin').replace(/[^A-Za-z0-9]/g, '').slice(0, 8);
    const storedName = `${Date.now()}-${crypto.randomBytes(6).toString('hex')}.${safeExt || 'bin'}`;
    fs.mkdirSync(uploadsDir, { recursive: true });
    fs.writeFileSync(path.join(uploadsDir, storedName), buf);

    const extracted = extractText(filename, str(body, 'mime', { max: 120 }), buf);
    const res = run(
      db,
      `INSERT INTO contract_files (contract_id, filename, mime, size, stored_name, text, extract_status, created_at)
       VALUES (?,?,?,?,?,?,?,?)`,
      [id, filename, str(body, 'mime', { max: 120 }), buf.length, storedName, extracted.text, extracted.status, U.nowISO()],
    );
    return {
      id: res.lastInsertRowid,
      filename,
      size: buf.length,
      extract_status: extracted.status,
      note: extracted.note,
      text_length: extracted.text.length,
    };
  });

  on('DELETE', '/api/files/:id', (params) => {
    const id = refId(db, 'contract_files', params.id, { required: true });
    const row = get(db, 'SELECT stored_name FROM contract_files WHERE id = ?', [id]);
    try {
      fs.unlinkSync(path.join(uploadsDir, row.stored_name));
    } catch {
      /* כבר נמחק */
    }
    run(db, 'DELETE FROM contract_files WHERE id = ?', [id]);
    return { ok: true };
  });

  on('GET', '/api/files/:id/text', (params) => {
    const id = refId(db, 'contract_files', params.id, { required: true });
    return get(db, 'SELECT id, filename, extract_status, text FROM contract_files WHERE id = ?', [id]);
  });

  /* --- חיובים --- */

  on('GET', '/api/charges', (_p, query) => {
    const where = [];
    const args = [];
    if (query.contract_id) {
      where.push('ch.contract_id = ?');
      args.push(Number(query.contract_id));
    }
    if (U.isValidPeriod(query.period)) {
      where.push('ch.period = ?');
      args.push(query.period);
    }
    return all(
      db,
      `SELECT ch.*, t.name AS tenant_name, p.name AS property_name
       FROM charges ch
       LEFT JOIN contracts c ON c.id = ch.contract_id
       LEFT JOIN tenants t ON t.id = c.tenant_id
       LEFT JOIN properties p ON p.id = c.property_id
       ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
       ORDER BY ch.period DESC, t.name COLLATE NOCASE`,
      args,
    );
  });

  on('POST', '/api/charges', (_p, _q, body) => {
    const contractId = refId(db, 'contracts', body.contract_id, { required: true });
    const period = periodField(body, 'period', { required: true });
    const contract = D.getContract(db, contractId);
    const amount = money(body, 'amount');
    if (amount === 0) bad('יש להזין סכום');
    const res = run(
      db,
      `INSERT INTO charges (contract_id, period, kind, label, amount_agorot, due_date, source_key, manual_override, notes, created_at)
       VALUES (?,?,?,?,?,?,NULL,1,?,?)`,
      [
        contractId,
        period,
        'manual',
        str(body, 'label', { fallback: 'חיוב נוסף', max: 200 }),
        amount,
        dateField(body, 'due_date', { fallback: U.periodDueDate(period, contract.payment_day) }),
        str(body, 'notes', { max: 1000 }),
        U.nowISO(),
      ],
    );
    return get(db, 'SELECT * FROM charges WHERE id = ?', [res.lastInsertRowid]);
  });

  on('PUT', '/api/charges/:id', (params, _q, body) => {
    const id = refId(db, 'charges', params.id, { required: true });
    const row = get(db, 'SELECT * FROM charges WHERE id = ?', [id]);
    const amount = body.amount === undefined && body.amount_agorot === undefined ? row.amount_agorot : money(body, 'amount');
    run(
      db,
      'UPDATE charges SET label=?, amount_agorot=?, due_date=?, canceled=?, notes=?, manual_override=1 WHERE id=?',
      [
        str(body, 'label', { fallback: row.label, max: 200 }),
        amount,
        dateField(body, 'due_date', { fallback: row.due_date }),
        body.canceled ? 1 : 0,
        str(body, 'notes', { fallback: row.notes, max: 1000 }),
        id,
      ],
    );
    return get(db, 'SELECT * FROM charges WHERE id = ?', [id]);
  });

  on('DELETE', '/api/charges/:id', (params) => {
    const id = refId(db, 'charges', params.id, { required: true });
    run(db, 'DELETE FROM charges WHERE id = ?', [id]);
    return { ok: true };
  });

  /* --- תשלומים --- */

  on('GET', '/api/payments', (_p, query) => {
    const where = [];
    const args = [];
    if (query.contract_id) {
      where.push('p.contract_id = ?');
      args.push(Number(query.contract_id));
    }
    if (query.method) {
      where.push('p.method = ?');
      args.push(String(query.method));
    }
    if (query.status) {
      where.push('p.status = ?');
      args.push(String(query.status));
    }
    if (U.isValidDate(query.from)) {
      where.push('p.paid_date >= ?');
      args.push(query.from);
    }
    if (U.isValidDate(query.to)) {
      where.push('p.paid_date <= ?');
      args.push(query.to);
    }
    if (U.isValidPeriod(query.period)) {
      where.push('EXISTS (SELECT 1 FROM allocations a WHERE a.payment_id = p.id AND a.period = ?)');
      args.push(query.period);
    }
    const rows = all(
      db,
      `SELECT p.*, t.name AS tenant_name, pr.name AS property_name
       FROM payments p
       LEFT JOIN contracts c ON c.id = p.contract_id
       LEFT JOIN tenants t ON t.id = c.tenant_id
       LEFT JOIN properties pr ON pr.id = c.property_id
       ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
       ORDER BY p.paid_date DESC, p.id DESC
       LIMIT 1000`,
      args,
    );
    return rows.map((p) => ({
      ...p,
      allocations: all(db, 'SELECT period, amount_agorot FROM allocations WHERE payment_id = ? ORDER BY period', [p.id]),
    }));
  });

  on('GET', '/api/payments/:id', (params) => {
    const id = refId(db, 'payments', params.id, { required: true });
    const row = get(
      db,
      `SELECT p.*, t.name AS tenant_name, pr.name AS property_name
       FROM payments p
       LEFT JOIN contracts c ON c.id = p.contract_id
       LEFT JOIN tenants t ON t.id = c.tenant_id
       LEFT JOIN properties pr ON pr.id = c.property_id
       WHERE p.id = ?`,
      [id],
    );
    return {
      ...row,
      allocations: all(db, 'SELECT period, amount_agorot FROM allocations WHERE payment_id = ? ORDER BY period', [id]),
    };
  });

  on('POST', '/api/payments', (_p, _q, body) =>
    tx(db, () => {
      const id = writePayment(db, null, body, { isNew: true });
      return get(db, 'SELECT * FROM payments WHERE id = ?', [id]);
    }),
  );

  on('PUT', '/api/payments/:id', (params, _q, body) =>
    tx(db, () => {
      const id = refId(db, 'payments', params.id, { required: true });
      writePayment(db, id, body, { isNew: false });
      return get(db, 'SELECT * FROM payments WHERE id = ?', [id]);
    }),
  );

  on('DELETE', '/api/payments/:id', (params) => {
    const id = refId(db, 'payments', params.id, { required: true });
    run(db, 'DELETE FROM payments WHERE id = ?', [id]);
    return { ok: true };
  });

  /* --- כרטסת --- */

  on('GET', '/api/statement', (_p, query) => {
    const id = refId(db, 'contracts', query.contract_id, { required: true });
    const row = contractRow(db, id);
    const charges = all(db, 'SELECT * FROM charges WHERE contract_id = ? AND canceled = 0', [id]);
    const payments = paymentsForContract(db, id);
    const events = [];
    for (const c of charges) {
      events.push({ date: c.due_date, type: 'charge', label: `${c.label} – ${U.periodLabel(c.period)}`, amount: c.amount_agorot, period: c.period });
    }
    for (const p of payments) {
      if (p.status === 'bounced') {
        events.push({ date: p.paid_date, type: 'bounced', label: `תשלום שחזר (${D.PAYMENT_METHODS[p.method]})`, amount: 0, method: p.method });
        continue;
      }
      events.push({
        date: p.paid_date,
        type: p.status === 'pending' ? 'pending' : 'payment',
        label: `${D.PAYMENT_METHODS[p.method] || p.method}${p.check_number ? ` #${p.check_number}` : ''}${p.reference ? ` (${p.reference})` : ''}`,
        amount: -p.amount_agorot,
        method: p.method,
        periods: p.allocations.map((a) => a.period),
      });
    }
    events.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : a.type === 'charge' ? -1 : 1));
    let balance = 0;
    for (const e of events) {
      if (e.type !== 'pending') balance += e.amount;
      e.balance = balance;
    }
    const summary = D.contractSummary(db, id);
    return { contract: { ...D.hydrateContract(row), label: contractLabel(row), tenant_name: row.tenant_name, property_name: row.property_name, property_address: row.property_address }, events, summary: summary.totals, periods: summary.periods };
  });

  /* --- חיפוש --- */

  on('GET', '/api/search', (_p, query) => {
    const q = String(query.q || '').slice(0, 300);
    const res = S.searchDocs(searchDocsFor(db), q);
    return { q, count: res.results.length, terms: res.query.include, results: res.results.slice(0, 100) };
  });

  /* --- ייצוא --- */

  on('GET', '/api/export/payments.csv', (_p, query) => {
    const rows = all(
      db,
      `SELECT p.*, t.name AS tenant_name, pr.name AS property_name,
              (SELECT GROUP_CONCAT(a.period, ' ') FROM allocations a WHERE a.payment_id = p.id) AS periods
       FROM payments p
       LEFT JOIN contracts c ON c.id = p.contract_id
       LEFT JOIN tenants t ON t.id = c.tenant_id
       LEFT JOIN properties pr ON pr.id = c.property_id
       ${U.isValidPeriod(query.period) ? "WHERE EXISTS (SELECT 1 FROM allocations a WHERE a.payment_id = p.id AND a.period = ?)" : ''}
       ORDER BY p.paid_date DESC`,
      U.isValidPeriod(query.period) ? [query.period] : [],
    );
    const csv = toCSV(
      ['תאריך', 'דייר', 'נכס', 'סכום', 'אמצעי תשלום', 'סטטוס', 'חודשים משויכים', 'מס׳ צ׳ק', 'בנק', 'אסמכתא', 'הערות'],
      rows.map((r) => [
        r.paid_date,
        r.tenant_name || '',
        r.property_name || '',
        shekels(r.amount_agorot),
        D.PAYMENT_METHODS[r.method] || r.method,
        D.PAYMENT_STATUSES[r.status] || r.status,
        r.periods || '',
        r.check_number,
        r.bank,
        r.reference,
        r.notes,
      ]),
    );
    return { __raw: csv, __type: 'text/csv; charset=utf-8', __filename: 'payments.csv' };
  });

  on('GET', '/api/export/balances.csv', (_p, query) => {
    const period = U.isValidPeriod(query.period) ? query.period : U.currentPeriod();
    const data = D.dashboard(db, period);
    const csv = toCSV(
      ['דייר', 'נכס', 'לתשלום החודש', 'שולם', 'ממתין', 'יתרה לחודש', 'יתרת פיגור כוללת', 'אמצעי תשלום ברירת מחדל'],
      data.rows.map((r) => [
        r.tenant_name,
        r.property_name,
        shekels(r.month.charged),
        shekels(r.month.paid),
        shekels(r.month.pending),
        shekels(r.month.charged - r.month.paid),
        shekels(r.totals.overdue),
        D.PAYMENT_METHODS[r.default_method] || r.default_method,
      ]),
    );
    return { __raw: csv, __type: 'text/csv; charset=utf-8', __filename: `balances-${period}.csv` };
  });

  on('GET', '/api/backup', () => ({
    __raw: JSON.stringify(
      {
        version: 1,
        exported_at: U.nowISO(),
        properties: all(db, 'SELECT * FROM properties'),
        tenants: all(db, 'SELECT * FROM tenants'),
        contracts: all(db, 'SELECT * FROM contracts'),
        contract_files: all(db, 'SELECT * FROM contract_files'),
        charges: all(db, 'SELECT * FROM charges'),
        payments: all(db, 'SELECT * FROM payments'),
        allocations: all(db, 'SELECT * FROM allocations'),
        settings: all(db, 'SELECT * FROM settings'),
      },
      null,
      1,
    ),
    __type: 'application/json; charset=utf-8',
    __filename: `rent-backup-${U.todayISO()}.json`,
  }));

  on('POST', '/api/restore', (_p, _q, body) => {
    const data = body && body.data;
    if (!data || typeof data !== 'object') bad('קובץ גיבוי לא תקין');
    const tables = ['allocations', 'payments', 'charges', 'contract_files', 'contracts', 'tenants', 'properties', 'settings'];
    return tx(db, () => {
      for (const t of tables) run(db, `DELETE FROM ${t}`);
      const insertAll = (table, rows) => {
        if (!Array.isArray(rows)) return 0;
        // מקבלים רק עמודות שקיימות בפועל בטבלה, כדי שגיבוי מגרסה אחרת לא ישבור את השחזור
        const columns = new Set(all(db, `PRAGMA table_info(${table})`).map((c) => c.name));
        let n = 0;
        for (const row of rows) {
          const keys = Object.keys(row).filter((k) => columns.has(k));
          if (!keys.length) continue;
          run(
            db,
            `INSERT OR REPLACE INTO ${table} (${keys.join(',')}) VALUES (${keys.map(() => '?').join(',')})`,
            keys.map((k) => row[k]),
          );
          n += 1;
        }
        return n;
      };
      const counts = {};
      for (const t of ['properties', 'tenants', 'contracts', 'contract_files', 'charges', 'payments', 'allocations', 'settings']) {
        counts[t] = insertAll(t, data[t]);
      }
      return { ok: true, counts };
    });
  });

  on('POST', '/api/demo', () =>
    tx(db, () => {
      const existing = get(db, 'SELECT COUNT(*) AS n FROM contracts').n;
      if (existing > 0) bad('כבר קיימים חוזים במערכת. אפשר לטעון נתוני דמו רק על מסד ריק.');
      return seedDemo(db);
    }),
  );

  on('POST', '/api/reset', (_p, _q, body) => {
    if (body.confirm !== 'מחק הכל') bad('לאישור המחיקה יש לשלוח confirm="מחק הכל"');
    return tx(db, () => {
      for (const t of ['allocations', 'payments', 'charges', 'contract_files', 'contracts', 'tenants', 'properties']) {
        run(db, `DELETE FROM ${t}`);
      }
      return { ok: true };
    });
  });

  function dispatch(method, pathname, query, body) {
    for (const route of routes) {
      if (route.method !== method) continue;
      const m = route.re.exec(pathname);
      if (!m) continue;
      const params = {};
      route.keys.forEach((k, i) => {
        params[k] = decodeURIComponent(m[i + 1]);
      });
      return route.handler(params, query, body || {});
    }
    throw new ApiError(404, 'נתיב לא קיים');
  }

  return { dispatch, seedDemo };
}

module.exports = { createRouter, ApiError, seedDemo, searchDocsFor, toCSV };
