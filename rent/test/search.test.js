'use strict';

const test = require('node:test');
const assert = require('node:assert');
const S = require('../src/search');

const CONTRACT = `הסכם שכירות בלתי מוגנת
1. תקופת השכירות: 12 חודשים עם אופציה להארכה בשנה נוספת.
2. דמי השכירות: 4,500 ש"ח לחודש, ישולמו עד ה-1 לכל חודש.
3. הביטחונות: שטר חוב וערבות אישית.
4. ועד בית וארנונה יחולו על השוכר.`;

const docs = () => [
  {
    contract_id: 1,
    tenant_name: 'דנה כהן',
    fields: [
      { key: 'meta', label: 'פרטים', weight: 3, text: 'דנה כהן | הרצל 12 | תל אביב' },
      { key: 'text', label: 'נוסח החוזה', weight: 1, text: CONTRACT },
    ],
  },
  {
    contract_id: 2,
    tenant_name: 'משה לוי',
    fields: [{ key: 'text', label: 'נוסח החוזה', weight: 1, text: 'שכירות חנות ללא אופציה. הארנונה על המשכיר.' }],
  },
];

test('נרמול: ניקוד, אותיות סופיות וגרשיים', () => {
  assert.equal(S.normalize('שָׁלוֹם').norm, 'שלומ');
  assert.equal(S.normalize('ש״ח').norm, 'ש"ח');
  assert.equal(S.normalize('בן־גוריון').norm, 'בנ גוריונ', 'מקף עברי מתפקד כרווח');
  assert.equal(S.normalize('ה-1 לחודש').norm, 'ה 1 לחודש');
  assert.equal(S.normalize('  רווחים   מרובים ').norm, 'רווחימ מרובימ ');
});

test('מציאת מילה בתוך נטייה עם אות חיבור', () => {
  const res = S.searchDocs(docs(), 'שכירות');
  assert.equal(res.results.length, 2);
  assert.equal(res.results[0].contract_id, 1, 'החוזה עם יותר התאמות ראשון');
});

test('כמה מילים = חייבות להופיע יחד', () => {
  assert.equal(S.searchDocs(docs(), 'אופציה הארכה').results.length, 1);
  assert.equal(S.searchDocs(docs(), 'אופציה חנות').results.length, 1);
  assert.equal(S.searchDocs(docs(), 'אופציה מרפסת').results.length, 0);
});

test('ביטוי מדויק במרכאות', () => {
  assert.equal(S.searchDocs(docs(), '"ועד בית"').results.length, 1);
  assert.equal(S.searchDocs(docs(), '"בית ועד"').results.length, 0);
});

test('החרגה עם מינוס', () => {
  const res = S.searchDocs(docs(), 'אופציה -חנות');
  assert.equal(res.results.length, 1);
  assert.equal(res.results[0].contract_id, 1);
});

test('חיפוש מספרים וסימני מטבע', () => {
  const res = S.searchDocs(docs(), '4,500');
  assert.equal(res.results.length, 1);
  const alt = S.searchDocs(docs(), 'ש"ח');
  assert.equal(alt.results.length, 1);
  const geresh = S.searchDocs(docs(), 'ש״ח');
  assert.equal(geresh.results.length, 1, 'גרשיים עבריים שקולים למרכאות');
});

test('קטע ההקשר מסמן את המונח במיקום הנכון', () => {
  const res = S.searchDocs(docs(), 'ערבות');
  const snippet = res.results[0].matches[0].snippets[0];
  const [start, end] = snippet.ranges[0];
  assert.equal(snippet.text.slice(start, end), 'ערבות', 'הסימון עומד בדיוק על המילה');
  assert.ok(snippet.text.includes('שטר חוב'), 'הקטע כולל את ההקשר סביב המילה');
});

test('חיפוש בפרטי הדייר ולא רק בטקסט', () => {
  const res = S.searchDocs(docs(), 'הרצל');
  assert.equal(res.results.length, 1);
  assert.equal(res.results[0].matches[0].key, 'meta');
});

test('שאילתה ריקה לא מחזירה הכל', () => {
  assert.equal(S.searchDocs(docs(), '   ').results.length, 0);
});
