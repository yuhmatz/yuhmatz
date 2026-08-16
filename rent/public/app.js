'use strict';

/* ממשק המשתמש של מערכת גביית שכר הדירה. ללא ספריות – JS רגיל. */

const state = {
  boot: null,
  view: 'dashboard',
  period: new Date().toISOString().slice(0, 7),
  contractId: null,
  payload: null,
  search: { q: '', data: null },
  filters: { method: '', status: '', contract_id: '', from: '', to: '' },
  textQuery: '',
};

const VIEWS = [
  ['dashboard', 'לוח בקרה'],
  ['contracts', 'חוזים'],
  ['payments', 'תשלומים'],
  ['checks', 'צ׳קים'],
  ['search', 'חיפוש בחוזים'],
  ['tenants', 'דיירים'],
  ['properties', 'נכסים'],
  ['settings', 'הגדרות'],
];

/* ---------- עזרים ---------- */

const $ = (sel, root = document) => root.querySelector(sel);
const el = (id) => document.getElementById(id);

function esc(value) {
  return String(value === null || value === undefined ? '' : value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function money(agorot) {
  const n = (Number(agorot) || 0) / 100;
  return '₪' + n.toLocaleString('he-IL', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function money0(agorot) {
  const n = Math.round((Number(agorot) || 0) / 100);
  return '₪' + n.toLocaleString('he-IL');
}

const HE_MONTHS = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'];

function periodLabel(period) {
  if (!period || !/^\d{4}-\d{2}$/.test(period)) return period || '';
  const [y, m] = period.split('-').map(Number);
  return `${HE_MONTHS[m - 1]} ${y}`;
}

function dateHe(iso) {
  if (!iso) return '';
  const [y, m, d] = String(iso).slice(0, 10).split('-');
  return `${d}/${m}/${y}`;
}

function addMonths(period, delta) {
  const [y, m] = period.split('-').map(Number);
  const total = y * 12 + (m - 1) + delta;
  return `${Math.floor(total / 12)}-${String(((total % 12) + 12) % 12 + 1).padStart(2, '0')}`;
}

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function toast(message, kind = '') {
  const node = document.createElement('div');
  node.className = `toast ${kind}`;
  node.textContent = message;
  el('toasts').appendChild(node);
  setTimeout(() => node.remove(), kind === 'error' ? 7000 : 3500);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    method: options.method || 'GET',
    headers: options.body ? { 'Content-Type': 'application/json' } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401) {
    showLogin();
    throw new Error('נדרשת כניסה');
  }
  const data = await res.json().catch(() => ({ error: 'תשובה לא תקינה מהשרת' }));
  if (!res.ok) throw new Error(data.error || `שגיאה (${res.status})`);
  return data;
}

/* ---------- נרמול עברי לחיפוש בתוך טקסט (זהה לצד השרת) ---------- */

const FINALS = { 'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ' };
const PUNCT = { '׳': "'", '״': '"', '’': "'", '‘': "'", '“': '"', '”': '"' };
const DASH_RE = /[-\u05BE\u2010-\u2015]/;
const DROP = /[\u0591-\u05BD\u05BF-\u05C7\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/;

function normalizeText(text) {
  const src = String(text || '');
  let norm = '';
  const map = [];
  let space = true;
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i];
    if (DROP.test(ch)) continue;
    if (/\s/.test(ch) || DASH_RE.test(ch)) {
      if (space) continue;
      norm += ' ';
      map.push(i);
      space = true;
      continue;
    }
    space = false;
    let out = PUNCT[ch] || FINALS[ch] || ch;
    const lower = out.toLowerCase();
    if (lower.length === 1) out = lower;
    norm += out;
    map.push(i);
  }
  map.push(src.length);
  return { norm, map };
}

/** מחזיר HTML עם סימון כל מופעי המונחים בטקסט. */
function highlight(text, query) {
  const terms = String(query || '')
    .split(/\s+/)
    .map((t) => normalizeText(t).norm.trim())
    .filter(Boolean);
  if (!terms.length) return esc(text);
  const { norm, map } = normalizeText(text);
  const ranges = [];
  for (const term of terms) {
    let idx = norm.indexOf(term);
    while (idx !== -1) {
      ranges.push([map[idx], map[Math.min(idx + term.length, map.length - 1)]]);
      idx = norm.indexOf(term, idx + term.length);
    }
  }
  if (!ranges.length) return esc(text);
  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  let out = '';
  let pos = 0;
  for (const [s, e] of merged) {
    out += esc(text.slice(pos, s)) + '<mark>' + esc(text.slice(s, e)) + '</mark>';
    pos = e;
  }
  return out + esc(text.slice(pos));
}

/** סימון קטע לפי טווחים שהתקבלו מהשרת. */
function markSnippet(snippet) {
  let out = '';
  let pos = 0;
  for (const [s, e] of snippet.ranges) {
    if (s < pos) continue;
    out += esc(snippet.text.slice(pos, s)) + '<mark>' + esc(snippet.text.slice(s, e)) + '</mark>';
    pos = e;
  }
  return out + esc(snippet.text.slice(pos));
}

/* ---------- מודאל ---------- */

let modalSubmit = null;

function closeModal() {
  el('modal-host').innerHTML = '';
  modalSubmit = null;
}

function openModal({ title, body, submitLabel = 'שמירה', onSubmit, wide = false, extraFooter = '' }) {
  el('modal-host').innerHTML = `
    <div class="modal-backdrop" data-close-backdrop>
      <form class="modal" id="modal-form" ${wide ? 'style="width:min(980px,100%)"' : ''}>
        <header><h3>${esc(title)}</h3><button type="button" class="btn ghost" data-act="modal-close">✕</button></header>
        <div class="body">${body}</div>
        <footer>
          <button class="btn primary" type="submit">${esc(submitLabel)}</button>
          <button class="btn" type="button" data-act="modal-close">ביטול</button>
          ${extraFooter}
        </footer>
      </form>
    </div>`;
  modalSubmit = onSubmit;
  const first = $('#modal-form input:not([type=hidden]), #modal-form select, #modal-form textarea');
  if (first) first.focus();
}

function formValues(form) {
  const out = {};
  for (const element of form.elements) {
    if (!element.name) continue;
    if (element.type === 'checkbox') out[element.name] = element.checked;
    else out[element.name] = element.value;
  }
  return out;
}

/* ---------- רכיבי טופס ---------- */

function field(label, inner, help = '') {
  return `<div class="field"><label>${esc(label)}</label>${inner}${help ? `<div class="help">${esc(help)}</div>` : ''}</div>`;
}

function input(name, value = '', attrs = '') {
  return `<input name="${name}" value="${esc(value)}" ${attrs}>`;
}

function select(name, options, value, attrs = '') {
  const opts = options
    .map(([v, label]) => `<option value="${esc(v)}" ${String(v) === String(value) ? 'selected' : ''}>${esc(label)}</option>`)
    .join('');
  return `<select name="${name}" ${attrs}>${opts}</select>`;
}

function textarea(name, value = '', attrs = '') {
  return `<textarea name="${name}" ${attrs}>${esc(value)}</textarea>`;
}

const methodOptions = () => Object.entries(state.boot.methods);
const statusOptions = () => Object.entries(state.boot.payment_statuses);

function contractOptions(selected) {
  return state.boot.contracts.map((c) => [c.id, `${c.label}${c.status !== 'active' ? ` (${state.boot.contract_statuses[c.status]})` : ''}`]);
}

function badgeForState(row) {
  const map = {
    paid: ['ok', 'שולם'],
    pending: ['warn', 'ממתין לפירעון'],
    partial: ['warn', 'שולם חלקית'],
    overdue: ['danger', 'בפיגור'],
    open: ['muted', 'טרם שולם'],
    credit: ['info', 'יתרת זכות'],
    none: ['muted', '—'],
  };
  const [cls, label] = map[row.state] || map.none;
  return `<span class="badge ${cls}">${label}</span>`;
}

/* ---------- לוח בקרה ---------- */

async function renderDashboard() {
  const data = await api(`/api/dashboard?period=${state.period}`);
  state.payload = data;
  const t = data.totals;
  const pct = t.expected > 0 ? Math.min(100, Math.round((t.paid / t.expected) * 100)) : 0;

  const rows = data.rows
    .map((r) => {
      const methods = r.methods.length
        ? r.methods.map((m) => `<span class="badge muted">${esc(state.boot.methods[m.method] || m.method)} ${money0(m.total)}</span>`).join(' ')
        : '<span class="muted small">—</span>';
      return `<tr class="row-click" data-act="open-contract" data-id="${r.contract_id}">
        <td class="strong">${esc(r.tenant_name)}<div class="sub">${esc(r.property_name)}</div></td>
        <td class="num">${money(r.month.charged)}</td>
        <td class="num">${money(r.month.paid)}</td>
        <td class="num">${r.month.pending ? money(r.month.pending) : '<span class="muted">—</span>'}</td>
        <td class="num ${r.month.charged - r.month.paid > 0 ? 'strong' : ''}">${money(r.month.charged - r.month.paid)}</td>
        <td>${r.active_in_period ? badgeForState(r.month) : `<span class="badge muted">${esc(r.period_note)}</span>`}</td>
        <td>${methods}</td>
        <td class="num">${r.totals.overdue > 0 ? `<span class="badge danger">${money(r.totals.overdue)}</span>` : '<span class="muted">—</span>'}</td>
        <td class="no-print"><button class="btn sm primary" data-act="new-payment" data-id="${r.contract_id}" data-period="${data.period}">רישום תשלום</button></td>
      </tr>`;
    })
    .join('');

  const checks = data.checks
    .map(
      (c) => `<tr>
        <td>${esc(c.tenant_name || '')}</td>
        <td class="num">${money(c.amount_agorot)}</td>
        <td>${esc(c.check_number || '')}</td>
        <td>${esc(c.bank || '')}</td>
        <td class="num">${dateHe(c.due_date || c.paid_date)}</td>
        <td class="no-print">
          <button class="btn sm" data-act="check-status" data-id="${c.id}" data-status="paid">נפרע</button>
          <button class="btn sm danger" data-act="check-status" data-id="${c.id}" data-status="bounced">חזר</button>
        </td>
      </tr>`,
    )
    .join('');

  el('view').innerHTML = `
    <div class="page-head">
      <h1>לוח בקרה – ${esc(data.period_label)}</h1>
      <div class="toolbar no-print">
        <button class="btn" data-act="prev-month">‹ חודש קודם</button>
        <button class="btn" data-act="next-month">חודש הבא ›</button>
        <button class="btn primary" data-act="new-payment">+ רישום תשלום</button>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="label">צפי גבייה לחודש</div><div class="value">${money0(t.expected)}</div>
        <div class="progress"><span style="width:${pct}%"></span></div>
        <div class="hint">${pct}% נגבו</div></div>
      <div class="kpi"><div class="label">נגבה בפועל</div><div class="value ok">${money0(t.paid)}</div></div>
      <div class="kpi"><div class="label">ממתין לפירעון (צ׳קים)</div><div class="value warn">${money0(t.pending)}</div></div>
      <div class="kpi"><div class="label">חוב פתוח לחודש</div><div class="value ${t.outstanding > 0 ? 'danger' : 'ok'}">${money0(t.outstanding)}</div></div>
      <div class="kpi"><div class="label">פיגור מצטבר</div><div class="value ${t.overdue_all > 0 ? 'danger' : 'ok'}">${money0(t.overdue_all)}</div>
        <div class="hint">כולל חודשים קודמים</div></div>
      <div class="kpi"><div class="label">יתרות זכות</div><div class="value">${money0(t.credit)}</div>
        <div class="hint">תשלומים שטרם שויכו לחודש</div></div>
    </div>

    <div class="card">
      <h2>מצב גבייה לפי דייר <span class="spacer"></span>
        <a class="btn sm no-print" href="/api/export/balances.csv?period=${data.period}">ייצוא CSV</a>
        <button class="btn sm no-print" data-act="print">הדפסה</button>
      </h2>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>דייר / נכס</th><th class="num">אמור להעביר</th><th class="num">הועבר</th><th class="num">ממתין</th>
            <th class="num">יתרה</th><th>סטטוס</th><th>איך שולם</th><th class="num">פיגור כולל</th><th class="no-print"></th>
          </tr></thead>
          <tbody>${rows || '<tr><td colspan="9" class="empty">אין חוזים פעילים. אפשר להתחיל מהוספת נכס, דייר וחוזה – או לטעון נתוני דמו בהגדרות.</td></tr>'}</tbody>
        </table>
      </div>
    </div>

    ${
      data.checks.length
        ? `<div class="card">
            <h2>צ׳קים שממתינים לפירעון (${data.checks.length})</h2>
            <div class="table-wrap"><table>
              <thead><tr><th>דייר</th><th class="num">סכום</th><th>מס׳ צ׳ק</th><th>בנק</th><th class="num">תאריך פירעון</th><th class="no-print"></th></tr></thead>
              <tbody>${checks}</tbody>
            </table></div>
          </div>`
        : ''
    }`;
}

/* ---------- חוזים ---------- */

async function renderContracts() {
  const list = await api('/api/contracts');
  const rows = list
    .map(
      (c) => `<tr class="row-click" data-act="open-contract" data-id="${c.id}">
        <td class="strong">${esc(c.tenant_name || 'ללא דייר')}</td>
        <td>${esc(c.property_name || '')}<div class="sub">${esc(c.property_address || '')}</div></td>
        <td class="num">${money(c.rent_agorot)}</td>
        <td class="nowrap">${esc(state.boot.methods[c.default_method])}</td>
        <td class="nowrap">${dateHe(c.start_date)} – ${c.end_date ? dateHe(c.end_date) : 'ללא סיום'}</td>
        <td class="num">${c.summary.balance > 0 ? `<span class="badge ${c.summary.overdue > 0 ? 'danger' : 'warn'}">${money(c.summary.balance)}</span>` : '<span class="badge ok">מאוזן</span>'}</td>
        <td><span class="badge ${c.status === 'active' ? 'ok' : 'muted'}">${esc(state.boot.contract_statuses[c.status])}</span></td>
      </tr>`,
    )
    .join('');

  el('view').innerHTML = `
    <div class="page-head">
      <h1>חוזים</h1>
      <div class="toolbar"><button class="btn primary" data-act="new-contract">+ חוזה חדש</button></div>
    </div>
    <div class="card">
      <div class="table-wrap"><table>
        <thead><tr><th>דייר</th><th>נכס</th><th class="num">שכ״ד חודשי</th><th>אמצעי תשלום</th><th>תקופה</th><th class="num">יתרה</th><th>סטטוס</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="7" class="empty">עדיין אין חוזים</td></tr>'}</tbody>
      </table></div>
    </div>`;
}

async function renderContract() {
  const c = await api(`/api/contracts/${state.contractId}`);
  state.payload = c;
  const s = c.summary;

  const periods = c.periods
    .map(
      (p) => `<tr>
        <td class="strong">${esc(p.label)}</td>
        <td class="num">${dateHe(p.due_date)}</td>
        <td class="num">${money(p.charged)}</td>
        <td class="num">${money(p.paid)}</td>
        <td class="num">${p.pending ? money(p.pending) : '<span class="muted">—</span>'}</td>
        <td class="num strong">${money(p.balance)}</td>
        <td>${badgeForState(p)}</td>
        <td class="no-print">${p.balance > 0 ? `<button class="btn sm" data-act="new-payment" data-id="${c.id}" data-period="${p.period}" data-amount="${p.balance}">רישום תשלום</button>` : ''}</td>
      </tr>`,
    )
    .reverse()
    .join('');

  const charges = c.charges
    .map(
      (ch) => `<tr class="${ch.canceled ? 'muted' : ''}">
        <td>${esc(periodLabel(ch.period))}</td>
        <td>${esc(ch.label)} ${ch.canceled ? '<span class="badge muted">בוטל</span>' : ''}</td>
        <td>${esc(state.boot.charge_kinds[ch.kind] || ch.kind)}</td>
        <td class="num">${dateHe(ch.due_date)}</td>
        <td class="num">${money(ch.amount_agorot)}</td>
        <td class="no-print">
          <button class="btn sm" data-act="edit-charge" data-id="${ch.id}">עריכה</button>
          <button class="btn sm ghost" data-act="delete-charge" data-id="${ch.id}">מחיקה</button>
        </td>
      </tr>`,
    )
    .join('');

  const payments = c.payments.map((p) => paymentRow(p, { showTenant: false })).join('');

  const files = c.files
    .map(
      (f) => `<tr>
        <td><a href="/files/${f.id}" target="_blank">${esc(f.filename)}</a></td>
        <td class="num">${Math.max(1, Math.round(f.size / 1024))} KB</td>
        <td>${fileStatusBadge(f)}</td>
        <td class="num">${dateHe(f.created_at)}</td>
        <td class="no-print">
          ${f.text_length > 0 ? `<button class="btn sm" data-act="file-text" data-id="${f.id}">הצגת הטקסט</button>` : ''}
          <button class="btn sm ghost" data-act="delete-file" data-id="${f.id}">מחיקה</button>
        </td>
      </tr>`,
    )
    .join('');

  const extras = c.extras.length
    ? c.extras.map((e) => `<span class="badge info">${esc(e.label)}: ${money(e.amount_agorot)}</span>`).join(' ')
    : '<span class="muted small">אין תוספות קבועות</span>';

  el('view').innerHTML = `
    <div class="page-head">
      <button class="btn ghost no-print" data-act="go-contracts">‹ חזרה לחוזים</button>
      <h1>${esc(c.tenant_name || 'ללא דייר')} · ${esc(c.property_name || c.property_address || 'נכס')}</h1>
      <div class="toolbar no-print">
        <button class="btn primary" data-act="new-payment" data-id="${c.id}">+ רישום תשלום</button>
        <button class="btn" data-act="new-charge" data-id="${c.id}">+ חיוב נוסף</button>
        <button class="btn" data-act="edit-contract" data-id="${c.id}">עריכת חוזה</button>
        <button class="btn" data-act="statement" data-id="${c.id}">כרטסת</button>
        <button class="btn danger" data-act="delete-contract" data-id="${c.id}">מחיקה</button>
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="label">שכר דירה חודשי</div><div class="value">${money0(c.rent_agorot)}</div>
        <div class="hint">עד ה-${c.payment_day} לחודש · ${esc(state.boot.methods[c.default_method])}</div></div>
      <div class="kpi"><div class="label">סה״כ חויב</div><div class="value">${money0(s.charged)}</div></div>
      <div class="kpi"><div class="label">סה״כ שולם</div><div class="value ok">${money0(s.paid)}</div></div>
      <div class="kpi"><div class="label">יתרה</div><div class="value ${s.balance > 0 ? 'danger' : 'ok'}">${money0(s.balance)}</div>
        <div class="hint">כולל חיובים שטרם הגיע מועדם</div></div>
      <div class="kpi"><div class="label">מזה בפיגור</div><div class="value ${s.overdue > 0 ? 'danger' : 'ok'}">${money0(s.overdue)}</div></div>
      <div class="kpi"><div class="label">ממתין לפירעון</div><div class="value warn">${money0(s.pending)}</div>
        ${s.unallocated ? `<div class="hint">יתרת זכות: ${money(s.unallocated)}</div>` : ''}</div>
    </div>

    <div class="card">
      <h2>פרטי החוזה</h2>
      <div class="meta-grid">
        <div><div class="k">דייר</div><div class="v">${esc(c.tenant_name || '—')}</div><div class="sub">${esc(c.tenant_phone || '')} ${esc(c.tenant_email || '')}</div></div>
        <div><div class="k">נכס</div><div class="v">${esc(c.property_name || '—')}</div><div class="sub">${esc([c.property_address, c.property_city].filter(Boolean).join(', '))}</div></div>
        <div><div class="k">תקופה</div><div class="v">${dateHe(c.start_date)} – ${c.end_date ? dateHe(c.end_date) : 'ללא תאריך סיום'}</div></div>
        <div><div class="k">ביטחונות</div><div class="v">${c.deposit_agorot ? money(c.deposit_agorot) : '—'}</div><div class="sub">${esc(c.deposit_kind || '')}</div></div>
        <div><div class="k">תוספות קבועות</div><div class="v pill-row">${extras}</div></div>
        <div><div class="k">סטטוס</div><div class="v">${esc(state.boot.contract_statuses[c.status])}</div></div>
      </div>
      ${c.notes ? `<div class="field" style="margin-top:12px"><label>הערות</label><div class="snippet">${esc(c.notes)}</div></div>` : ''}
    </div>

    <div class="card">
      <h2>מעקב חודשי <span class="spacer"></span><span class="sub">כמה אמור לשלם מול כמה שולם בפועל</span></h2>
      <div class="table-wrap"><table>
        <thead><tr><th>חודש</th><th class="num">תאריך יעד</th><th class="num">אמור לשלם</th><th class="num">שולם</th><th class="num">ממתין</th><th class="num">יתרה</th><th>סטטוס</th><th class="no-print"></th></tr></thead>
        <tbody>${periods || '<tr><td colspan="8" class="empty">אין חיובים</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="card">
      <h2>תשלומים שהתקבלו (${c.payments.length})</h2>
      <div class="table-wrap"><table>
        <thead><tr><th class="num">תאריך</th><th class="num">סכום</th><th>אמצעי</th><th>פרטים</th><th>שויך לחודשים</th><th>סטטוס</th><th class="no-print"></th></tr></thead>
        <tbody>${payments || '<tr><td colspan="7" class="empty">טרם נרשמו תשלומים</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="card">
      <h2>חיובים (${c.charges.length}) <span class="spacer"></span><span class="sub">נוצרים אוטומטית בכל חודש לפי החוזה</span></h2>
      <div class="table-wrap"><table>
        <thead><tr><th>חודש</th><th>תיאור</th><th>סוג</th><th class="num">תאריך יעד</th><th class="num">סכום</th><th class="no-print"></th></tr></thead>
        <tbody>${charges || '<tr><td colspan="6" class="empty">אין חיובים</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="card no-print">
      <h2>קבצי החוזה <span class="spacer"></span>
        <label class="btn sm">העלאת קובץ<input type="file" id="file-input" class="hidden" accept=".pdf,.docx,.odt,.txt,.md,.csv,.jpg,.jpeg,.png"></label>
      </h2>
      <div class="table-wrap"><table>
        <thead><tr><th>שם הקובץ</th><th class="num">גודל</th><th>ניתן לחיפוש</th><th class="num">הועלה</th><th></th></tr></thead>
        <tbody>${files || '<tr><td colspan="5" class="empty">לא הועלו קבצים. אפשר להעלות PDF / Word / טקסט – והמערכת תחלץ מהם טקסט לחיפוש.</td></tr>'}</tbody>
      </table></div>
    </div>

    <div class="card">
      <h2>נוסח החוזה <span class="spacer"></span>
        <input id="text-search" class="no-print" style="width:220px" placeholder="חיפוש בתוך החוזה" value="${esc(state.textQuery)}">
        <span id="text-hits" class="sub"></span>
        <button class="btn sm no-print" data-act="edit-text" data-id="${c.id}">עריכה</button>
      </h2>
      <div class="contract-text" id="contract-text">${c.contract_text ? highlight(c.contract_text, state.textQuery) : '<span class="muted">לא הוזן נוסח חוזה. אפשר להדביק כאן את החוזה (כפתור עריכה) או להעלות קובץ – כדי שאפשר יהיה לחפש בתוכו.</span>'}</div>
    </div>`;

  const searchInput = el('text-search');
  if (searchInput) {
    searchInput.addEventListener('input', () => {
      state.textQuery = searchInput.value;
      const target = el('contract-text');
      target.innerHTML = c.contract_text ? highlight(c.contract_text, state.textQuery) : '';
      const hits = target.querySelectorAll('mark').length;
      el('text-hits').textContent = state.textQuery ? `${hits} תוצאות` : '';
      const first = target.querySelector('mark');
      if (first) first.scrollIntoView({ block: 'center', behavior: 'smooth' });
    });
    if (state.textQuery) searchInput.dispatchEvent(new Event('input'));
  }
  const fileInput = el('file-input');
  if (fileInput) fileInput.addEventListener('change', () => uploadFile(c.id, fileInput));
}

function fileStatusBadge(f) {
  if (f.extract_status === 'ok') return `<span class="badge ok">כן (${f.text_length} תווים)</span>`;
  if (f.extract_status === 'empty') return '<span class="badge warn">לא – כנראה סריקה</span>';
  if (f.extract_status === 'unsupported') return '<span class="badge muted">לא נתמך</span>';
  if (f.extract_status === 'error') return '<span class="badge danger">שגיאה</span>';
  return '<span class="badge muted">—</span>';
}

function paymentRow(p, { showTenant }) {
  const details = [];
  if (p.check_number) details.push(`צ׳ק ${p.check_number}`);
  if (p.bank) details.push(p.bank);
  if (p.branch) details.push(`סניף ${p.branch}`);
  if (p.reference) details.push(p.reference);
  if (p.due_date) details.push(`פירעון ${dateHe(p.due_date)}`);
  if (p.notes) details.push(p.notes);
  const statusCls = p.status === 'paid' ? 'ok' : p.status === 'pending' ? 'warn' : 'danger';
  const alloc = p.allocations && p.allocations.length
    ? p.allocations.map((a) => `<span class="badge muted">${esc(periodLabel(a.period))} · ${money0(a.amount_agorot)}</span>`).join(' ')
    : '<span class="badge info">לא שויך</span>';
  return `<tr>
    ${showTenant ? `<td class="strong">${esc(p.tenant_name || '')}<div class="sub">${esc(p.property_name || '')}</div></td>` : ''}
    <td class="num nowrap">${dateHe(p.paid_date)}</td>
    <td class="num strong">${money(p.amount_agorot)}</td>
    <td class="nowrap">${esc(state.boot.methods[p.method] || p.method)}</td>
    <td class="small">${esc(details.join(' · '))}</td>
    <td class="pill-row">${alloc}</td>
    <td><span class="badge ${statusCls}">${esc(state.boot.payment_statuses[p.status])}</span></td>
    <td class="no-print nowrap">
      ${p.status === 'pending' ? `<button class="btn sm" data-act="check-status" data-id="${p.id}" data-status="paid">נפרע</button>` : ''}
      <button class="btn sm" data-act="edit-payment" data-id="${p.id}">עריכה</button>
      <button class="btn sm ghost" data-act="delete-payment" data-id="${p.id}">מחיקה</button>
    </td>
  </tr>`;
}

/* ---------- תשלומים ---------- */

async function renderPayments() {
  const f = state.filters;
  const qs = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const list = await api(`/api/payments${qs ? `?${qs}` : ''}`);
  const total = list.filter((p) => p.status === 'paid').reduce((acc, p) => acc + p.amount_agorot, 0);

  el('view').innerHTML = `
    <div class="page-head">
      <h1>תשלומים</h1>
      <div class="toolbar">
        <button class="btn primary" data-act="new-payment">+ רישום תשלום</button>
        <a class="btn" href="/api/export/payments.csv">ייצוא CSV</a>
      </div>
    </div>
    <div class="card no-print">
      <div class="grid3">
        ${field('חוזה', select('contract_id', [['', 'הכל'], ...contractOptions()], f.contract_id, 'data-filter="contract_id"'))}
        ${field('אמצעי תשלום', select('method', [['', 'הכל'], ...methodOptions()], f.method, 'data-filter="method"'))}
        ${field('סטטוס', select('status', [['', 'הכל'], ...statusOptions()], f.status, 'data-filter="status"'))}
        ${field('מתאריך', input('from', f.from, 'type="date" data-filter="from"'))}
        ${field('עד תאריך', input('to', f.to, 'type="date" data-filter="to"'))}
        <div class="field" style="display:flex;align-items:flex-end"><button class="btn" data-act="clear-filters">ניקוי סינון</button></div>
      </div>
    </div>
    <div class="card">
      <h2>${list.length} תשלומים <span class="spacer"></span><span class="sub">סה״כ שנפרע: ${money(total)}</span></h2>
      <div class="table-wrap"><table>
        <thead><tr><th>דייר / נכס</th><th class="num">תאריך</th><th class="num">סכום</th><th>אמצעי</th><th>פרטים</th><th>שויך לחודשים</th><th>סטטוס</th><th class="no-print"></th></tr></thead>
        <tbody>${list.map((p) => paymentRow(p, { showTenant: true })).join('') || '<tr><td colspan="8" class="empty">אין תשלומים להצגה</td></tr>'}</tbody>
      </table></div>
    </div>`;

  for (const node of document.querySelectorAll('[data-filter]')) {
    node.addEventListener('change', () => {
      state.filters[node.dataset.filter] = node.value;
      render();
    });
  }
}

/* ---------- צ׳קים ---------- */

async function renderChecks() {
  const list = await api('/api/payments?method=check');
  const groups = {
    pending: list.filter((p) => p.status === 'pending'),
    paid: list.filter((p) => p.status === 'paid'),
    bounced: list.filter((p) => p.status === 'bounced'),
  };
  const table = (rows, withActions) => `
    <div class="table-wrap"><table>
      <thead><tr><th>דייר</th><th>מס׳ צ׳ק</th><th>בנק / סניף / חשבון</th><th class="num">סכום</th><th class="num">תאריך פירעון</th><th>חודשים</th><th class="no-print"></th></tr></thead>
      <tbody>${
        rows
          .map(
            (p) => `<tr>
              <td class="strong">${esc(p.tenant_name || '')}</td>
              <td>${esc(p.check_number || '—')}</td>
              <td class="small">${esc([p.bank, p.branch, p.account].filter(Boolean).join(' / ') || '—')}</td>
              <td class="num">${money(p.amount_agorot)}</td>
              <td class="num">${dateHe(p.due_date || p.paid_date)}</td>
              <td class="pill-row">${p.allocations.map((a) => `<span class="badge muted">${esc(periodLabel(a.period))}</span>`).join(' ')}</td>
              <td class="no-print nowrap">${
                withActions
                  ? `<button class="btn sm" data-act="check-status" data-id="${p.id}" data-status="paid">נפרע</button>
                     <button class="btn sm danger" data-act="check-status" data-id="${p.id}" data-status="bounced">חזר</button>`
                  : `<button class="btn sm" data-act="edit-payment" data-id="${p.id}">עריכה</button>`
              }</td>
            </tr>`,
          )
          .join('') || '<tr><td colspan="7" class="empty">אין רשומות</td></tr>'
      }</tbody>
    </table></div>`;

  el('view').innerHTML = `
    <div class="page-head"><h1>צ׳קים</h1>
      <div class="toolbar"><button class="btn primary" data-act="new-payment" data-method="check">+ רישום צ׳ק</button></div>
    </div>
    <div class="card"><h2>ממתינים לפירעון (${groups.pending.length}) <span class="spacer"></span>
      <span class="sub">סה״כ ${money(groups.pending.reduce((a, p) => a + p.amount_agorot, 0))}</span></h2>${table(groups.pending, true)}</div>
    <div class="card"><h2>נפרעו (${groups.paid.length})</h2>${table(groups.paid, false)}</div>
    ${groups.bounced.length ? `<div class="card"><h2>צ׳קים שחזרו (${groups.bounced.length})</h2>${table(groups.bounced, false)}</div>` : ''}`;
}

/* ---------- חיפוש בחוזים ---------- */

async function renderSearch() {
  const data = state.search.data;
  const results = data
    ? data.results
        .map(
          (r) => `<div class="card">
            <div class="result-head">
              <h2 style="margin:0"><a href="#" data-act="open-contract" data-id="${r.contract_id}">${esc(r.title)}</a></h2>
              <span class="badge muted">${esc(r.tenant_name || '')}</span>
              <span class="badge muted">${esc(r.property_name || '')}</span>
              <span class="spacer"></span>
              <span class="sub">${r.matches.reduce((a, m) => a + m.count, 0)} התאמות</span>
            </div>
            ${r.matches
              .map(
                (m) => `<div class="match-group">
                  <div class="label">${esc(m.label)} · ${m.count} התאמות</div>
                  ${m.snippets.map((s) => `<div class="snippet">${markSnippet(s)}</div>`).join('')}
                </div>`,
              )
              .join('')}
          </div>`,
        )
        .join('')
    : '';

  el('view').innerHTML = `
    <div class="page-head"><h1>חיפוש בחוזים</h1></div>
    <div class="card">
      <div class="search-box">
        <input id="q" value="${esc(state.search.q)}" placeholder="לדוגמה: אופציה, פינוי, ועד בית, &quot;מדד המחירים&quot;" autofocus>
        <button class="btn primary" data-act="do-search">חיפוש</button>
      </div>
      <div class="help sub" style="margin-top:8px">
        כמה מילים = חייבות להופיע יחד · "מרכאות" = ביטוי מדויק · מילה עם מינוס לפניה (למשל <span class="mono">-ערבות</span>) = להוציא מהתוצאות.
        החיפוש מתעלם מניקוד ומאותיות סופיות, וסורק את נוסח החוזה, הקבצים שהועלו, ההערות ופרטי הדייר והנכס.
      </div>
    </div>
    ${data ? `<div class="sub" style="margin:10px 4px">${data.count} חוזים תואמים ל"${esc(data.q)}"</div>` : ''}
    ${results || (data ? '<div class="card empty">לא נמצאו תוצאות</div>' : '')}`;

  const input = el('q');
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') doSearch();
  });
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
}

async function doSearch() {
  const q = el('q').value.trim();
  state.search.q = q;
  state.search.data = q ? await api(`/api/search?q=${encodeURIComponent(q)}`) : null;
  state.textQuery = q;
  await renderSearch();
}

/* ---------- דיירים ונכסים ---------- */

async function renderTenants() {
  const list = await api('/api/tenants');
  el('view').innerHTML = `
    <div class="page-head"><h1>דיירים</h1>
      <div class="toolbar"><button class="btn primary" data-act="new-tenant">+ דייר חדש</button></div></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>שם</th><th>טלפון</th><th>דוא״ל</th><th>ת.ז.</th><th>הערות</th><th class="no-print"></th></tr></thead>
      <tbody>${
        list
          .map(
            (t) => `<tr>
              <td class="strong">${esc(t.name)}</td><td class="nowrap">${esc(t.phone)}</td><td>${esc(t.email)}</td>
              <td class="mono">${esc(t.national_id)}</td><td class="small">${esc(t.notes)}</td>
              <td class="no-print nowrap">
                <button class="btn sm" data-act="edit-tenant" data-id="${t.id}">עריכה</button>
                <button class="btn sm ghost" data-act="delete-tenant" data-id="${t.id}">מחיקה</button>
              </td></tr>`,
          )
          .join('') || '<tr><td colspan="6" class="empty">אין דיירים</td></tr>'
      }</tbody>
    </table></div></div>`;
}

async function renderProperties() {
  const list = await api('/api/properties');
  el('view').innerHTML = `
    <div class="page-head"><h1>נכסים</h1>
      <div class="toolbar"><button class="btn primary" data-act="new-property">+ נכס חדש</button></div></div>
    <div class="card"><div class="table-wrap"><table>
      <thead><tr><th>שם</th><th>כתובת</th><th>עיר</th><th>יחידה</th><th>הערות</th><th class="no-print"></th></tr></thead>
      <tbody>${
        list
          .map(
            (p) => `<tr>
              <td class="strong">${esc(p.name)}</td><td>${esc(p.address)}</td><td>${esc(p.city)}</td>
              <td>${esc(p.unit)}</td><td class="small">${esc(p.notes)}</td>
              <td class="no-print nowrap">
                <button class="btn sm" data-act="edit-property" data-id="${p.id}">עריכה</button>
                <button class="btn sm ghost" data-act="delete-property" data-id="${p.id}">מחיקה</button>
              </td></tr>`,
          )
          .join('') || '<tr><td colspan="6" class="empty">אין נכסים</td></tr>'
      }</tbody>
    </table></div></div>`;
}

/* ---------- הגדרות ---------- */

async function renderSettings() {
  el('view').innerHTML = `
    <div class="page-head"><h1>הגדרות וגיבוי</h1></div>
    <div class="card">
      <h2>גיבוי הנתונים</h2>
      <p class="sub">כל הנתונים נשמרים מקומית בתיקיית <span class="mono">data</span> שליד התוכנה. מומלץ להוריד גיבוי מדי פעם.</p>
      <div class="toolbar">
        <a class="btn primary" href="/api/backup">הורדת גיבוי (JSON)</a>
        <label class="btn">שחזור מגיבוי<input type="file" id="restore-input" class="hidden" accept=".json"></label>
        <a class="btn" href="/api/export/payments.csv">ייצוא תשלומים (CSV)</a>
        <a class="btn" href="/api/export/balances.csv?period=${state.period}">ייצוא יתרות (CSV)</a>
      </div>
      <div class="help">שחזור מוחק את כל הנתונים הקיימים ומחליף אותם בגיבוי. קבצי החוזה עצמם (PDF/Word) אינם נכללים בגיבוי – יש לגבות בנפרד את התיקייה <span class="mono">data/uploads</span>.</div>
    </div>
    <div class="card">
      <h2>נתוני דמו</h2>
      <p class="sub">טוען שלושה חוזים לדוגמה עם תשלומים, צ׳קים ונוסח חוזה – כדי להתרשם מהמערכת. פועל רק כשאין חוזים.</p>
      <button class="btn" data-act="load-demo">טעינת נתוני דמו</button>
    </div>
    <div class="card">
      <h2>איפוס</h2>
      <p class="sub">מחיקת כל הנכסים, הדיירים, החוזים והתשלומים. אין חזרה – כדאי להוריד גיבוי קודם.</p>
      <button class="btn danger" data-act="reset-all">מחיקת כל הנתונים</button>
    </div>`;

  const restore = el('restore-input');
  restore.addEventListener('change', async () => {
    const file = restore.files[0];
    if (!file) return;
    if (!confirm('השחזור ימחק את כל הנתונים הקיימים. להמשיך?')) return;
    try {
      const data = JSON.parse(await file.text());
      const res = await api('/api/restore', { method: 'POST', body: { data } });
      toast(`שוחזר בהצלחה (${Object.values(res.counts).reduce((a, b) => a + b, 0)} רשומות)`, 'ok');
      await boot();
    } catch (err) {
      toast(err.message, 'error');
    }
  });
}

/* ---------- כרטסת ---------- */

async function showStatement(contractId) {
  const data = await api(`/api/statement?contract_id=${contractId}`);
  const rows = data.events
    .map(
      (e) => `<tr>
        <td class="num nowrap">${dateHe(e.date)}</td>
        <td>${esc(e.label)}${e.type === 'pending' ? ' <span class="badge warn">ממתין</span>' : ''}${e.type === 'bounced' ? ' <span class="badge danger">חזר</span>' : ''}</td>
        <td class="num">${e.amount > 0 ? money(e.amount) : ''}</td>
        <td class="num">${e.amount < 0 ? money(-e.amount) : ''}</td>
        <td class="num strong">${money(e.balance)}</td>
      </tr>`,
    )
    .join('');
  openModal({
    title: `כרטסת – ${data.contract.tenant_name || ''} · ${data.contract.property_name || ''}`,
    wide: true,
    submitLabel: 'הדפסה',
    body: `<div class="table-wrap"><table>
        <thead><tr><th class="num">תאריך</th><th>תיאור</th><th class="num">חיוב</th><th class="num">תשלום</th><th class="num">יתרה</th></tr></thead>
        <tbody>${rows || '<tr><td colspan="5" class="empty">אין תנועות</td></tr>'}</tbody>
      </table></div>
      <div class="sub" style="margin-top:10px">סה״כ חויב ${money(data.summary.charged)} · שולם ${money(data.summary.paid)} · יתרה ${money(data.summary.balance)}</div>`,
    onSubmit: () => {
      const win = window.open('', '_blank');
      win.document.write(`<html dir="rtl" lang="he"><head><meta charset="utf-8"><title>כרטסת</title>
        <link rel="stylesheet" href="/styles.css"></head><body><main><div class="card">
        <h2>כרטסת – ${esc(data.contract.tenant_name || '')} · ${esc(data.contract.property_name || '')}</h2>
        <div class="sub">${esc(data.contract.property_address || '')}</div>
        <table><thead><tr><th>תאריך</th><th>תיאור</th><th class="num">חיוב</th><th class="num">תשלום</th><th class="num">יתרה</th></tr></thead>
        <tbody>${rows}</tbody></table>
        <p class="sub">סה״כ חויב ${money(data.summary.charged)} · שולם ${money(data.summary.paid)} · יתרה ${money(data.summary.balance)}</p>
        </div></main></body></html>`);
      win.document.close();
      setTimeout(() => win.print(), 300);
      return false;
    },
  });
}

/* ---------- טפסים ---------- */

function tenantForm(t = {}) {
  openModal({
    title: t.id ? 'עריכת דייר' : 'דייר חדש',
    body: `${field('שם מלא *', input('name', t.name, 'required'))}
      <div class="grid2">
        ${field('טלפון', input('phone', t.phone))}
        ${field('דוא״ל', input('email', t.email, 'type="email"'))}
      </div>
      ${field('תעודת זהות', input('national_id', t.national_id))}
      ${field('הערות', textarea('notes', t.notes))}`,
    onSubmit: async (v) => {
      await api(t.id ? `/api/tenants/${t.id}` : '/api/tenants', { method: t.id ? 'PUT' : 'POST', body: v });
      toast('נשמר', 'ok');
      await boot();
    },
  });
}

function propertyForm(p = {}) {
  openModal({
    title: p.id ? 'עריכת נכס' : 'נכס חדש',
    body: `${field('שם הנכס *', input('name', p.name, 'required placeholder="למשל: דירה ברחוב הרצל 12"'))}
      <div class="grid2">
        ${field('כתובת', input('address', p.address))}
        ${field('עיר', input('city', p.city))}
      </div>
      ${field('מספר יחידה / דירה', input('unit', p.unit))}
      ${field('הערות', textarea('notes', p.notes))}`,
    onSubmit: async (v) => {
      await api(p.id ? `/api/properties/${p.id}` : '/api/properties', { method: p.id ? 'PUT' : 'POST', body: v });
      toast('נשמר', 'ok');
      await boot();
    },
  });
}

function extraRow(extra = { label: '', amount_agorot: 0 }, idx) {
  return `<div class="inline-field" data-extra-row style="margin-bottom:6px">
    <input placeholder="תיאור (למשל ועד בית)" data-extra-label value="${esc(extra.label)}" style="flex:2">
    <input placeholder="סכום ₪" data-extra-amount value="${extra.amount_agorot ? (extra.amount_agorot / 100).toFixed(2) : ''}" style="flex:1">
    <button type="button" class="btn sm ghost" data-act="remove-extra">✕</button>
  </div>`;
}

function contractForm(c = {}) {
  const tenants = state.boot.tenants.map((t) => [t.id, t.name]);
  const properties = state.boot.properties.map((p) => [p.id, `${p.name}${p.address ? ` – ${p.address}` : ''}`]);
  if (!tenants.length || !properties.length) {
    toast('כדי ליצור חוזה צריך קודם להוסיף לפחות דייר אחד ונכס אחד', 'error');
    return;
  }
  openModal({
    title: c.id ? 'עריכת חוזה' : 'חוזה חדש',
    wide: true,
    body: `<div class="grid2">
        ${field('דייר *', select('tenant_id', tenants, c.tenant_id))}
        ${field('נכס *', select('property_id', properties, c.property_id))}
      </div>
      ${field('כותרת החוזה', input('title', c.title, 'placeholder="למשל: שכירות דירה – הרצל 12"'))}
      <div class="grid3">
        ${field('תחילת השכירות *', input('start_date', (c.start_date || todayISO()).slice(0, 10), 'type="date" required'))}
        ${field('סיום השכירות', input('end_date', (c.end_date || '').slice(0, 10), 'type="date"'), 'אפשר להשאיר ריק')}
        ${field('סטטוס', select('status', Object.entries(state.boot.contract_statuses), c.status || 'active'))}
      </div>
      <div class="grid3">
        ${field('שכר דירה חודשי (₪) *', input('rent', c.rent_agorot ? (c.rent_agorot / 100).toFixed(2) : '', 'required inputmode="decimal"'))}
        ${field('יום התשלום בחודש', input('payment_day', c.payment_day || 1, 'type="number" min="1" max="31"'))}
        ${field('אמצעי תשלום מוסכם', select('default_method', methodOptions(), c.default_method || 'bank_transfer'))}
      </div>
      <div class="grid2">
        ${field('ביטחונות / פיקדון (₪)', input('deposit', c.deposit_agorot ? (c.deposit_agorot / 100).toFixed(2) : ''))}
        ${field('סוג הביטחון', input('deposit_kind', c.deposit_kind, 'placeholder="שטר חוב / ערבות בנקאית / פיקדון"'))}
      </div>
      <div class="field">
        <label>תוספות קבועות לכל חודש</label>
        <div id="extras">${(c.extras || []).map(extraRow).join('')}</div>
        <button type="button" class="btn sm" data-act="add-extra">+ הוספת תוספת</button>
        <div class="help">למשל ועד בית, דמי ניהול או חניה – ייווספו אוטומטית לחיוב החודשי.</div>
      </div>
      <div class="field inline-field">
        <input type="checkbox" name="prorate" id="prorate" ${c.prorate === false ? '' : 'checked'}>
        <label for="prorate" style="margin:0">חישוב יחסי בחודש הראשון והאחרון (לפי מספר ימים)</label>
      </div>
      ${field('הערות', textarea('notes', c.notes))}
      ${field('נוסח החוזה (להדבקה וחיפוש)', textarea('contract_text', c.contract_text, 'style="min-height:160px"'), 'אפשר להדביק כאן את החוזה המלא, וגם להעלות קובץ אחרי השמירה.')}`,
    onSubmit: async (v, form) => {
      v.extras = [...form.querySelectorAll('[data-extra-row]')]
        .map((row) => ({
          label: row.querySelector('[data-extra-label]').value.trim(),
          amount: row.querySelector('[data-extra-amount]').value.trim(),
        }))
        .filter((e) => e.amount);
      const saved = await api(c.id ? `/api/contracts/${c.id}` : '/api/contracts', { method: c.id ? 'PUT' : 'POST', body: v });
      toast('החוזה נשמר', 'ok');
      await loadBootData();
      state.view = 'contract';
      state.contractId = saved.id || c.id;
      await render();
    },
  });
}

async function paymentForm(payment = {}, defaults = {}) {
  const contractId = payment.contract_id || defaults.contract_id || (state.boot.contracts[0] || {}).id;
  if (!contractId) {
    toast('אין חוזים במערכת – צריך ליצור חוזה לפני רישום תשלום', 'error');
    return;
  }
  const contract = await api(`/api/contracts/${contractId}`);
  const openPeriods = contract.periods.filter((p) => p.balance > 0);
  const suggested = defaults.period || (openPeriods[0] || {}).period || state.period;
  const suggestedAmount =
    defaults.amount !== undefined
      ? defaults.amount
      : payment.amount_agorot !== undefined
        ? payment.amount_agorot
        : (openPeriods.find((p) => p.period === suggested) || {}).balance || contract.rent_agorot;
  const currentPeriod = payment.id && payment.allocations && payment.allocations.length ? payment.allocations[0].period : suggested;

  const periodChoices = [
    ['__auto', 'אוטומטי – לזקוף לחוב הישן ביותר'],
    ...contract.periods
      .slice()
      .reverse()
      .map((p) => [p.period, `${p.label}${p.balance > 0 ? ` (חסר ${money(p.balance)})` : ' (מאוזן)'}`]),
    ['__none', 'ללא שיוך לחודש (מקדמה)'],
  ];

  openModal({
    title: payment.id ? 'עריכת תשלום' : 'רישום תשלום שהתקבל',
    wide: true,
    body: `${field('חוזה *', select('contract_id', contractOptions(), contractId, payment.id ? 'disabled' : 'data-reload-contract'))}
      <div class="grid3">
        ${field('סכום שהתקבל (₪) *', input('amount', (suggestedAmount / 100).toFixed(2), 'required inputmode="decimal"'))}
        ${field('תאריך קבלה *', input('paid_date', (payment.paid_date || todayISO()).slice(0, 10), 'type="date" required'))}
        ${field('אמצעי תשלום *', select('method', methodOptions(), payment.method || defaults.method || contract.default_method, 'id="method-select"'))}
      </div>
      <div class="grid2">
        ${field('שיוך לחודש', select('period_choice', periodChoices, payment.id ? currentPeriod : '__auto'))}
        ${field('סטטוס', select('status', statusOptions(), payment.status || ''), 'צ׳ק דחוי = "ממתין לפירעון"; יעודכן ל"שולם" כשייפרע.')}
      </div>
      <div id="method-fields"></div>
      ${field('הערות', textarea('notes', payment.notes, 'style="min-height:60px"'))}`,
    onSubmit: async (v) => {
      const body = {
        contract_id: payment.id ? payment.contract_id : v.contract_id,
        amount: v.amount,
        paid_date: v.paid_date,
        method: v.method,
        status: v.status,
        notes: v.notes,
        check_number: v.check_number || '',
        bank: v.bank || '',
        branch: v.branch || '',
        account: v.account || '',
        reference: v.reference || '',
        due_date: v.due_date || '',
      };
      if (v.period_choice === '__auto') body.auto_allocate = true;
      else if (v.period_choice === '__none') {
        body.auto_allocate = false;
        body.allocations = [];
      } else body.period = v.period_choice;
      await api(payment.id ? `/api/payments/${payment.id}` : '/api/payments', { method: payment.id ? 'PUT' : 'POST', body });
      toast('התשלום נשמר', 'ok');
      await render();
    },
  });

  const methodSelect = el('method-select');
  const renderMethodFields = () => {
    const m = methodSelect.value;
    const host = el('method-fields');
    if (m === 'check') {
      host.innerHTML = `<div class="grid3">
          ${field('מספר צ׳ק', input('check_number', payment.check_number))}
          ${field('בנק', input('bank', payment.bank))}
          ${field('סניף', input('branch', payment.branch))}
        </div>
        <div class="grid2">
          ${field('מספר חשבון', input('account', payment.account))}
          ${field('תאריך פירעון הצ׳ק', input('due_date', (payment.due_date || '').slice(0, 10), 'type="date"'))}
        </div>`;
    } else if (m === 'bank_transfer' || m === 'standing_order') {
      host.innerHTML = `<div class="grid3">
          ${field('אסמכתא', input('reference', payment.reference))}
          ${field('בנק', input('bank', payment.bank))}
          ${field('חשבון', input('account', payment.account))}
        </div>`;
    } else if (m === 'bit' || m === 'paybox' || m === 'credit_card') {
      host.innerHTML = field('אסמכתא / 4 ספרות אחרונות', input('reference', payment.reference));
    } else {
      host.innerHTML = field('פירוט', input('reference', payment.reference));
    }
    const statusSelect = $('#modal-form [name=status]');
    if (!payment.id) statusSelect.value = m === 'check' ? 'pending' : 'paid';
  };
  methodSelect.addEventListener('change', renderMethodFields);
  renderMethodFields();
  if (payment.status) $('#modal-form [name=status]').value = payment.status;

  const reload = $('#modal-form [data-reload-contract]');
  if (reload) {
    reload.addEventListener('change', () => {
      closeModal();
      paymentForm({}, { contract_id: Number(reload.value) });
    });
  }
}

function chargeForm(contractId, charge = {}) {
  openModal({
    title: charge.id ? 'עריכת חיוב' : 'חיוב נוסף',
    body: `${field('חודש *', input('period', charge.period || state.period, 'type="month" required'))}
      ${field('תיאור *', input('label', charge.label || '', 'required placeholder="למשל: תיקון דוד שמש / ארנונה"'))}
      <div class="grid2">
        ${field('סכום (₪) *', input('amount', charge.amount_agorot ? (charge.amount_agorot / 100).toFixed(2) : '', 'required inputmode="decimal"'))}
        ${field('תאריך יעד', input('due_date', (charge.due_date || '').slice(0, 10), 'type="date"'))}
      </div>
      ${charge.id ? `<div class="field inline-field"><input type="checkbox" name="canceled" id="canceled" ${charge.canceled ? 'checked' : ''}><label for="canceled" style="margin:0">ביטול החיוב (לא ייכלל ביתרה)</label></div>` : ''}
      ${field('הערות', textarea('notes', charge.notes))}`,
    onSubmit: async (v) => {
      await api(charge.id ? `/api/charges/${charge.id}` : '/api/charges', {
        method: charge.id ? 'PUT' : 'POST',
        body: { ...v, contract_id: contractId },
      });
      toast('נשמר', 'ok');
      await render();
    },
  });
}

function contractTextForm(contract) {
  openModal({
    title: 'נוסח החוזה',
    wide: true,
    body: field('הדבקת נוסח החוזה', textarea('contract_text', contract.contract_text, 'style="min-height:340px"'),
      'הטקסט נשמר במסד הנתונים ונכלל בחיפוש.'),
    onSubmit: async (v) => {
      const body = { ...contract, contract_text: v.contract_text, rent: (contract.rent_agorot / 100).toFixed(2), deposit: (contract.deposit_agorot / 100).toFixed(2) };
      body.extras = contract.extras.map((e) => ({ label: e.label, amount: (e.amount_agorot / 100).toFixed(2) }));
      await api(`/api/contracts/${contract.id}`, { method: 'PUT', body });
      toast('נשמר', 'ok');
      await render();
    },
  });
}

async function uploadFile(contractId, inputEl) {
  const file = inputEl.files[0];
  if (!file) return;
  if (file.size > 25 * 1024 * 1024) {
    toast('הקובץ גדול מ-25MB', 'error');
    return;
  }
  toast(`מעלה את ${file.name}…`);
  const buffer = await file.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < bytes.length; i += 8192) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192));
  }
  try {
    const res = await api(`/api/contracts/${contractId}/files`, {
      method: 'POST',
      body: { filename: file.name, mime: file.type, data_base64: btoa(binary) },
    });
    toast(res.note || `הקובץ הועלה (${res.text_length} תווים ניתנים לחיפוש)`, res.extract_status === 'ok' ? 'ok' : '');
    await render();
  } catch (err) {
    toast(err.message, 'error');
  }
}

/* ---------- ניתוב ותצוגה ---------- */

async function render() {
  try {
    if (state.view === 'dashboard') await renderDashboard();
    else if (state.view === 'contracts') await renderContracts();
    else if (state.view === 'contract') await renderContract();
    else if (state.view === 'payments') await renderPayments();
    else if (state.view === 'checks') await renderChecks();
    else if (state.view === 'search') await renderSearch();
    else if (state.view === 'tenants') await renderTenants();
    else if (state.view === 'properties') await renderProperties();
    else if (state.view === 'settings') await renderSettings();
    renderTabs();
  } catch (err) {
    toast(err.message, 'error');
  }
}

function renderTabs() {
  el('tabs').innerHTML = VIEWS.map(
    ([id, label]) =>
      `<button data-view="${id}" class="${state.view === id || (id === 'contracts' && state.view === 'contract') ? 'active' : ''}">${label}</button>`,
  ).join('');
}

async function loadBootData() {
  state.boot = await api('/api/bootstrap');
  if (!state.period) state.period = state.boot.current_period;
}

/* ---------- אירועים ---------- */

document.addEventListener('click', async (event) => {
  const tab = event.target.closest('#tabs button');
  if (tab) {
    state.view = tab.dataset.view;
    state.contractId = null;
    await render();
    return;
  }

  const node = event.target.closest('[data-act]');
  if (!node) return;
  const act = node.dataset.act;
  const id = Number(node.dataset.id);
  event.preventDefault();

  try {
    switch (act) {
      case 'modal-close':
        closeModal();
        break;
      case 'print':
        window.print();
        break;
      case 'prev-month':
      case 'next-month':
        state.period = addMonths(state.period, act === 'prev-month' ? -1 : 1);
        el('global-period').value = state.period;
        await render();
        break;
      case 'open-contract':
        state.view = 'contract';
        state.contractId = id;
        await render();
        break;
      case 'go-contracts':
        state.view = 'contracts';
        state.contractId = null;
        await render();
        break;
      case 'new-contract':
        contractForm();
        break;
      case 'edit-contract':
        contractForm(await api(`/api/contracts/${id}`));
        break;
      case 'delete-contract':
        if (!confirm('למחוק את החוזה על כל החיובים והתשלומים שלו?')) return;
        await api(`/api/contracts/${id}`, { method: 'DELETE' });
        toast('החוזה נמחק', 'ok');
        state.view = 'contracts';
        await loadBootData();
        await render();
        break;
      case 'edit-text':
        contractTextForm(await api(`/api/contracts/${id}`));
        break;
      case 'statement':
        await showStatement(id);
        break;
      case 'new-tenant':
        tenantForm();
        break;
      case 'edit-tenant':
        tenantForm(state.boot.tenants.find((t) => t.id === id));
        break;
      case 'delete-tenant':
        if (!confirm('למחוק את הדייר?')) return;
        await api(`/api/tenants/${id}`, { method: 'DELETE' });
        await loadBootData();
        await render();
        break;
      case 'new-property':
        propertyForm();
        break;
      case 'edit-property':
        propertyForm(state.boot.properties.find((p) => p.id === id));
        break;
      case 'delete-property':
        if (!confirm('למחוק את הנכס?')) return;
        await api(`/api/properties/${id}`, { method: 'DELETE' });
        await loadBootData();
        await render();
        break;
      case 'new-payment':
        await paymentForm(
          {},
          {
            contract_id: id || (state.view === 'contract' ? state.contractId : undefined),
            period: node.dataset.period,
            amount: node.dataset.amount ? Number(node.dataset.amount) : undefined,
            method: node.dataset.method,
          },
        );
        break;
      case 'edit-payment':
        await paymentForm(await api(`/api/payments/${id}`));
        break;
      case 'delete-payment':
        if (!confirm('למחוק את התשלום?')) return;
        await api(`/api/payments/${id}`, { method: 'DELETE' });
        toast('נמחק', 'ok');
        await render();
        break;
      case 'check-status':
        await api(`/api/payments/${id}`, { method: 'PUT', body: await paymentPatch(id, node.dataset.status) });
        toast(node.dataset.status === 'paid' ? 'סומן כנפרע' : 'סומן כצ׳ק שחזר', 'ok');
        await render();
        break;
      case 'new-charge':
        chargeForm(id);
        break;
      case 'edit-charge': {
        const charge = state.payload.charges.find((c) => c.id === id);
        chargeForm(state.contractId, charge);
        break;
      }
      case 'delete-charge':
        if (!confirm('למחוק את החיוב?')) return;
        await api(`/api/charges/${id}`, { method: 'DELETE' });
        await render();
        break;
      case 'delete-file':
        if (!confirm('למחוק את הקובץ?')) return;
        await api(`/api/files/${id}`, { method: 'DELETE' });
        await render();
        break;
      case 'file-text': {
        const data = await api(`/api/files/${id}/text`);
        openModal({
          title: `טקסט שחולץ – ${data.filename}`,
          wide: true,
          submitLabel: 'סגירה',
          body: `<div class="contract-text">${highlight(data.text, state.textQuery)}</div>`,
          onSubmit: () => true,
        });
        break;
      }
      case 'add-extra':
        el('extras').insertAdjacentHTML('beforeend', extraRow());
        break;
      case 'remove-extra':
        node.closest('[data-extra-row]').remove();
        break;
      case 'do-search':
        await doSearch();
        break;
      case 'clear-filters':
        state.filters = { method: '', status: '', contract_id: '', from: '', to: '' };
        await render();
        break;
      case 'load-demo':
        await api('/api/demo', { method: 'POST' });
        toast('נתוני הדמו נטענו', 'ok');
        await loadBootData();
        state.view = 'dashboard';
        await render();
        break;
      case 'reset-all':
        if (!confirm('למחוק את כל הנתונים? הפעולה בלתי הפיכה.')) return;
        await api('/api/reset', { method: 'POST', body: { confirm: 'מחק הכל' } });
        toast('הכל נמחק', 'ok');
        await loadBootData();
        await render();
        break;
      default:
        break;
    }
  } catch (err) {
    toast(err.message, 'error');
  }
});

/** שולף את פרטי התשלום הקיים כדי שעדכון סטטוס לא ימחק שדות. */
async function paymentPatch(paymentId, status) {
  const p = await api(`/api/payments/${paymentId}`);
  return {
    contract_id: p.contract_id,
    amount_agorot: p.amount_agorot,
    method: p.method,
    status,
    paid_date: p.paid_date,
    due_date: p.due_date || '',
    reference: p.reference,
    bank: p.bank,
    branch: p.branch,
    account: p.account,
    check_number: p.check_number,
    notes: p.notes,
    allocations: p.allocations.map((a) => ({ period: a.period, amount_agorot: a.amount_agorot })),
  };
}

document.addEventListener('submit', async (event) => {
  if (event.target.id === 'modal-form') {
    event.preventDefault();
    const form = event.target;
    const submitButton = $('button[type=submit]', form);
    submitButton.disabled = true;
    try {
      const keepOpen = await modalSubmit(formValues(form), form);
      if (keepOpen !== false) closeModal();
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      submitButton.disabled = false;
    }
    return;
  }
  if (event.target.id === 'login-form') {
    event.preventDefault();
    try {
      await api('/api/login', { method: 'POST', body: { passcode: el('passcode').value } });
      el('login').classList.add('hidden');
      await boot();
    } catch (err) {
      toast(err.message, 'error');
    }
  }
});

document.addEventListener('click', (event) => {
  if (event.target.matches('[data-close-backdrop]')) closeModal();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeModal();
});

function showLogin() {
  el('app').classList.add('hidden');
  el('login').classList.remove('hidden');
}

/* ---------- אתחול ---------- */

async function boot() {
  const auth = await fetch('/api/auth').then((r) => r.json());
  if (auth.required && !auth.authorized) {
    showLogin();
    return;
  }
  el('login').classList.add('hidden');
  el('app').classList.remove('hidden');
  await loadBootData();
  state.period = state.period || state.boot.current_period;
  const monthInput = el('global-period');
  monthInput.value = state.period;
  monthInput.addEventListener('change', async () => {
    if (!monthInput.value) return;
    state.period = monthInput.value;
    await render();
  });
  await render();
}

boot().catch((err) => toast(err.message, 'error'));
