'use strict';

const test = require('node:test');
const assert = require('node:assert');
const zlib = require('node:zlib');
const E = require('../src/extract');

/* ---------- בניית DOCX מינימלי לבדיקה ---------- */

function zipOne(name, content) {
  const nameBuf = Buffer.from(name, 'utf8');
  const raw = Buffer.from(content, 'utf8');
  const deflated = zlib.deflateRawSync(raw);

  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4);
  local.writeUInt16LE(8, 8); // deflate
  local.writeUInt32LE(0, 14); // crc (לא נבדק)
  local.writeUInt32LE(deflated.length, 18);
  local.writeUInt32LE(raw.length, 22);
  local.writeUInt16LE(nameBuf.length, 26);
  const localBlock = Buffer.concat([local, nameBuf, deflated]);

  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(20, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt16LE(8, 10);
  central.writeUInt32LE(0, 16);
  central.writeUInt32LE(deflated.length, 20);
  central.writeUInt32LE(raw.length, 24);
  central.writeUInt16LE(nameBuf.length, 28);
  central.writeUInt32LE(0, 42); // offset של הכותרת המקומית
  const centralBlock = Buffer.concat([central, nameBuf]);

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(1, 8);
  eocd.writeUInt16LE(1, 10);
  eocd.writeUInt32LE(centralBlock.length, 12);
  eocd.writeUInt32LE(localBlock.length, 16);

  return Buffer.concat([localBlock, centralBlock, eocd]);
}

test('חילוץ טקסט מ-DOCX', () => {
  const xml = `<?xml version="1.0"?><w:document><w:body>
    <w:p><w:r><w:t>הסכם שכירות</w:t></w:r></w:p>
    <w:p><w:r><w:t xml:space="preserve">דמי שכירות: 4,500 ש&quot;ח</w:t></w:r><w:tab/><w:r><w:t>לחודש</w:t></w:r></w:p>
  </w:body></w:document>`;
  const buf = zipOne('word/document.xml', xml);
  const result = E.extractText('חוזה.docx', '', buf);
  assert.equal(result.status, 'ok');
  assert.match(result.text, /הסכם שכירות/);
  assert.match(result.text, /4,500 ש"ח/);
  assert.match(result.text, /לחודש/);
});

/* ---------- PDF מינימלי ---------- */

function buildPdf(textOps) {
  const content = `BT /F1 12 Tf 72 720 Td ${textOps} ET`;
  const parts = [
    '%PDF-1.4\n',
    '1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n',
    '2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n',
    '3 0 obj << /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n',
    `4 0 obj << /Length ${content.length} >>\nstream\n${content}\nendstream\nendobj\n`,
    '5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n',
    'trailer << /Root 1 0 R /Size 6 >>\n%%EOF\n',
  ];
  return Buffer.from(parts.join(''), 'latin1');
}

test('חילוץ טקסט לטיני מ-PDF', () => {
  const result = E.extractText('contract.pdf', 'application/pdf', buildPdf('(Rent agreement: 4500 NIS per month) Tj'));
  assert.equal(result.status, 'ok');
  assert.match(result.text, /Rent agreement: 4500 NIS per month/);
});

test('חילוץ עברית מ-PDF בקידוד windows-1255', () => {
  const hebrew = Buffer.from('הסכם שכירות דירה בתל אביב', 'utf8');
  const cp1255 = [...'הסכם שכירות דירה בתל אביב'].map((ch) => {
    const code = ch.codePointAt(0);
    if (code >= 0x05d0 && code <= 0x05ea) return String.fromCharCode(code - 0x05d0 + 0xe0);
    return ch;
  }).join('');
  assert.ok(hebrew.length > 0);
  const result = E.extractText('חוזה.pdf', 'application/pdf', buildPdf(`(${cp1255}) Tj`));
  assert.match(result.text, /הסכם שכירות דירה בתל אביב/);
});

test('PDF ללא טקסט מסומן כלא ניתן לחיפוש', () => {
  const result = E.extractText('scan.pdf', 'application/pdf', Buffer.from('%PDF-1.4\n%%EOF\n', 'latin1'));
  assert.equal(result.status, 'empty');
  assert.match(result.note, /סריקה|להדביק/);
});

test('טקסט עברי בסדר ויזואלי מתהפך אוטומטית', () => {
  const logical = 'הסכם שכירות בין הצדדים לתקופה של שנה אחת עם אופציה להארכה נוספת בשנה';
  const visual = [...logical].reverse().join('');
  const fixed = E.fixVisualHebrew(visual);
  assert.equal(fixed, logical);
});

test('טקסט עברי תקין לא משתנה', () => {
  const logical = 'הסכם שכירות בין הצדדים לתקופה של שנה אחת עם אופציה להארכה נוספת בשנה';
  assert.equal(E.fixVisualHebrew(logical), logical);
});

test('קובץ טקסט בקידוד windows-1255 נקרא נכון', () => {
  const bytes = Buffer.from([0xe4, 0xe1, 0xe9, 0xfa]); // הבית
  const result = E.extractText('note.txt', 'text/plain', bytes);
  assert.equal(result.text, 'הבית');
});

test('סוג קובץ שאינו נתמך נשמר אך אינו נסרק', () => {
  const result = E.extractText('image.png', 'image/png', Buffer.from([0x89, 0x50, 0x4e, 0x47]));
  assert.equal(result.status, 'unsupported');
});
