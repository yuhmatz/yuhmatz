/* Node harness for the RoomScan phone-side geometry.
   Run: node test_math.mjs           (or: node tests/test_roomscan_math.mjs) */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

/* The maths lives inside roomscan.html in a tagged <script> block so the page
   stays a single deployable file; pull it out and evaluate it. */
function loadRS() {
  for (const cand of ["../roomscan.html", "roomscan.html"]) {
    let txt;
    try { txt = readFileSync(join(here, cand), "utf8"); } catch { continue; }
    if (cand.endsWith(".html")) {
      const m = txt.match(/<script id="rs-math">([\s\S]*?)<\/script>/);
      if (!m) throw new Error("roomscan.html has no <script id=\"rs-math\"> block");
      txt = m[1];
    }
    const fn = new Function(txt + "\nreturn RS;");
    return fn();
  }
  throw new Error("could not find the RoomScan maths source");
}
const RS = loadRS();

const D2R = Math.PI / 180, R2D = 180 / Math.PI;
let fails = [];
function check(cond, label) {
  console.log((cond ? "  ok   " : "  FAIL ") + label);
  if (!cond) fails.push(label);
}
const close = (a, b, t = 1e-9) => Math.abs(a - b) <= t;

/* ---- independent rotation implementation (matrix product, not the closed
   form the page uses) so the closed form is actually being verified -------- */
function mul(A, B) {
  const C = new Array(9).fill(0);
  for (let r = 0; r < 3; r++)
    for (let c = 0; c < 3; c++)
      for (let k = 0; k < 3; k++) C[r * 3 + c] += A[r * 3 + k] * B[k * 3 + c];
  return C;
}
const Rz = (t) => [Math.cos(t), -Math.sin(t), 0, Math.sin(t), Math.cos(t), 0, 0, 0, 1];
const Rx = (t) => [1, 0, 0, 0, Math.cos(t), -Math.sin(t), 0, Math.sin(t), Math.cos(t)];
const Ry = (t) => [Math.cos(t), 0, Math.sin(t), 0, 1, 0, -Math.sin(t), 0, Math.cos(t)];
const refRot = (a, b, g) => mul(mul(Rz(a * D2R), Rx(b * D2R)), Ry(g * D2R));

/* deterministic PRNG so a failure is reproducible */
let seed = 20260818;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
function gauss(sigma) {
  const u = Math.max(1e-9, rnd()), v = rnd();
  return sigma * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

console.log("rotation matrix");
let worst = 0;
for (let i = 0; i < 500; i++) {
  const a = rnd() * 720 - 360, b = rnd() * 360 - 180, g = rnd() * 180 - 90;
  const A = RS.rotMatrix(a, b, g), B = refRot(a, b, g);
  for (let k = 0; k < 9; k++) worst = Math.max(worst, Math.abs(A[k] - B[k]));
}
check(worst < 1e-12, `closed form == Rz*Rx*Ry over 500 random poses (max diff ${worst.toExponential(2)})`);

let orth = 0;
for (let i = 0; i < 200; i++) {
  const R = RS.rotMatrix(rnd() * 360, rnd() * 360 - 180, rnd() * 180 - 90);
  for (let r = 0; r < 3; r++)
    for (let c = 0; c < 3; c++) {
      let d = 0;
      for (let k = 0; k < 3; k++) d += R[r * 3 + k] * R[c * 3 + k];
      orth = Math.max(orth, Math.abs(d - (r === c ? 1 : 0)));
    }
}
check(orth < 1e-12, "matrix is orthonormal");

console.log("look direction");
let d = RS.dirFromOrientation(0, 90, 0);
check(close(d[0], 0, 1e-12) && close(d[1], 1, 1e-12) && close(d[2], 0, 1e-12),
      "beta=90 (upright, facing north) -> +Y");
d = RS.dirFromOrientation(0, 0, 0);
check(close(d[2], -1, 1e-12), "beta=0 (flat on a table) -> straight down");
d = RS.dirFromOrientation(90, 90, 0);
check(close(d[0], -1, 1e-12) && close(d[1], 0, 1e-9),
      "alpha=90 rotates the view to the west");

console.log("floor intersection");
const h = 1.5;
let hit = RS.floorHit(RS.dirFromOrientation(0, 60, 0), h);
check(hit && close(hit.dist, h / Math.tan(30 * D2R), 1e-9),
      `depression 30 deg -> ${hit ? hit.dist.toFixed(4) : "null"} m (expect 2.5981)`);
check(hit && close(hit.x, 0, 1e-9) && close(hit.y, hit.dist, 1e-9), "and it lies due north");
check(RS.floorHit(RS.dirFromOrientation(0, 91, 0), h) === null, "aiming above the horizon rejected");
check(RS.floorHit(RS.dirFromOrientation(0, 88, 0), h) === null, "grazing shot rejected");

let mism = 0;
for (let i = 0; i < 400; i++) {
  const a = rnd() * 360, b = rnd() * 80 + 5, g = rnd() * 60 - 30;
  const R = refRot(a, b, g);
  const dd = [-R[2], -R[5], -R[8]];
  if (dd[2] >= -0.08) continue;
  const t = h / -dd[2];
  const want = [t * dd[0], t * dd[1]];
  const got = RS.floorHit(RS.dirFromOrientation(a, b, g), h);
  if (!got || Math.hypot(got.x - want[0], got.y - want[1]) > 1e-9) mism++;
}
check(mism === 0, `floorHit matches the reference ray for every pose incl. roll (${mism} bad)`);

console.log("height measurement");
// ceiling corner 3.2 m away, room 2.62 high, phone at 1.45
{
  const H = 2.62, ph = 1.45, r = 3.2;
  const dz = H - ph;
  const dir = [0, r / Math.hypot(r, dz), dz / Math.hypot(r, dz)];
  check(close(RS.heightAt(dir, r, ph), H, 1e-9), "heightAt recovers the ceiling height");
}
// door calibration: door 2.00 m tall, 2.6 m away, phone actually at 1.38
{
  const doorH = 2.0, D = 2.6, ph = 1.38;
  const nb = Math.hypot(D, ph), nt = Math.hypot(D, doorH - ph);
  const dB = [0, D / nb, -ph / nb];
  const dT = [0, D / nt, (doorH - ph) / nt];
  const got = RS.heightFromReference(dB, dT, doorH);
  check(got !== null && close(got, ph, 1e-9), `door calibration -> ${got?.toFixed(4)} (expect 1.3800)`);
  check(RS.heightFromReference(dT, dT, doorH) === null, "calibration rejects two upward shots");
}

console.log("averaging / steadiness");
{
  const base = RS.dirFromOrientation(10, 65, 0);
  const samples = [];
  for (let i = 0; i < 20; i++) samples.push(RS.dirFromOrientation(10 + gauss(0.4), 65 + gauss(0.4), 0));
  const avg = RS.averageDir(samples);
  const ang = Math.acos(Math.max(-1, Math.min(1, avg.dir.reduce((s, v, k) => s + v * base[k], 0)))) * R2D;
  check(ang < 0.35, `20 jittered samples average to within ${ang.toFixed(3)} deg of truth`);
  check(avg.spreadDeg > 0.2 && avg.spreadDeg < 6, `spread reported (${avg.spreadDeg.toFixed(2)} deg)`);
  check(RS.averageDir([]) === null, "empty sample set -> null");
}

console.log("error model");
{
  const ph = 1.45, sig = 1.5;
  const e2 = RS.shotError(2, ph, sig), e4 = RS.shotError(4, ph, sig);
  const want = (16 + ph * ph) / (4 + ph * ph);           // closed form d(D)/d(angle)
  check(close(e4 / e2, want, 1e-9) && e4 / e2 > 2,
        `error grows as (D^2+h^2)/h: ${e2.toFixed(3)} -> ${e4.toFixed(3)} m (ratio ${(e4 / e2).toFixed(2)}x for 2x the distance)`);
  check(close(e2, sig * Math.PI / 180 * (4 + ph * ph) / ph, 1e-12), "shotError matches its closed form");
}

/* ---- end-to-end room simulation --------------------------------------- */
function simulate(room, station, ph, sigmaDeg, compassOffset) {
  // returns the floor polygon a phone would reconstruct from `station`
  return room.map((P) => {
    const dx = P[0] - station[0], dy = P[1] - station[1];
    const dir = [dx, dy, -ph];
    const n = Math.hypot(dir[0], dir[1], dir[2]);
    const u = [dir[0] / n, dir[1] / n, dir[2] / n];
    let beta = Math.acos(Math.max(-1, Math.min(1, -u[2]))) * R2D;
    let alpha = Math.atan2(-u[0], u[1]) * R2D + compassOffset;
    if (sigmaDeg) { alpha += gauss(sigmaDeg); beta += gauss(sigmaDeg); }
    const hitP = RS.floorHit(RS.dirFromOrientation(alpha, beta, 0), ph);
    return hitP ? [hitP.x, hitP.y] : null;
  });
}

function sides(poly) {
  const n = poly.length, out = [];
  for (let i = 0; i < n; i++)
    out.push(Math.hypot(poly[(i + 1) % n][0] - poly[i][0], poly[(i + 1) % n][1] - poly[i][1]));
  return out;
}

console.log("noiseless reconstruction");
{
  const room = [[0, 0], [4.2, 0], [4.2, 3.1], [0, 3.1]];
  const got = simulate(room, [1.3, 0.9], 1.45, 0, 137);   // arbitrary compass heading
  check(got.every((p) => p !== null), "every corner produced a shot");
  const sw = sides(room), sg = sides(got);
  const maxErr = Math.max(...sw.map((v, i) => Math.abs(v - sg[i])));
  check(maxErr < 1e-9, `side lengths exact (max err ${maxErr.toExponential(2)} m)`);
  check(close(Math.abs(RS.polyArea(got)), 4.2 * 3.1, 1e-9), "area exact");
  const norm = RS.normalizeFrame(RS.ensureCCW(got));
  check(close(norm[0][0], 0, 1e-9) && close(norm[0][1], 0, 1e-9), "normalizeFrame puts corner 0 at the origin");
  check(close(norm[1][1], 0, 1e-9) && norm[1][0] > 0, "normalizeFrame lays wall 0 along +X");
}

console.log("multi-station linking");
{
  //  L-shaped room; station A sees corners 0,1,2,3 - station B sees 3,4,5 and
  //  re-shoots 2,3 so the two halves can be stitched.
  const room = [[0, 0], [5.0, 0], [5.0, 3.0], [2.0, 3.0], [2.0, 6.0], [0, 6.0]];
  const A = simulate(room, [1.5, 1.2], 1.45, 0, 40);
  const B = simulate(room, [0.9, 4.6], 1.45, 0, 250);
  const shared = [2, 3];
  const fit = RS.fitStations(shared.map((i) => B[i]), shared.map((i) => A[i]));
  check(fit !== null, "fit solved from 2 shared corners");
  check(close(fit.scale, 1, 1e-9), `scale check ${fit.scale.toFixed(6)} (1.0 = stations agree)`);
  check(fit.rms < 1e-9, `fit rms ${fit.rms.toExponential(2)} m`);
  const merged = A.slice(0, 4).concat([4, 5].map((i) => RS.applyFit(fit, B[i])));
  const sw = sides(room), sg = sides(merged);
  const maxErr = Math.max(...sw.map((v, i) => Math.abs(v - sg[i])));
  check(maxErr < 1e-9, `stitched L-room sides exact (max err ${maxErr.toExponential(2)} m)`);
  check(close(Math.abs(RS.polyArea(merged)), 5 * 3 + 2 * 3, 1e-9), "stitched area exact");
  check(RS.fitStations([[0, 0]], [[1, 1]]) === null, "one shared corner is not enough");
}

console.log("regularisation");
{
  const off = [[0, 0], [4.2, 0.09], [4.15, 3.12], [-0.06, 3.05]];
  const reg = RS.regularize(off, 8);
  const n = reg.points.length;
  let worstAng = 0;
  for (let i = 0; i < n; i++) {
    const a = reg.points[(i - 1 + n) % n], b = reg.points[i], c = reg.points[(i + 1) % n];
    const u = [a[0] - b[0], a[1] - b[1]], v = [c[0] - b[0], c[1] - b[1]];
    const ang = Math.acos(Math.max(-1, Math.min(1,
      (u[0] * v[0] + u[1] * v[1]) / (Math.hypot(...u) * Math.hypot(...v))))) * R2D;
    worstAng = Math.max(worstAng, Math.abs(ang - 90));
  }
  check(worstAng < 1e-9, `wonky rectangle squared up (worst corner off by ${worstAng.toExponential(2)} deg)`);
  check(reg.snapped.every(Boolean), "all four walls snapped");
  // a genuinely angled wall must NOT be snapped away
  const bay = [[0, 0], [4, 0], [4, 3], [2.5, 4.2], [0, 3]];
  const reg2 = RS.regularize(bay, 8);
  check(!reg2.snapped[2] && !reg2.snapped[3], "45-degree bay walls left alone");
  check(Math.abs(Math.abs(RS.polyArea(reg2.points)) - Math.abs(RS.polyArea(bay))) < 0.3,
        "regularising a bay room barely changes its area");
}

console.log("openings placement");
{
  const room = [[0, 0], [4, 0], [4, 3], [0, 3]];
  const pr = RS.projectOnWall(room, 0, [1.4, 0.02]);
  check(close(pr.u, 1.4, 1e-9) && close(pr.len, 4, 1e-9), "projectOnWall gives the along-wall coordinate");
  check(RS.nearestWall(room, [1.4, 0.05]).wall === 0, "nearestWall picks the south wall");
  check(RS.nearestWall(room, [3.95, 1.5]).wall === 1, "nearestWall picks the east wall");
  check(RS.nearestWall(room, [2, 2.98]).wall === 2, "nearestWall picks the north wall");
}

/* ---- accuracy characterisation (reported, not asserted beyond a bound) -- */
console.log("accuracy under sensor noise (200 trials each)");
const room = [[0, 0], [4.2, 0], [4.2, 3.1], [0, 3.1]];
const trueSides = sides(room), trueArea = 4.2 * 3.1;
for (const sigma of [0.5, 1.0, 1.5, 2.5]) {
  let rawErr = [], regErr = [], areaErrRaw = [], areaErrReg = [];
  for (let t = 0; t < 200; t++) {
    const got = simulate(room, [1.3 + gauss(0.3), 0.9 + gauss(0.3)], 1.45, sigma, rnd() * 360);
    if (got.some((p) => p === null)) continue;
    const reg = RS.regularize(got, 10).points;
    const sg = sides(got), sr = sides(reg);
    rawErr.push(Math.max(...trueSides.map((v, i) => Math.abs(v - sg[i]))));
    regErr.push(Math.max(...trueSides.map((v, i) => Math.abs(v - sr[i]))));
    areaErrRaw.push(Math.abs(Math.abs(RS.polyArea(got)) - trueArea) / trueArea);
    areaErrReg.push(Math.abs(Math.abs(RS.polyArea(reg)) - trueArea) / trueArea);
  }
  const med = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length / 2)];
  const p95 = (a) => a.slice().sort((x, y) => x - y)[Math.floor(a.length * 0.95)];
  console.log(`    sigma=${sigma.toFixed(1)} deg  wall err median ${med(rawErr).toFixed(3)} m ` +
    `/ p95 ${p95(rawErr).toFixed(3)} m   after squaring-up: median ${med(regErr).toFixed(3)} m ` +
    `/ p95 ${p95(regErr).toFixed(3)} m   area err median ${(med(areaErrRaw) * 100).toFixed(1)}% -> ` +
    `${(med(areaErrReg) * 100).toFixed(1)}%`);
  if (sigma <= 1.5) {
    check(med(regErr) < 0.20, `sigma=${sigma}: median wall error after squaring-up under 20 cm`);
    check(med(areaErrReg) < 0.10, `sigma=${sigma}: median area error after squaring-up under 10%`);
  }
}

console.log();
if (fails.length) {
  console.log(`${fails.length} FAILURES:`);
  fails.forEach((f) => console.log("  - " + f));
  process.exit(1);
}
console.log("all phone-side maths tests passed");
