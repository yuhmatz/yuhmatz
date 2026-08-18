# RoomScan — הטלפון כסורק תלת־מימד לחדרים

הרחבה ל‑JARVIS (v4.68): אומרים **"סרוק את החדר"**, נפתח מסך עם קוד QR, סורקים
אותו עם הטלפון, מסמנים את פינות החדר דרך המצלמה — ומקבלים מודל תלת־מימד,
תוכנית קומה עם מידות, ושטח/היקף/גובה תקרה. הכול נשמר על המחשב, בלי ענן.

## התחלה מהירה

1. אומרים ל‑JARVIS: **"סרוק את החדר"** / *"scan the room"* (או "פתח את סורק החדרים").
2. על המסך נפתחת קונסולת RoomScan עם קוד QR. סורקים אותו עם מצלמת הטלפון.
3. בפעם הראשונה הדפדפן בטלפון יתריע שהחיבור **לא מאובטח** — זה תעודת ה‑TLS
   שג'רוויס ייצר בעצמו לרשת הביתית. לוחצים **"מתקדם" → "המשך"** פעם אחת.
   *(בלי HTTPS הדפדפן פשוט לא ייתן גישה למצלמה ולחיישני התנועה — ולכן היא קיימת.)*
4. מזינים שם לחדר, בוחרים שיטה, ומתחילים.
5. עומדים בערך במרכז החדר, מכוונים את הכוונת **לפינה שבין הקיר לרצפה**, ולוחצים
   "סמן פינה". עוברים פינה־פינה סביב החדר.
6. "גובה תקרה" — מכוונים לפינה שבין הקיר לתקרה מעל הפינה האחרונה.
7. "סגור חדר" → מסך סיכום → **"שלח ל‑JARVIS"**. החדר מופיע מיד בקונסולה במחשב.

**לדיוק טוב יותר:** השתמשו ב"כיול לפי דלת" לפני שמתחילים (מכוונים לתחתית משקוף
הדלת ואז לחלקו העליון). ניחוש של גובה היד הוא מקור הטעות הגדול ביותר.

---

## What it is

`roomscan.html` (phone) + `roomview.html` (PC console) + a RoomScan module inside
`jarvis.py`. The phone measures the room; the PC turns the measurements into real
geometry and exports it.

### Three capture methods, best first

| Method | How | Accuracy | Needs |
|---|---|---|---|
| **AR** | WebXR `immersive-ar` hit-test — tap the reticle on each floor corner | ~2 cm | Android + Chrome with ARCore |
| **Sensors** | Aim the crosshair at each wall/floor corner and tap. The ray from the known phone height meets the floor plane, so every tap is a polar measurement | 5–20 cm | any phone with orientation sensors |
| **Manual** | Type width × depth × height | exact, if you measured it | nothing |

The page picks AR when the phone supports it and falls back on its own.

### Measured accuracy (sensor mode)

From `tests/test_roomscan_math.mjs`, 200 simulated scans of a 4.2 × 3.1 m room
with the phone at 1.45 m — `σ` is the per-axis orientation noise:

| σ | median wall error | after "square up" | median area error |
|---|---|---|---|
| 0.5° | 10.0 cm | **5.4 cm** | 1.9 % |
| 1.0° | 19.0 cm | **9.7 cm** | 3.2 % |
| 1.5° | 29.1 cm | **15.8 cm** | 5.3 % |
| 2.5° | 48.9 cm | 30.2 cm | 8.5 % |

Two things follow from the error model, `σ·(D² + h²)/h`:

* **Error grows with the square of distance.** Doubling the distance to a corner
  roughly triples the error. Stand near the middle of the room; the live readout
  shows the expected error per shot.
* **Squaring up roughly halves the wall error** — but it fixes *angles*, not
  *scale*, so the area error barely moves. Only a better height calibration or
  AR mode improves that.

Every shot averages ~0.4 s of sensor samples and is rejected outright if the
phone was still moving (>2.6° of wander).

### Rooms bigger than one viewpoint

If you can't see every corner from one spot: **Menu → New station**. Walk to a
new spot, re-shoot two corners you already marked, and a 2D Procrustes fit
stitches the two halves together. A side effect is that **compass accuracy never
matters** — only relative yaw within a single station is used, and the fit
absorbs the offset between stations. The fit reports its RMS; above 60 cm it is
refused rather than silently producing a bent room.

### Openings

"Door / window" takes three taps: bottom-left, bottom-right, then the top edge.
The opening is assigned to the nearest wall and **cut out of the wall geometry**
— a door is a real hole in the mesh, not a painted rectangle.

## What you get

Every scan writes `RoomScans/<room>_<timestamp>/`:

| File | What |
|---|---|
| `room.glb` | binary glTF 2.0 — opens in Blender, Windows 3D Viewer, three.js |
| `room.obj` + `room.mtl` | Wavefront, for anything that won't read glTF |
| `plan.svg` | dimensioned floor plan: wall lengths, doors, windows, stations, north |
| `scan.json` | the raw measurements, so a scan can be rebuilt or re-exported |
| `photos/` | optional reference photos taken from the phone |

Plus a note in `Obsidian_Vault/Knowledge/Rooms/<room>.md` with the dimension
table, so rooms are searchable later.

Models are Y-up, metres, with the floor at Y = 0. Walls carry inward normals and
double-sided materials, so the room reads correctly from inside and outside.

## How it is wired

```
phone ──HTTPS :7779──► RoomScan TLS listener   (roomscan.html, /api/scan, /api/photo)
                        │  self-signed cert, per-session token in the QR link
                        ▼
                   RoomScans/<room>_<stamp>/   (glb, obj, svg, json)
                        ▲
PC console ──HTTP :7778─┘  /roomscan_info, /rooms, /room   (loopback only)
           ──HTTP :7777──► roomview.html + the exported files
```

| Port | Bind | Purpose |
|---|---|---|
| 7777 | 0.0.0.0 | existing static server (WorldView, Achilles, RoomScan console, exports) |
| 7778 | 0.0.0.0 | existing API proxy; the three RoomScan routes are **loopback-only** |
| 7779 | 0.0.0.0 | **new** — the phone-facing TLS scanner |

Windows Firewall will ask to allow Python on the private network the first time.
Phone and PC must be on the same network (or the same Tailscale tailnet).

### Security

* The scanner and every API call require a **per-session token**, generated at
  start-up and carried in the QR link. Without it: `403`.
* `/roomscan_info` hands out that token, so it is **loopback-only** — as are
  `/rooms` and `/room`.
* Upload bodies are capped (3 MB JSON, 6 MB per photo) and rejected on the
  `Content-Length` header, before a byte is read.
* Every incoming document is validated and clamped: coordinates, ceiling height,
  corner count, opening geometry. Room names are slugged, and scan folders are
  verified to resolve inside `RoomScans/`.
* The certificate and its private key live in `.roomscan_cert/` — **gitignored**.
  So is `RoomScans/`.

### The certificate

Browsers only expose `getUserMedia` and the motion sensors in a *secure context*,
and `http://192.168.x.x` is not one. JARVIS therefore generates a self-signed
certificate for its own LAN address (via `openssl` if it is on PATH, otherwise
via the `cryptography` package **in a separate process** — a half-installed
`cryptography` panics in a way that a normal `except` cannot catch). If neither is
available the console says so and only manual entry will work on the phone.

## Voice

| Say | Result |
|---|---|
| "סרוק את החדר" / "scan the room" / "open roomscan" | opens the console + scanner |
| "פתח את סורק החדרים" / "open the room scanner" | same |
| "מה הסריקה האחרונה" / "room scan status" | reports area, ceiling, corner count |

Both are also exposed to the brain as the `open_roomscan` and `roomscan_status`
tools, so a phrasing the intercepts miss still reaches them.

## Tests

No third-party packages needed. They run against `jarvis.py` and
`roomscan.html` directly — there is no second copy of the code to drift.

```bash
python tests/test_roomscan.py           # geometry, exporters, TLS server, hostile input
node   tests/test_roomscan_math.mjs     # phone-side maths + simulated scans
python tests/test_roomscan_browser.py   # real page, real TLS, headless Chromium, real files
```

The browser test skips cleanly (exit 0) when no Chromium is installed.

## Limits, honestly

* Sensor mode assumes **one floor plane** and a **constant phone height**. Split
  levels and steps are not modelled.
* Walls are zero-thickness. This is a room's *inner* shell, not a construction model.
* Furniture boxes are supported by the format and rendered by the console, but the
  phone UI does not capture them yet — the field is there for the next pass.
* The QR code is drawn by a CDN library. With no internet the console prints the
  address in large type instead; everything else works offline.
* AR mode needs Android + Chrome with ARCore. iOS Safari has no WebXR, so an
  iPhone always uses sensor mode — including iPhones with LiDAR, which no browser
  can reach.

### One pre-existing note, not introduced here

The static server on **:7777** (started at boot since v4.67 and used by
WorldView, Achilles and now this console) serves the whole JARVIS folder to
`0.0.0.0` — including `.env`. That predates RoomScan and is unchanged by it, but
anyone on the LAN can read it. Worth restricting to an allow-list of files.
