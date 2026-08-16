'use strict';

/*
 * שרת מקומי למערכת גביית שכר דירה.
 * הרצה:  node server.js          (ברירת מחדל: http://localhost:4173)
 * אפשרויות סביבה:
 *   PORT=5000            – פורט אחר
 *   RENT_DATA=/path/dir  – תיקיית נתונים (ברירת מחדל: ./data)
 *   RENT_PASSCODE=1234   – דורש קוד כניסה (מומלץ אם פותחים לרשת המקומית)
 *   RENT_HOST=0.0.0.0    – האזנה לכל הכתובות (גישה מהטלפון באותה רשת)
 */

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const dbLib = require('./src/db');
const { createRouter, ApiError } = require('./src/api');

const PORT = Number(process.env.PORT || 4173);
const HOST = process.env.RENT_HOST || '127.0.0.1';
const DATA_DIR = process.env.RENT_DATA || path.join(__dirname, 'data');
const UPLOADS_DIR = path.join(DATA_DIR, 'uploads');
const PUBLIC_DIR = path.join(__dirname, 'public');
const PASSCODE = process.env.RENT_PASSCODE || '';
const MAX_BODY = 30 * 1024 * 1024;

fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const db = dbLib.open(path.join(DATA_DIR, 'rent.db'));
const router = createRouter({ db, uploadsDir: UPLOADS_DIR });
const sessions = new Set();

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.ico': 'image/x-icon',
  '.pdf': 'application/pdf',
  '.txt': 'text/plain; charset=utf-8',
  '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
};

function sendJSON(res, status, data) {
  const body = JSON.stringify(data);
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', (chunk) => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(new ApiError(413, 'הבקשה גדולה מדי'));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on('end', () => {
      const raw = Buffer.concat(chunks).toString('utf8');
      if (!raw) return resolve({});
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new ApiError(400, 'גוף בקשה לא תקין (JSON)'));
      }
    });
    req.on('error', reject);
  });
}

function parseCookies(header) {
  const out = {};
  for (const part of String(header || '').split(';')) {
    const idx = part.indexOf('=');
    if (idx === -1) continue;
    out[part.slice(0, idx).trim()] = part.slice(idx + 1).trim();
  }
  return out;
}

function authorized(req) {
  if (!PASSCODE) return true;
  const token = parseCookies(req.headers.cookie).rent_session;
  return !!token && sessions.has(token);
}

function serveStatic(req, res, pathname) {
  const rel = pathname === '/' ? 'index.html' : pathname.replace(/^\/+/, '');
  const target = path.join(PUBLIC_DIR, rel);
  if (!target.startsWith(PUBLIC_DIR)) {
    res.writeHead(403).end('forbidden');
    return;
  }
  fs.readFile(target, (err, data) => {
    if (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('לא נמצא');
      return;
    }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(target)] || 'application/octet-stream', 'Cache-Control': 'no-cache' });
    res.end(data);
  });
}

/** הורדת קובץ חוזה מקורי. */
function serveUpload(req, res, id) {
  const row = dbLib.get(db, 'SELECT * FROM contract_files WHERE id = ?', [Number(id)]);
  if (!row) return sendJSON(res, 404, { error: 'הקובץ לא נמצא' });
  const target = path.join(UPLOADS_DIR, row.stored_name);
  if (!target.startsWith(UPLOADS_DIR) || !fs.existsSync(target)) {
    return sendJSON(res, 404, { error: 'הקובץ נמחק מהדיסק' });
  }
  const encoded = encodeURIComponent(row.filename);
  res.writeHead(200, {
    'Content-Type': row.mime || MIME[path.extname(row.filename)] || 'application/octet-stream',
    'Content-Disposition': `inline; filename*=UTF-8''${encoded}`,
  });
  fs.createReadStream(target).pipe(res);
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = decodeURIComponent(url.pathname);
  const query = Object.fromEntries(url.searchParams.entries());

  try {
    if (pathname === '/api/login' && req.method === 'POST') {
      const body = await readBody(req);
      if (!PASSCODE || String(body.passcode || '') !== PASSCODE) {
        return sendJSON(res, 401, { error: 'קוד כניסה שגוי' });
      }
      const token = crypto.randomBytes(24).toString('hex');
      sessions.add(token);
      res.setHeader('Set-Cookie', `rent_session=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800`);
      return sendJSON(res, 200, { ok: true });
    }
    if (pathname === '/api/auth' && req.method === 'GET') {
      return sendJSON(res, 200, { required: !!PASSCODE, authorized: authorized(req) });
    }

    if (pathname.startsWith('/api/') || pathname.startsWith('/files/')) {
      if (!authorized(req)) return sendJSON(res, 401, { error: 'נדרשת כניסה' });
    }

    if (pathname.startsWith('/files/') && req.method === 'GET') {
      return serveUpload(req, res, pathname.split('/')[2]);
    }

    if (pathname.startsWith('/api/')) {
      const body = ['POST', 'PUT', 'PATCH'].includes(req.method) ? await readBody(req) : {};
      const result = router.dispatch(req.method, pathname, query, body);
      if (result && result.__raw !== undefined) {
        res.writeHead(200, {
          'Content-Type': result.__type,
          'Content-Disposition': `attachment; filename="${result.__filename}"`,
          'Cache-Control': 'no-store',
        });
        return res.end(result.__raw);
      }
      return sendJSON(res, 200, result === undefined ? { ok: true } : result);
    }

    return serveStatic(req, res, pathname);
  } catch (err) {
    if (err instanceof ApiError) return sendJSON(res, err.status, { error: err.message });
    console.error('[שגיאה]', err);
    return sendJSON(res, 500, { error: `שגיאת שרת: ${err.message}` });
  }
});

server.listen(PORT, HOST, () => {
  const shown = HOST === '0.0.0.0' ? 'localhost' : HOST;
  console.log(`\n  מערכת גביית שכר דירה פועלת\n  → http://${shown}:${PORT}\n  נתונים: ${DATA_DIR}${PASSCODE ? '\n  מוגן בקוד כניסה' : ''}\n`);
});

module.exports = { server, db };
