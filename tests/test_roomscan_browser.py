"""RoomScan end-to-end, in a real browser.

Serves the real roomscan.html from the real TLS listener, drives it with a
headless Chromium (synthesising deviceorientation events so the capture path
runs for real), posts the result to the real handler, and checks what landed on
disk. Skips with exit code 0 when no Chromium is installed.

    python tests/test_roomscan_browser.py
"""
import datetime
import html
import http.server
import json
import math
import os
import re
import shutil
import socket
import socketserver
import ssl
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
WORK = Path(tempfile.mkdtemp(prefix="roomscan_e2e_"))
PORT = int(os.environ.get("ROOMSCAN_TEST_PORT", "7799"))

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    shutil.which("google-chrome") or "",
]
CHROME = next((c for c in CHROME_CANDIDATES if c and Path(c).exists()), None)
if not CHROME:
    hits = sorted(Path("/opt/pw-browsers").glob("chromium-*/chrome-linux/chrome")) \
        if Path("/opt/pw-browsers").exists() else []
    CHROME = str(hits[-1]) if hits else None
if not CHROME:
    print("no chromium found - skipping the browser test")
    sys.exit(0)

# The driver runs inside the page: it fakes a phone standing at one spot and
# aiming at each corner of an L-shaped room, then uploads through the real API.
DRIVER = r"""
<script>
(function () {
  const log = [];
  const ok = (c, l) => log.push((c ? "ok   " : "FAIL ") + l);
  const R2D = 180 / Math.PI;
  function dump() {
    const d = document.createElement("pre");
    d.id = "AUTOTEST"; d.textContent = log.join("\n");
    document.body.appendChild(d);
  }
  function fire(a, b) {
    for (let i = 0; i < 6; i++)
      window.dispatchEvent(new DeviceOrientationEvent("deviceorientation",
        { alpha: a, beta: b, gamma: 0 }));
  }
  // A settled aim. Real elapsed time drains the sample ring buffer between
  // corners; here everything happens in one tick, so clear it explicitly -
  // otherwise the (correct) "phone is still moving" guard rejects every shot.
  function aimAt(px, py, st, ph, comp) {
    oriBuf.length = 0;
    const dx = px - st[0], dy = py - st[1], n = Math.hypot(dx, dy, ph);
    const u = [dx / n, dy / n, -ph / n];
    fire(Math.atan2(-u[0], u[1]) * R2D + comp,
         Math.acos(Math.max(-1, Math.min(1, -u[2]))) * R2D);
  }
  setTimeout(async function () {
    try {
      ok(window.isSecureContext === true,
         "the page is a secure context (camera + sensors allowed)");
      ok(TOKEN.length > 0, "the session key arrived in the URL");
      ok(typeof RS.floorHit === "function", "the geometry module is live");

      window.addEventListener("deviceorientation", onOri, true);
      S.mode = "sensor"; S.phoneH = 1.45; S.name = "E2E Room";
      S.corners = []; S.stationLocal = []; S.fit = null;
      startScanning();

      const ROOM = [[0,0],[4.2,0],[4.2,3.1],[2.0,3.1],[2.0,5.0],[0,5.0]];
      ROOM.forEach(function (P) { aimAt(P[0], P[1], [1.2, 1.4], 1.45, 33); markCorner(); });
      ok(S.corners.length === 6, "6 corners captured through the event path");
      const err = Math.max.apply(null, ROOM.map(function (P, i) {
        // the model frame is rotated by the (unknown) compass heading, so
        // compare wall lengths rather than absolute positions
        const a = ROOM[i], b = ROOM[(i + 1) % 6];
        const c = S.corners[i], d = S.corners[(i + 1) % 6];
        return Math.abs(Math.hypot(b[0]-a[0], b[1]-a[1]) - Math.hypot(d[0]-c[0], d[1]-c[1]));
      }));
      ok(err < 1e-6, "every wall length recovered (max err " + err.toExponential(2) + " m)");

      S.ceiling = 2.62; S.ceilingMeasured = true;
      S.openings = [{ wall: 0, type: "door", u0: 1.0, u1: 1.9, z0: 0, z1: 2.05 }];
      finishRoom();
      ok(/16\.82/.test(document.getElementById("sheet").textContent),
         "the review screen shows 16.82 m2");

      const r = await fetch(location.origin + "/api/scan?k=" + encodeURIComponent(TOKEN), {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(buildDoc())
      });
      const j = await r.json();
      ok(r.ok && !!j.id, "POST /api/scan accepted: " + (j.id || j.error));
      ok(j.stats && Math.abs(j.stats.area_m2 - 16.82) < 1e-3,
         "the server computed the same area: " + (j.stats ? j.stats.area_m2.toFixed(6) : "-"));

      const bad = await fetch(location.origin + "/api/scan?k=nope", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      ok(bad.status === 403, "an unkeyed POST from the page is refused (" + bad.status + ")");
      dump();
    } catch (e) {
      log.push("FAIL threw: " + e.message);
      dump();
    }
  }, 300);
})();
</script>
"""

page = (REPO / "roomscan.html").read_text(encoding="utf-8")
(WORK / "roomscan.html").write_text(page.replace("</body>", DRIVER + "</body>"),
                                    encoding="utf-8")

src = (REPO / "jarvis.py").read_text(encoding="utf-8")
START = "# --- v4.68: ROOMSCAN - phone camera -> 3D room model"
END = "# --- Google Places + Directions ---"
if START not in src or END not in src:
    print("could not find the RoomScan block in jarvis.py")
    sys.exit(2)
ns = {"json": json, "math": math, "re": re, "struct": struct, "os": os, "sys": sys,
      "threading": threading, "datetime": datetime, "Path": Path, "time": time,
      "http": http, "urllib": urllib, "socketserver": socketserver,
      "subprocess": subprocess, "ssl": ssl, "shutil": shutil, "socket": socket,
      "webbrowser": webbrowser,
      "__file__": str(WORK / "jarvis.py"), "KNOWLEDGE_DIR": str(WORK / "K")}
exec(compile(src[src.index(START):src.index(END)], "jarvis.py:roomscan", "exec"), ns)

FAIL = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAIL.append(label)


info = ns["_start_roomscan_server"](PORT)
check(info.get("https") is True,
      "TLS listener up on :%d (%s)" % (PORT, info.get("error") or "no error"))
if not info.get("https"):
    print("cannot run the browser leg without TLS")
    shutil.rmtree(WORK, ignore_errors=True)
    sys.exit(1)

url = "https://127.0.0.1:%d/?k=%s" % (PORT, ns["_rs_token"]())
out = subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                      "--disable-dev-shm-usage", "--use-gl=swiftshader",
                      "--ignore-certificate-errors", "--virtual-time-budget=12000",
                      "--window-size=430,900", "--dump-dom", url],
                     capture_output=True, timeout=180)
dom = out.stdout.decode("utf-8", "replace")
m = re.search(r'<pre id="AUTOTEST">(.*?)</pre>', dom, re.S)
if not m:
    check(False, "the in-page driver never ran (the page threw during load)")
    print(dom[:1500])
else:
    for line in html.unescape(m.group(1)).splitlines():
        print("  " + line)
        if line.startswith("FAIL"):
            FAIL.append(line)

print("on disk")
dirs = ns["_rs_scan_dirs"]()
check(len(dirs) == 1, "exactly one scan folder written (%d)" % len(dirs))
if dirs:
    d = dirs[0]
    for f in ("scan.json", "room.obj", "room.mtl", "room.glb", "plan.svg"):
        check((d / f).exists(), "%s written by the server" % f)
    s = json.loads((d / "scan.json").read_text(encoding="utf-8"))
    check(s["name"] == "E2E Room", "the room name round-tripped")
    check(abs(s["stats"]["area_m2"] - 16.82) < 1e-3,
          "area on disk: %.6f m2 (corners are quantised to 0.1 mm on upload)"
          % s["stats"]["area_m2"])
    check(len(s["openings"]) == 1 and s["openings"][0]["type"] == "door",
          "the door survived the round trip")
    blob = (d / "room.glb").read_bytes()
    check(struct.unpack("<I", blob[:4])[0] == 0x46546C67, "room.glb is a glTF binary")
    check(struct.unpack("<I", blob[8:12])[0] == len(blob), "room.glb length header")
    notes = list((WORK / "K" / "Rooms").glob("*.md"))
    check(len(notes) == 1 and "16.82" in notes[0].read_text(encoding="utf-8"),
          "the obsidian note was written")

shutil.rmtree(WORK, ignore_errors=True)
print()
if FAIL:
    print("%d FAILURES:" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("browser end-to-end passed")
