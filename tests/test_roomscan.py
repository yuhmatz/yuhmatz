"""RoomScan tests - geometry, exporters, and the phone-facing server.

Runs against the REAL jarvis.py: the RoomScan block is extracted from it and
executed with the globals jarvis provides, so there is no second copy of the
code to drift. No third-party packages needed.

    python tests/test_roomscan.py
"""
import datetime
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
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
JARVIS = HERE.parent / "jarvis.py"
WORK = Path(tempfile.mkdtemp(prefix="roomscan_test_"))

START = "# --- v4.68: ROOMSCAN - phone camera -> 3D room model"
END = "# --- Google Places + Directions ---"

src = JARVIS.read_text(encoding="utf-8")
if START not in src or END not in src:
    print("could not find the RoomScan block in jarvis.py")
    sys.exit(2)
block = src[src.index(START):src.index(END)]

# roomscan.html has to exist for the server test to serve it
shutil.copy(HERE.parent / "roomscan.html", WORK / "roomscan.html")

ns = {
    "json": json, "math": math, "re": re, "struct": struct, "os": os, "sys": sys,
    "threading": threading, "datetime": datetime, "Path": Path, "time": time,
    "http": http, "urllib": urllib, "subprocess": subprocess, "ssl": ssl,
    "shutil": shutil, "socket": socket, "socketserver": socketserver,
    "webbrowser": webbrowser,
    "__file__": str(WORK / "jarvis.py"),
    "KNOWLEDGE_DIR": str(WORK / "Obsidian_Vault" / "Knowledge"),
}
exec(compile(block, "jarvis.py:roomscan", "exec"), ns)

FAIL = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAIL.append(label)


def close(a, b, tol=1e-6):
    return abs(a - b) <= tol


def inside(pt, poly):
    """ray casting - True when pt is strictly inside poly"""
    x, y = pt
    hit = False
    n = len(poly)
    for i in range(n):
        x0, y0 = poly[i]
        x1, y1 = poly[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            xc = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
            if x < xc:
                hit = not hit
    return hit


def sides(poly):
    n = len(poly)
    return [math.hypot(poly[(i + 1) % n][0] - poly[i][0],
                       poly[(i + 1) % n][1] - poly[i][1]) for i in range(n)]


# ============================================================ polygon helpers
print("polygon helpers")
rect = [[0, 0], [4, 0], [4, 3], [0, 3]]
check(close(ns["_rs_poly_area"](rect), 12.0), "rect area 12")
check(close(ns["_rs_poly_area"](list(reversed(rect))), -12.0), "cw area is negative")
check(ns["_rs_poly_area"](ns["_rs_ensure_ccw"](list(reversed(rect)))) > 0,
      "ensure_ccw flips winding")
check(close(ns["_rs_poly_perimeter"](rect), 14.0), "rect perimeter 14")
check(close(ns["_rs_wall_len"](rect, 1), 3.0), "wall length")

# ============================================================= triangulation
print("triangulation")


def tri_area_sum(poly, tris):
    tot = 0.0
    for (a, b, c) in tris:
        ax, ay = poly[a]
        bx, by = poly[b]
        cx, cy = poly[c]
        tot += ((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) / 2.0
    return tot


for name, poly in [
    ("rect", rect),
    ("cw rect", list(reversed(rect))),
    ("L-shape", [[0, 0], [5, 0], [5, 2], [2, 2], [2, 4], [0, 4]]),
    ("U-shape", [[0, 0], [6, 0], [6, 4], [4, 4], [4, 1.5], [2, 1.5], [2, 4], [0, 4]]),
    ("comb", [[0, 0], [7, 0], [7, 3], [6, 3], [6, 1], [5, 1], [5, 3], [4, 3],
              [4, 1], [3, 1], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3]]),
]:
    tris = ns["_rs_triangulate"](poly)
    want = abs(ns["_rs_poly_area"](poly))
    got = tri_area_sum(poly, tris)
    ccw = all(((poly[b][0] - poly[a][0]) * (poly[c][1] - poly[a][1])
               - (poly[b][1] - poly[a][1]) * (poly[c][0] - poly[a][0])) > 0
              for (a, b, c) in tris)
    check(len(tris) == len(poly) - 2, "%s: %d triangles (n-2)" % (name, len(tris)))
    check(close(got, want, 1e-9), "%s: area preserved (%.4f)" % (name, got))
    check(ccw, "%s: every triangle wound CCW" % name)

# ================================================================ wall cells
print("wall openings")
cells = ns["_rs_wall_cells"](4.0, 2.6, [])
check(len(cells) == 1, "a blank wall is one cell")

door = {"wall": 0, "type": "door", "u0": 1.0, "u1": 1.9, "z0": 0.0, "z1": 2.05}
win = {"wall": 0, "type": "window", "u0": 2.4, "u1": 3.6, "z0": 0.95, "z1": 2.1}
cells = ns["_rs_wall_cells"](4.0, 2.6, [door, win])
got = sum((u1 - u0) * (z1 - z0) for (u0, u1, z0, z1) in cells)
want = 4.0 * 2.6 - 0.9 * 2.05 - 1.2 * 1.15
check(close(got, want, 1e-9), "door + window removed exactly (%.4f)" % got)
check(not any(c[0] < o["u1"] - 1e-9 and c[1] > o["u0"] + 1e-9 and
              c[2] < o["z1"] - 1e-9 and c[3] > o["z0"] + 1e-9
              for c in cells for o in (door, win)),
      "no wall cell overlaps an opening")

o1 = {"u0": 1.0, "u1": 2.0, "z0": 0.0, "z1": 2.0}
o2 = {"u0": 1.5, "u1": 2.5, "z0": 0.5, "z1": 1.5}
cells = ns["_rs_wall_cells"](4.0, 2.6, [o1, o2])
got = sum((u1 - u0) * (z1 - z0) for (u0, u1, z0, z1) in cells)
check(close(got, 4.0 * 2.6 - (2.0 + 1.0 - 0.5), 1e-9),
      "overlapping openings subtract their union once (%.4f)" % got)

# ================================================================ validation
print("input validation")
for bad, why in [({"floor": [[0, 0], [1, 0]]}, "fewer than 3 corners"),
                 ({"floor": [[0, 0], [1, 0], ["x", 2]]}, "a non-numeric corner"),
                 ({"floor": "nope"}, "a non-list floor"),
                 ("not an object", "a non-object document")]:
    try:
        ns["_rs_validate"](bad)
        check(False, "rejects %s" % why)
    except ValueError:
        check(True, "rejects %s" % why)

v = ns["_rs_validate"]({"name": "בדיקה/../x", "floor": list(reversed(rect)),
                        "ceiling": 99, "openings": [dict(door)],
                        "objects": [{"label": "sofa", "x": 1, "y": 1,
                                     "w": 2, "d": 0.9, "h": 0.8, "yaw": 15}]})
check(ns["_rs_poly_area"](v["floor"]) > 0, "a clockwise floor is normalised to CCW")
check(close(v["ceiling"], ns["ROOMSCAN_MAX_CEILING"]), "an absurd ceiling is clamped")
check(v["openings"][0]["z1"] <= v["ceiling"] + 1e-9, "openings are clamped to the ceiling")
check("/" not in ns["_rs_slug"]("a/b") and "\\" not in ns["_rs_slug"]("a\\b"),
      "the folder slug strips path separators")
check(ns["_rs_slug"]("../..") not in ("", ".", ".."),
      "the folder slug cannot be a traversal (%r)" % ns["_rs_slug"]("../.."))
dup = ns["_rs_validate"]({"floor": [[0, 0], [4, 0], [4, 0], [4, 3], [0, 3], [0, 0]]})
check(len(dup["floor"]) == 4, "duplicate and closing points are dropped")

# ====================================================================== mesh
print("mesh")
scan = ns["_rs_validate"]({
    "name": "Living room", "ceiling": 2.62,
    "floor": [[0, 0], [4.2, 0], [4.2, 3.1], [2.0, 3.1], [2.0, 5.0], [0, 5.0]],
    "openings": [{"wall": 0, "type": "door", "u0": 1.0, "u1": 1.9, "z0": 0, "z1": 2.05},
                 {"wall": 1, "type": "window", "u0": 0.8, "u1": 2.2, "z0": 0.95, "z1": 2.1}],
    "objects": [{"label": "sofa", "x": 1.0, "y": 1.0, "w": 2.0, "d": 0.9,
                 "h": 0.8, "yaw": 30}],
    "stations": [{"x": 0, "y": 0, "h": 1.45}],
})
groups, stats = ns["_rs_build_mesh"](scan)
check(close(stats["area_m2"], 4.2 * 3.1 + 2.0 * 1.9), "L-shaped floor area")
check(close(stats["volume_m3"], stats["area_m2"] * 2.62), "volume = area x ceiling")
check(len(groups) == 4, "floor / ceiling / walls / objects groups")

bad_n = 0
for g in groups:
    for t in range(0, len(g.idx), 3):
        ia, ib, ic = g.idx[t], g.idx[t + 1], g.idx[t + 2]
        pa, pb, pc = (g.pos[3 * i:3 * i + 3] for i in (ia, ib, ic))
        e1 = [pb[k] - pa[k] for k in range(3)]
        e2 = [pc[k] - pa[k] for k in range(3)]
        cr = [e1[1] * e2[2] - e1[2] * e2[1],
              e1[2] * e2[0] - e1[0] * e2[2],
              e1[0] * e2[1] - e1[1] * e2[0]]
        ln = math.sqrt(sum(c * c for c in cr)) or 1.0
        stored = g.nrm[3 * ia:3 * ia + 3]
        if sum(cr[k] / ln * stored[k] for k in range(3)) < 0.99:
            bad_n += 1
check(bad_n == 0, "triangle winding agrees with its normal everywhere")

gw = [g for g in groups if g.name == "Walls"][0]
inward, probed = True, 0
for t in range(0, len(gw.idx), 3):
    ia, ib, ic = gw.idx[t], gw.idx[t + 1], gw.idx[t + 2]
    pa, pb, pc = (gw.pos[3 * i:3 * i + 3] for i in (ia, ib, ic))
    mid = [(pa[k] + pb[k] + pc[k]) / 3.0 for k in range(3)]
    nrm = gw.nrm[3 * ia:3 * ia + 3]
    probed += 1
    if not (inside((mid[0] + nrm[0] * .01, mid[1] + nrm[1] * .01), scan["floor"])
            and not inside((mid[0] - nrm[0] * .01, mid[1] - nrm[1] * .01), scan["floor"])):
        inward = False
check(inward and probed > 0, "wall normals point into the room (%d probed)" % probed)

gf = [g for g in groups if g.name == "Floor"][0]
gc = [g for g in groups if g.name == "Ceiling"][0]
check(all(gf.nrm[3 * i + 2] > 0.99 for i in range(len(gf.nrm) // 3)), "floor faces up")
check(all(gc.nrm[3 * i + 2] < -0.99 for i in range(len(gc.nrm) // 3)), "ceiling faces down")

wall_area = 0.0
for t in range(0, len(gw.idx), 3):
    ia, ib, ic = gw.idx[t], gw.idx[t + 1], gw.idx[t + 2]
    pa, pb, pc = (gw.pos[3 * i:3 * i + 3] for i in (ia, ib, ic))
    e1 = [pb[k] - pa[k] for k in range(3)]
    e2 = [pc[k] - pa[k] for k in range(3)]
    cr = [e1[1] * e2[2] - e1[2] * e2[1],
          e1[2] * e2[0] - e1[0] * e2[2],
          e1[0] * e2[1] - e1[1] * e2[0]]
    wall_area += math.sqrt(sum(c * c for c in cr)) / 2.0
check(close(wall_area, stats["perimeter_m"] * 2.62 - 0.9 * 2.05 - 1.4 * 1.15, 1e-6),
      "wall surface = perimeter x height minus the openings (%.4f m2)" % wall_area)

# ================================================================= exporters
print("exporters")
out = WORK / "out"
out.mkdir(parents=True, exist_ok=True)
ns["_rs_write_glb"](out / "room.glb", groups, "Living room")
blob = (out / "room.glb").read_bytes()
magic, ver, total = struct.unpack("<III", blob[:12])
check(magic == 0x46546C67 and ver == 2, "glb magic and version")
check(total == len(blob), "glb header length matches the file")
jlen, jtype = struct.unpack("<II", blob[12:20])
check(jtype == 0x4E4F534A, "JSON chunk type")
gj = json.loads(blob[20:20 + jlen].decode("utf-8"))
blen, btype = struct.unpack("<II", blob[20 + jlen:28 + jlen])
check(btype == 0x004E4942, "BIN chunk type")
binb = blob[28 + jlen:28 + jlen + blen]
check(len(binb) == blen, "BIN chunk length")
check(len(blob) % 4 == 0 and jlen % 4 == 0 and blen % 4 == 0, "chunks are 4-byte aligned")
check(gj["buffers"][0]["byteLength"] <= blen, "declared buffer fits the BIN chunk")

ok_acc = True
for a in gj["accessors"]:
    bv = gj["bufferViews"][a["bufferView"]]
    size = {5126: 4, 5125: 4}[a["componentType"]] * {"VEC3": 3, "SCALAR": 1}[a["type"]]
    if a["count"] * size != bv["byteLength"] or bv["byteOffset"] % 4:
        ok_acc = False
    if bv["byteOffset"] + bv["byteLength"] > blen:
        ok_acc = False
check(ok_acc, "every accessor matches its bufferView and stays in range")

for prim in gj["meshes"][0]["primitives"]:
    n_pos = gj["accessors"][prim["attributes"]["POSITION"]]["count"]
    idx_acc = gj["accessors"][prim["indices"]]
    off = gj["bufferViews"][idx_acc["bufferView"]]["byteOffset"]
    idxs = struct.unpack_from("<%dI" % idx_acc["count"], binb, off)
    check(max(idxs) < n_pos, "primitive %d indices stay inside POSITION"
          % prim["material"])
    check("min" in gj["accessors"][prim["attributes"]["POSITION"]],
          "primitive %d POSITION has min/max" % prim["material"])
    check(prim["material"] < len(gj["materials"]), "primitive %d material exists"
          % prim["material"])
ymax = max(a["max"][1] for a in gj["accessors"] if "max" in a)
ymin = min(a["min"][1] for a in gj["accessors"] if "min" in a)
check(close(ymax, 2.62, 1e-4), "Y-up conversion: ceiling at +Y %.4f" % ymax)
check(close(ymin, 0.0, 1e-4), "Y-up conversion: floor at Y=0")

mtl = ns["_rs_write_obj"](out / "room.obj", groups, "Living room")
objtxt = (out / "room.obj").read_text(encoding="utf-8")
nv = sum(1 for line in objtxt.splitlines() if line.startswith("v "))
nvn = sum(1 for line in objtxt.splitlines() if line.startswith("vn "))
nf = sum(1 for line in objtxt.splitlines() if line.startswith("f "))
check(nv == nvn, "obj vertex and normal counts match")
check(nf == stats["triangles"], "obj face count == triangle count (%d)" % nf)
check(all(1 <= int(tok.split("//")[0]) <= nv
          for line in objtxt.splitlines() if line.startswith("f ")
          for tok in line.split()[1:]),
      "obj face indices are in range")
check(mtl.exists() and "newmtl Floor" in mtl.read_text(encoding="utf-8"), "mtl written")

ns["_rs_write_plan_svg"](out / "plan.svg", scan, stats)
try:
    ET.parse(out / "plan.svg")
    check(True, "plan.svg is well-formed XML")
except Exception as e:
    check(False, "plan.svg XML: %r" % e)

# ================================================================ save + load
print("save / load")
res = ns["_rs_save"]({"name": "סלון", "ceiling": 2.62,
                      "floor": [[0, 0], [4.2, 0], [4.2, 3.1], [0, 3.1]],
                      "openings": [dict(door)], "meta": {"mode": "sensor"}})
folder = Path(res["folder"])
for f in ("scan.json", "room.obj", "room.mtl", "room.glb", "plan.svg"):
    check((folder / f).exists(), "saved %s" % f)
check(close(res["stats"]["area_m2"], 13.02, 1e-9), "saved area")
loaded = ns["_rs_load"](res["id"])
check(loaded is not None and loaded["name"] == "סלון", "reload by id, hebrew name intact")
check(ns["_rs_load"]("../../etc") is None, "path traversal refused on load")
check(ns["_rs_load"]("nope") is None, "unknown id refused")
notes = list((WORK / "Obsidian_Vault" / "Knowledge" / "Rooms").glob("*.md"))
check(len(notes) == 1 and "13.02" in notes[0].read_text(encoding="utf-8"),
      "obsidian note written with the area")

# ==================================================================== server
print("server (TLS, token, hostile input)")
PORT = int(os.environ.get("ROOMSCAN_TEST_PORT", "7793"))
info = ns["_start_roomscan_server"](PORT)
check(info.get("https") is True,
      "TLS listener up on :%d (%s)" % (PORT, info.get("error") or "no error"))
tok = ns["_rs_token"]()
base = "https://127.0.0.1:%d" % PORT
sslctx = ssl.create_default_context()
sslctx.check_hostname = False
sslctx.verify_mode = ssl.CERT_NONE          # self-signed on purpose


def call(path, data=None, ctype="application/json", key=None, raw=False):
    k = tok if key is None else key
    url = base + path + ("&" if "?" in path else "?") + "k=" + urllib.parse.quote(k)
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data is not None else "GET")
    if data is not None:
        req.add_header("Content-Type", ctype)
    try:
        with urllib.request.urlopen(req, timeout=10, context=sslctx) as r:
            body = r.read()
            return r.status, (body if raw else json.loads(body.decode("utf-8")))
    except urllib.error.HTTPError as e:
        body = e.read()
        try:
            return e.code, json.loads(body.decode("utf-8"))
        except Exception:
            return e.code, body


code, body = call("/api/ping")
check(code == 200 and body.get("ok") is True, "ping with the session key -> 200")
check(call("/api/ping", key="wrong")[0] == 403, "wrong key -> 403")
check(call("/api/ping", key="")[0] == 403, "no key -> 403")
code, body = call("/", raw=True)
check(code == 200 and b"RoomScan" in body, "the scanner page is served with the key")
check(call("/", key="nope", raw=True)[0] == 403, "the scanner page needs the key")
check(call("/../jarvis.py", raw=True)[0] in (403, 404), "no arbitrary file serving")

doc = {"name": "סלון", "ceiling": 2.62,
       "floor": [[0, 0], [4.2, 0], [4.2, 3.1], [2.0, 3.1], [2.0, 5.0], [0, 5.0]],
       "openings": [{"wall": 0, "type": "door", "u0": 1.0, "u1": 1.9,
                     "z0": 0, "z1": 2.05}],
       "stations": [{"x": 0.9, "y": 1.1, "h": 1.45, "rms": 0.0}],
       "meta": {"mode": "sensor", "app": "test"}}
code, body = call("/api/scan", json.dumps(doc).encode("utf-8"))
check(code == 200 and "id" in body, "upload a scan -> 200")
check(close(body["stats"]["area_m2"], 4.2 * 3.1 + 2.0 * 1.9, 1e-9), "server-side area")
check((Path(body["folder"]) / "room.glb").stat().st_size > 500, "glb written by the server")
check(call("/api/scan", json.dumps(doc).encode("utf-8"), key="bad")[0] == 403,
      "upload without the key -> 403")
check(call("/api/scan", b"{not json")[0] == 400, "malformed json -> 400")
code, body = call("/api/scan", json.dumps({"floor": [[0, 0]]}).encode("utf-8"))
check(code == 400 and "3 corners" in str(body.get("error", "")),
      "a bad document -> 400 with a readable reason")

for bad, label in [
    ({"floor": [[0, 0], [4, 0], [4, 3]], "ceiling": float("inf")}, "infinite ceiling"),
    ({"floor": [[1e9, 0], [4, 0], [4, 3]]}, "absurd coordinate"),
    ({"floor": [[0, 0], [4, 0], [4, 3]],
      "openings": [{"wall": 99, "u0": 0, "u1": 1}]}, "opening on a missing wall"),
    ({"floor": [[0, 0], [4, 0], [4, 3]], "objects": [{"x": "a", "y": 1}]}, "junk object"),
    ({"floor": [[0, 0], [4, 0], [4, 3]], "name": "../../../etc/passwd"},
     "traversal in the room name"),
]:
    code, body = call("/api/scan", json.dumps(bad).encode("utf-8"))
    check(code in (200, 400), "%s -> no 500 (got %s)" % (label, code))
    if code == 200:
        p = Path(body["folder"]).resolve()
        check(str(p).startswith(str(ns["_rs_root"]().resolve())),
              "  ...and it stayed inside RoomScans/")

try:
    code, _ = call("/api/scan", b"x" * (ns["ROOMSCAN_MAX_JSON"] + 10))
    check(code == 413, "oversized body -> 413")
except Exception as e:
    check(True, "oversized body refused mid-upload (%s)" % type(e).__name__)
code, body = call("/api/ping")
check(code == 200 and body.get("ok"), "the server is still healthy afterwards")

jpg = b"\xff\xd8\xff\xe0" + b"\x00" * 900 + b"\xff\xd9"
code, body = call("/api/photo?name=" + urllib.parse.quote("סלון"), jpg, "image/jpeg")
check(code == 200 and body.get("ok"), "photo upload -> 200")
check(len(list(ns["_rs_root"]().rglob("photos/*.jpg"))) == 1,
      "the photo landed in its scan folder")

code, body = call("/api/scans")
check(code == 200 and len(body["scans"]) >= 2, "the scan index lists what was saved")

# =========================================================== voice behaviour
print("voice")
check("מ" in ns["roomscan_status"]("he"), "hebrew status: %s"
      % ns["roomscan_status"]("he")[:60])
check("m2" in ns["roomscan_status"]("en"), "english status: %s"
      % ns["roomscan_status"]("en")[:60])

for msg, want in [
    ("סרוק את החדר", "open"), ("תסרוק חדר", "open"),
    ("scan the room", "open"), ("open roomscan", "open"),
    ("פתח את סורק החדרים", "open"), ("open the room scanner", "open"),
    ("build a 3d model of the room", "open"),
    ("מה הסריקה האחרונה של סריקת חדר", "status"),
    ("what is the status of the room scan", "status"),
    ("what is a room", None), ("מה זה חדר", None),
    ("open worldview", None), ("תפתח את הגלובוס", None),
    ("play some music", None), ("", None), (None, None),
]:
    got = ns["_roomscan_intercept"](msg)
    check(got == want, "intercept %-42r -> %r" % (msg, got))

print()
shutil.rmtree(WORK, ignore_errors=True)
if FAIL:
    print("%d FAILURES:" % len(FAIL))
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("all RoomScan tests passed")
