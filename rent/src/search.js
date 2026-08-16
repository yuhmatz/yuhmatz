'use strict';

/*
 * חיפוש טקסט חופשי בחוזים – מותאם לעברית:
 *  - התעלמות מניקוד, גרשיים, מקף עברי וסימני כיווניות
 *  - אותיות סופיות מנורמלות (ם/מ, ן/נ, ך/כ, ף/פ, ץ/צ) כדי שחיפוש יתפוס גם נטיות
 *  - חיפוש תת־מחרוזת, כך ש"שכירות" נמצא גם בתוך "והשכירות"
 *  - תחביר: כמה מילים = AND, "ציטוט מדויק", מילה- להוצאה
 */

const FINALS = { 'ך': 'כ', 'ם': 'מ', 'ן': 'נ', 'ף': 'פ', 'ץ': 'צ' };
const PUNCT_MAP = {
  '׳': "'", // גרש
  '״': '"', // גרשיים
  '’': "'",
  '‘': "'",
  '“': '"',
  '”': '"',
};
// ניקוד, טעמים וסימני כיווניות – נמחקים לגמרי
const DASH_RE = /[-\u05BE\u2010-\u2015]/;
const DROP_RE = /[\u0591-\u05BD\u05BF-\u05C7\u200B-\u200F\u202A-\u202E\u2066-\u2069\uFEFF]/;

/**
 * מנרמל טקסט ומחזיר גם מיפוי מיקומים חזרה למחרוזת המקורית.
 * @returns {{norm: string, map: number[]}}
 */
function normalize(text) {
  const src = String(text == null ? '' : text);
  let norm = '';
  const map = [];
  let prevWasSpace = true;
  for (let i = 0; i < src.length; i += 1) {
    const ch = src[i];
    if (DROP_RE.test(ch)) continue;
    if (/\s/.test(ch) || DASH_RE.test(ch)) {
      if (prevWasSpace) continue;
      norm += ' ';
      map.push(i);
      prevWasSpace = true;
      continue;
    }
    prevWasSpace = false;
    let out = PUNCT_MAP[ch] || FINALS[ch] || ch;
    const lower = out.toLowerCase();
    if (lower.length === 1) out = lower;
    norm += out;
    map.push(i);
  }
  map.push(src.length); // שומר על גישה בטוחה לסוף
  return { norm, map };
}

function normalizeQueryTerm(term) {
  return normalize(term).norm.trim();
}

/**
 * פירוק שאילתה: מילים רגילות, "ביטוי מדויק", ומינוס להחרגה.
 * @returns {{include: string[], exclude: string[], raw: string}}
 */
function parseQuery(q) {
  const include = [];
  const exclude = [];
  const re = /(-?)"([^"]*)"|(-?)(\S+)/g;
  let m;
  while ((m = re.exec(String(q || ''))) !== null) {
    const neg = (m[1] || m[3]) === '-';
    const term = normalizeQueryTerm(m[2] !== undefined ? m[2] : m[4]);
    if (!term) continue;
    (neg ? exclude : include).push(term);
  }
  return { include, exclude, raw: String(q || '') };
}

/** כל מופעי needle ב-hay (ללא חפיפה). */
function findAll(hay, needle) {
  const out = [];
  if (!needle) return out;
  let idx = hay.indexOf(needle);
  while (idx !== -1) {
    out.push(idx);
    idx = hay.indexOf(needle, idx + needle.length);
  }
  return out;
}

/**
 * מחפש בשדה טקסט אחד ומחזיר מונים וקטעי הקשר עם סימון.
 * @returns {{count:number, snippets:{text:string, ranges:[number,number][]}[]}|null}
 */
function searchField(text, query, opts = {}) {
  const { maxSnippets = 3, context = 90 } = opts;
  const original = String(text == null ? '' : text);
  if (!original.trim()) return null;
  const { norm, map } = normalize(original);
  if (!norm) return null;

  for (const term of query.exclude) {
    if (norm.includes(term)) return null;
  }
  const hits = [];
  for (const term of query.include) {
    const positions = findAll(norm, term);
    if (positions.length === 0) return null; // AND
    for (const pos of positions) hits.push({ start: pos, end: pos + term.length });
  }
  if (hits.length === 0) return null;

  hits.sort((a, b) => a.start - b.start);
  const snippets = [];
  let i = 0;
  while (i < hits.length && snippets.length < maxSnippets) {
    const from = Math.max(0, hits[i].start - context);
    const windowEnd = hits[i].end + context;
    const group = [];
    while (i < hits.length && hits[i].start <= windowEnd) {
      group.push(hits[i]);
      i += 1;
    }
    const to = Math.min(norm.length, group[group.length - 1].end + context);
    const oStart = map[from] ?? 0;
    const oEnd = map[Math.min(to, map.length - 1)] ?? original.length;
    const raw = original.slice(oStart, oEnd);
    const ranges = group.map((h) => {
      const s = (map[h.start] ?? oStart) - oStart;
      const e = (map[Math.min(h.end, map.length - 1)] ?? oEnd) - oStart;
      return [Math.max(0, s), Math.max(0, e)];
    });
    // החלפת שורות ברווח היא 1:1, כך שמיקומי הסימון נשארים תקפים
    const flat = raw.replace(/[\r\n\t]/g, ' ');
    const lead = oStart > 0 ? '…' : '';
    snippets.push({
      text: lead + flat + (oEnd < original.length ? '…' : ''),
      ranges: lead ? ranges.map(([s, e]) => [s + 1, e + 1]) : ranges,
    });
  }
  return { count: hits.length, snippets };
}

/**
 * חיפוש רוחבי בכל החוזים.
 * @param {object[]} docs [{contract_id, tenant_name, property_name, fields:[{key,label,text}]}]
 */
function searchDocs(docs, q, opts = {}) {
  const query = parseQuery(q);
  if (query.include.length === 0) return { query, results: [] };
  const results = [];
  for (const doc of docs) {
    const matches = [];
    let score = 0;
    for (const field of doc.fields) {
      const hit = searchField(field.text, query, opts);
      if (!hit) continue;
      const weight = field.weight || 1;
      score += hit.count * weight;
      matches.push({ key: field.key, label: field.label, count: hit.count, snippets: hit.snippets });
    }
    if (matches.length > 0) results.push({ ...doc, fields: undefined, matches, score });
  }
  results.sort((a, b) => b.score - a.score);
  return { query, results };
}

module.exports = { normalize, parseQuery, findAll, searchField, searchDocs, normalizeQueryTerm };
