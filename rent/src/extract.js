'use strict';

/*
 * חילוץ טקסט מקבצי חוזה, ללא ספריות חיצוניות:
 *   TXT/MD/CSV  – פענוח UTF-8 ואם צריך windows-1255
 *   DOCX/ODT    – קריאת ZIP פנימית + שליפת הטקסט מה-XML
 *   PDF         – חילוץ "מיטב המאמץ": פריסת אובייקטים, פענוח זרמים,
 *                 שימוש במפות ToUnicode והיפוך שורות עבריות שנשמרו בסדר ויזואלי.
 * קובץ PDF סרוק (תמונה) לא ניתן לחילוץ – במקרה כזה מוחזר status=empty
 * והמשתמש יכול להדביק את נוסח החוזה ידנית לשדה הטקסט.
 */

const zlib = require('node:zlib');

/* ---------- טקסט פשוט ---------- */

function decodeText(buf) {
  try {
    return new TextDecoder('utf-8', { fatal: true }).decode(buf);
  } catch {
    try {
      return new TextDecoder('windows-1255').decode(buf);
    } catch {
      return buf.toString('latin1');
    }
  }
}

/* ---------- ZIP (עבור DOCX/ODT) ---------- */

function readZip(buf) {
  const files = new Map();
  let eocd = -1;
  for (let i = buf.length - 22; i >= 0 && i > buf.length - 66000; i -= 1) {
    if (buf.readUInt32LE(i) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error('not a zip file');
  const count = buf.readUInt16LE(eocd + 10);
  let ptr = buf.readUInt32LE(eocd + 16);

  for (let n = 0; n < count && ptr + 46 <= buf.length; n += 1) {
    if (buf.readUInt32LE(ptr) !== 0x02014b50) break;
    const method = buf.readUInt16LE(ptr + 10);
    const compSize = buf.readUInt32LE(ptr + 20);
    const nameLen = buf.readUInt16LE(ptr + 28);
    const extraLen = buf.readUInt16LE(ptr + 30);
    const commentLen = buf.readUInt16LE(ptr + 32);
    const localOffset = buf.readUInt32LE(ptr + 42);
    const name = buf.slice(ptr + 46, ptr + 46 + nameLen).toString('utf8');
    ptr += 46 + nameLen + extraLen + commentLen;

    if (localOffset + 30 > buf.length || buf.readUInt32LE(localOffset) !== 0x04034b50) continue;
    const lNameLen = buf.readUInt16LE(localOffset + 26);
    const lExtraLen = buf.readUInt16LE(localOffset + 28);
    const dataStart = localOffset + 30 + lNameLen + lExtraLen;
    const raw = buf.slice(dataStart, dataStart + (compSize || buf.length - dataStart));
    try {
      files.set(name, method === 0 ? raw : zlib.inflateRawSync(raw));
    } catch {
      /* מדלגים על ערך פגום */
    }
  }
  return files;
}

function decodeEntities(s) {
  return s
    .replace(/&#x([0-9a-fA-F]+);/g, (_, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&#(\d+);/g, (_, d) => String.fromCodePoint(Number(d)))
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
}

function xmlToText(xml, paragraphTags) {
  let s = xml;
  s = s.replace(/<w:tab[^>]*\/>/g, '\t').replace(/<text:tab[^>]*\/>/g, '\t');
  s = s.replace(/<w:br[^>]*\/>/g, '\n').replace(/<text:line-break[^>]*\/>/g, '\n');
  for (const tag of paragraphTags) {
    s = s.replace(new RegExp(`</${tag}>`, 'g'), '\n');
  }
  s = s.replace(/<[^>]*>/g, '');
  return decodeEntities(s)
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function docxText(buf) {
  const zip = readZip(buf);
  const parts = [];
  for (const name of ['word/document.xml', 'word/header1.xml', 'word/footer1.xml']) {
    const entry = zip.get(name);
    if (entry) parts.push(xmlToText(entry.toString('utf8'), ['w:p']));
  }
  const odt = zip.get('content.xml');
  if (odt && parts.length === 0) parts.push(xmlToText(odt.toString('utf8'), ['text:p', 'text:h']));
  return parts.filter(Boolean).join('\n\n');
}

/* ---------- PDF ---------- */

function inflateMaybe(bufSlice) {
  const attempts = [zlib.inflateSync, zlib.inflateRawSync];
  for (const fn of attempts) {
    try {
      return fn(bufSlice);
    } catch {
      /* ננסה את הבא */
    }
  }
  return null;
}

/** מפרק את גוף ה-PDF לאובייקטים ממוספרים, כולל אלה שבתוך Object Streams. */
function pdfObjects(buf) {
  const latin = buf.toString('latin1');
  const objects = new Map();
  const objRe = /(\d+)\s+\d+\s+obj\b/g;
  let m;
  while ((m = objRe.exec(latin)) !== null) {
    const num = Number(m[1]);
    const bodyStart = m.index + m[0].length;
    const endIdx = latin.indexOf('endobj', bodyStart);
    const body = latin.slice(bodyStart, endIdx === -1 ? Math.min(bodyStart + 200000, latin.length) : endIdx);
    const streamIdx = body.indexOf('stream');
    let dict = body;
    let data = null;
    if (streamIdx !== -1) {
      dict = body.slice(0, streamIdx);
      let s = bodyStart + streamIdx + 'stream'.length;
      if (latin[s] === '\r') s += 1;
      if (latin[s] === '\n') s += 1;
      const endStream = latin.indexOf('endstream', s);
      if (endStream !== -1) data = buf.slice(s, endStream);
    }
    objects.set(num, { dict, data });
  }

  // אובייקטים דחוסים (PDF 1.5+)
  for (const [, obj] of [...objects]) {
    if (!obj.data || !/\/Type\s*\/ObjStm/.test(obj.dict)) continue;
    const inflated = inflateMaybe(obj.data);
    if (!inflated) continue;
    const text = inflated.toString('latin1');
    const n = Number((obj.dict.match(/\/N\s+(\d+)/) || [])[1] || 0);
    const first = Number((obj.dict.match(/\/First\s+(\d+)/) || [])[1] || 0);
    const header = text.slice(0, first).trim().split(/\s+/).map(Number);
    for (let i = 0; i < n; i += 1) {
      const num = header[i * 2];
      const off = header[i * 2 + 1];
      if (!Number.isFinite(num) || !Number.isFinite(off)) continue;
      const nextOff = i + 1 < n ? header[i * 2 + 3] : text.length - first;
      const chunk = text.slice(first + off, first + (Number.isFinite(nextOff) ? nextOff : text.length));
      if (!objects.has(num)) objects.set(num, { dict: chunk, data: null });
    }
  }
  return objects;
}

/** פענוח מפת ToUnicode -> Map<code, string> */
function parseCMap(text) {
  const map = new Map();
  let codeBytes = 1;
  const hex = (h) => {
    let out = '';
    for (let i = 0; i + 3 < h.length + 1; i += 4) {
      const code = parseInt(h.slice(i, i + 4), 16);
      if (Number.isFinite(code)) out += String.fromCharCode(code);
    }
    return out;
  };

  const bfcharRe = /beginbfchar([\s\S]*?)endbfchar/g;
  let m;
  while ((m = bfcharRe.exec(text)) !== null) {
    const pairRe = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]*)>/g;
    let p;
    while ((p = pairRe.exec(m[1])) !== null) {
      if (p[1].length >= 4) codeBytes = 2;
      map.set(parseInt(p[1], 16), hex(p[2]));
    }
  }
  const bfrangeRe = /beginbfrange([\s\S]*?)endbfrange/g;
  while ((m = bfrangeRe.exec(text)) !== null) {
    const body = m[1];
    const rangeRe = /<([0-9a-fA-F]+)>\s*<([0-9a-fA-F]+)>\s*(?:<([0-9a-fA-F]*)>|\[([\s\S]*?)\])/g;
    let r;
    while ((r = rangeRe.exec(body)) !== null) {
      const lo = parseInt(r[1], 16);
      const hi = parseInt(r[2], 16);
      if (r[1].length >= 4) codeBytes = 2;
      if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi - lo > 65535) continue;
      if (r[3] !== undefined) {
        const base = parseInt(r[3], 16);
        for (let c = lo; c <= hi; c += 1) {
          map.set(c, String.fromCharCode(base + (c - lo)));
        }
      } else {
        const items = r[4].match(/<([0-9a-fA-F]*)>/g) || [];
        items.forEach((item, idx) => {
          map.set(lo + idx, hex(item.replace(/[<>]/g, '')));
        });
      }
    }
  }
  return { map, codeBytes };
}

/** מפרק מחרוזת PDF ל-array של קודי בייט. */
function pdfLiteralBytes(str) {
  const out = [];
  for (let i = 0; i < str.length; i += 1) {
    const ch = str[i];
    if (ch !== '\\') {
      out.push(str.charCodeAt(i) & 0xff);
      continue;
    }
    const next = str[i + 1];
    i += 1;
    switch (next) {
      case 'n': out.push(10); break;
      case 'r': out.push(13); break;
      case 't': out.push(9); break;
      case 'b': out.push(8); break;
      case 'f': out.push(12); break;
      case '\n': break;
      case '\r': if (str[i + 1] === '\n') i += 1; break;
      default:
        if (next >= '0' && next <= '7') {
          let oct = next;
          while (oct.length < 3 && str[i + 1] >= '0' && str[i + 1] <= '7') {
            oct += str[i + 1];
            i += 1;
          }
          out.push(parseInt(oct, 8) & 0xff);
        } else if (next !== undefined) {
          out.push(next.charCodeAt(0) & 0xff);
        }
    }
  }
  return out;
}

const WIN1255 = (() => {
  try {
    return new TextDecoder('windows-1255');
  } catch {
    return null;
  }
})();

function bytesToText(bytes, cmap) {
  if (cmap && cmap.map.size) {
    let out = '';
    if (cmap.codeBytes === 2) {
      for (let i = 0; i + 1 < bytes.length; i += 2) {
        const code = (bytes[i] << 8) | bytes[i + 1];
        out += cmap.map.has(code) ? cmap.map.get(code) : '';
      }
    } else {
      for (const b of bytes) out += cmap.map.has(b) ? cmap.map.get(b) : String.fromCharCode(b);
    }
    return out;
  }
  const buf = Buffer.from(bytes);
  if (WIN1255 && bytes.some((b) => b >= 0x80)) return WIN1255.decode(buf);
  return buf.toString('latin1');
}

/** מריץ טוקנייזר קטן על זרם התוכן ומחזיר את הטקסט המוצג. */
function contentStreamText(content, fontCMaps, fallbackCMap) {
  let out = '';
  let current = fallbackCMap;
  let i = 0;
  const pushStr = (bytes) => {
    out += bytesToText(bytes, current);
  };
  while (i < content.length) {
    const ch = content[i];
    if (ch === '(') {
      let depth = 1;
      let j = i + 1;
      let literal = '';
      while (j < content.length && depth > 0) {
        const c = content[j];
        if (c === '\\') {
          literal += c + (content[j + 1] || '');
          j += 2;
          continue;
        }
        if (c === '(') depth += 1;
        if (c === ')') {
          depth -= 1;
          if (depth === 0) break;
        }
        literal += c;
        j += 1;
      }
      pushStr(pdfLiteralBytes(literal));
      i = j + 1;
      continue;
    }
    if (ch === '<' && content[i + 1] !== '<') {
      const end = content.indexOf('>', i);
      if (end === -1) break;
      const hexStr = content.slice(i + 1, end).replace(/[^0-9a-fA-F]/g, '');
      const bytes = [];
      for (let k = 0; k + 1 < hexStr.length + 1; k += 2) {
        const pair = hexStr.slice(k, k + 2).padEnd(2, '0');
        bytes.push(parseInt(pair, 16));
      }
      pushStr(bytes);
      i = end + 1;
      continue;
    }
    const opMatch = /^(\/[A-Za-z0-9#+._-]+)\s+[\d.]+\s+Tf|^(T\*|TD|Td|Tm|ET|TJ|Tj)\b|^(-?[\d.]+)/.exec(content.slice(i, i + 60));
    if (opMatch) {
      if (opMatch[1]) {
        const name = opMatch[1].slice(1);
        current = fontCMaps.get(name) || fallbackCMap;
      } else if (opMatch[2] && opMatch[2] !== 'TJ' && opMatch[2] !== 'Tj') {
        out += '\n';
      } else if (opMatch[3]) {
        const kern = parseFloat(opMatch[3]);
        if (kern <= -150) out += ' ';
      }
      i += opMatch[0].length;
      continue;
    }
    i += 1;
  }
  return out;
}

/** טקסט שנשמר בסדר ויזואלי מזוהה לפי אותיות סופיות בתחילת מילה. */
function fixVisualHebrew(text) {
  const words = text.match(/[֐-׿]{2,}/g) || [];
  if (words.length < 8) return text;
  let starts = 0;
  let ends = 0;
  for (const w of words) {
    if (/^[ךםןףץ]/.test(w)) starts += 1;
    if (/[ךםןףץ]$/.test(w)) ends += 1;
  }
  if (starts > ends && starts / words.length > 0.15) {
    return text
      .split('\n')
      .map((line) => [...line].reverse().join(''))
      .join('\n');
  }
  return text;
}

function pdfText(buf) {
  const objects = pdfObjects(buf);
  const cmaps = new Map(); // objNum -> cmap
  const fontToCMap = new Map(); // font objNum -> cmap
  const nameToCMap = new Map(); // /F1 -> cmap

  for (const [num, obj] of objects) {
    if (!obj.data) continue;
    const inflated = /\/Filter/.test(obj.dict) ? inflateMaybe(obj.data) : obj.data;
    if (!inflated) continue;
    const text = inflated.toString('latin1');
    if (text.includes('beginbfchar') || text.includes('beginbfrange')) {
      cmaps.set(num, parseCMap(text));
    }
  }
  for (const [num, obj] of objects) {
    const ref = obj.dict.match(/\/ToUnicode\s+(\d+)\s+\d+\s+R/);
    if (ref && cmaps.has(Number(ref[1]))) fontToCMap.set(num, cmaps.get(Number(ref[1])));
  }
  for (const [, obj] of objects) {
    const fontDict = obj.dict.match(/\/Font\s*<<([\s\S]*?)>>/);
    if (!fontDict) continue;
    const entryRe = /\/([A-Za-z0-9#+._-]+)\s+(\d+)\s+\d+\s+R/g;
    let e;
    while ((e = entryRe.exec(fontDict[1])) !== null) {
      const cmap = fontToCMap.get(Number(e[2]));
      if (cmap) nameToCMap.set(e[1], cmap);
    }
  }
  // מפה ממוזגת כגיבוי כשלא הצלחנו לקשר גופן לשם
  let fallback = null;
  if (cmaps.size === 1) [fallback] = [...cmaps.values()];
  else if (cmaps.size > 1) {
    const merged = new Map();
    let codeBytes = 1;
    for (const c of cmaps.values()) {
      codeBytes = Math.max(codeBytes, c.codeBytes);
      for (const [k, v] of c.map) if (!merged.has(k)) merged.set(k, v);
    }
    fallback = { map: merged, codeBytes };
  }

  const chunks = [];
  for (const [, obj] of objects) {
    if (!obj.data) continue;
    if (/\/Subtype\s*\/Image/.test(obj.dict) || /\/Type\s*\/ObjStm/.test(obj.dict)) continue;
    const inflated = /\/Filter/.test(obj.dict) ? inflateMaybe(obj.data) : obj.data;
    if (!inflated) continue;
    const content = inflated.toString('latin1');
    if (!/\bBT\b/.test(content) || !/(Tj|TJ)\b/.test(content)) continue;
    const text = contentStreamText(content, nameToCMap, fallback);
    if (text.trim()) chunks.push(text);
  }

  const joined = chunks
    .join('\n')
    .replace(/\u0000/g, "")
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  return fixVisualHebrew(joined);
}

/* ---------- נקודת כניסה ---------- */

function letterCount(text) {
  return (text.match(/[֐-׿A-Za-z]/g) || []).length;
}

/**
 * @returns {{text:string, status:'ok'|'empty'|'unsupported'|'error', note:string}}
 */
function extractText(filename, mime, buf) {
  const ext = String(filename || '').toLowerCase().split('.').pop();
  const emptyNote =
    'לא נמצא טקסט בקובץ (כנראה סריקה/תמונה). אפשר להדביק את נוסח החוזה בשדה "נוסח החוזה" כדי לאפשר חיפוש.';
  try {
    if (['txt', 'md', 'csv', 'json', 'html', 'htm'].includes(ext) || String(mime).startsWith('text/')) {
      const text = decodeText(buf).replace(/\r\n/g, '\n');
      return { text, status: letterCount(text) > 5 ? 'ok' : 'empty', note: letterCount(text) > 5 ? '' : emptyNote };
    }
    if (['docx', 'odt', 'dotx'].includes(ext)) {
      const text = docxText(buf);
      return { text, status: letterCount(text) > 5 ? 'ok' : 'empty', note: letterCount(text) > 5 ? '' : emptyNote };
    }
    if (ext === 'pdf' || mime === 'application/pdf') {
      const text = pdfText(buf);
      return { text, status: letterCount(text) > 20 ? 'ok' : 'empty', note: letterCount(text) > 20 ? '' : emptyNote };
    }
    return { text: '', status: 'unsupported', note: 'סוג הקובץ נשמר אך אינו ניתן לחיפוש טקסט (רק PDF/DOCX/TXT נסרקים).' };
  } catch (err) {
    return { text: '', status: 'error', note: `שגיאה בקריאת הקובץ: ${err.message}` };
  }
}

module.exports = { extractText, decodeText, readZip, docxText, pdfText, xmlToText, fixVisualHebrew, parseCMap };
