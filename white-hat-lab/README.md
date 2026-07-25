# 🛡️ White Hat Lab

A **completely local, educational cybersecurity lab** for learning ethical hacking end to end — from theory and methodology, through hands-on practice on intentionally vulnerable endpoints, to writing professional security reports.

It is designed to run **only on your own machine** (bound to `127.0.0.1`) and to be a **safe, legal** place to practise the offensive-security skills that defenders and authorized penetration testers need.

> ⚠️ **This project deliberately contains insecure code.** That is the entire point — you learn by finding and fixing real vulnerability patterns. It must **never** be deployed to a server, exposed to a network, or reached from another machine.

---

## Table of contents

- [What's inside](#whats-inside)
- [Quick start](#quick-start)
- [Project architecture](#project-architecture)
- [The four components](#the-four-components)
- [Educational objectives](#educational-objectives)
- [Rules of Engagement](#rules-of-engagement)
- [Safety considerations](#safety-considerations)
- [Legal disclaimer](#legal-disclaimer)
- [Extending the lab](#extending-the-lab)

---

## What's inside

| Component | What it teaches | Tech |
| --- | --- | --- |
| **Learning Center** | Rules of Engagement + the 8-stage penetration-testing lifecycle | Vanilla ES-module SPA, dark theme |
| **Training Environment** | Hands-on SQLi, reflected XSS, sensitive data exposure, path traversal | Node.js + Express + in-memory SQLite (WASM) |
| **Report Generator** | Turning a finding into a professional Markdown / PDF report | Express + PDFKit |
| **Recon Scanner** | The Scanning phase: port checks + HTTP header/service fingerprinting | Standalone Python 3 (stdlib only) |

Every vulnerable endpoint is paired with extensive inline comments explaining **why the flaw exists, how attackers find it, its real-world impact, and how to fix it** — plus a working *secure* counterpart to compare against.

---

## Quick start

### Prerequisites

- **Node.js** ≥ 18 (tested on Node 22)
- **Python** ≥ 3.8 (for the recon scanner; standard library only, no `pip install` needed)

### Run the lab

```bash
cd white-hat-lab

# 1. Install backend dependencies (express, sql.js, pdfkit — all pure JS)
npm install

# 2. Start the server (binds to 127.0.0.1:3000 only)
npm start

# 3. Open the Learning Center in your browser
#    http://127.0.0.1:3000
```

### Run the recon scanner (in a second terminal, with the lab running)

```bash
python3 tools/recon_scanner.py http://127.0.0.1:3000

# or via npm:
npm run scan
```

To use a different port (still loopback-only):

```bash
WHL_PORT=4000 npm start
```

---

## Project architecture

```
white-hat-lab/
├── package.json              # Scripts + pure-JS dependencies
├── README.md                 # You are here
│
├── backend/                  # Express server (the training environment)
│   ├── server.js             # Entry point + loopback safety guards
│   ├── config.js             # Hard-coded 127.0.0.1 bind (safety-critical)
│   ├── db/
│   │   └── init.js           # In-memory SQLite seed (sql.js / WASM)
│   ├── routes/
│   │   ├── vulnerable.js      # INTENTIONALLY vulnerable endpoints (commented)
│   │   ├── secure.js          # Secure reference implementations (the fixes)
│   │   └── reports.js         # Markdown + PDF report generation
│   └── lab-files/            # Simulated, clearly-fake files for the exposure demo
│
├── frontend/                 # No-build SPA served by the backend
│   ├── index.html
│   ├── css/styles.css        # Dark-theme design system
│   └── js/
│       ├── app.js            # Hash router + sidebar + server status
│       ├── util.js           # DOM / formatting helpers
│       ├── data/             # Educational content (theory as data)
│       │   ├── methodology.js
│       │   └── rulesOfEngagement.js
│       └── views/            # One module per screen
│           ├── home.js
│           ├── learningCenter.js
│           ├── trainingEnv.js
│           ├── reportGenerator.js
│           └── tools.js
│
└── tools/
    └── recon_scanner.py      # Standalone Python recon/scanning demonstrator
```

**Design choices**

- **No frontend build step.** The UI is plain HTML/CSS + native ES modules, so there is nothing to compile — clone, `npm install`, `npm start`. This keeps the lab approachable and easy to read.
- **Pure-JS dependencies only.** `sql.js` (SQLite compiled to WebAssembly) gives a *real* SQL engine for an authentic injection demo without native compilation, so `npm install` works on any OS. `pdfkit` produces PDFs with no system dependencies.
- **Education content is data.** Methodology stages and Rules of Engagement live in `frontend/js/data/`, so new modules are added without touching view logic.
- **Vulnerable and secure code sit side by side.** `routes/vulnerable.js` shows the flaw; `routes/secure.js` shows the fix; the UI lets you fire the same payload at both.

---

## The four components

### 1. Learning Center

- **Rules of Engagement** — explicit authorization, scope definition, responsible disclosure, safety-first, legal considerations, data handling, and the golden rule (never test without permission), plus a pre-engagement checklist.
- **Ethical Hacking Methodology** — an interactive, clickable timeline of the full lifecycle: **Reconnaissance → Scanning → Enumeration → Vulnerability Assessment → Exploitation → Post-Exploitation → Documentation → Reporting.** Each stage lists its description, purpose, typical tools, expected outputs, and best practices.

### 2. Training Environment (intentionally vulnerable)

| Scenario | Endpoint | Try it |
| --- | --- | --- |
| **SQL Injection** (auth bypass) | `POST /api/vuln/login` | Username `admin'--` with any password. Or dump every row with `' OR '1'='1' --`. |
| **Reflected XSS** | `GET /api/vuln/profile?name=` | `name=<script>alert('xss')</script>` |
| **Sensitive Data Exposure** | `GET /admin-backup` | Browse to the "hidden" backup directory — no auth required. |
| **Path / Directory Traversal** | `GET /api/vuln/download?file=` | `file=database_backup.sql`, then escape with `file=../config.js`. |

Each scenario in the UI includes the OWASP category, a severity badge, a hint, an interactive tester, and (for SQLi) a one-click comparison against the **secure** endpoint so you can watch the same payload fail once the code is fixed.

> The exposure and traversal demos operate on **simulated, obviously-fake files** in `backend/lab-files/`. The traversal flaw is genuine (so `../` works), but the impact is contained to your own machine over loopback — exactly the kind of controlled environment ethical practice requires.

### 3. Report Generator

A structured finding form (title, category, severity, CVSS score, affected component, description, steps to reproduce, proof of concept, risk assessment, remediation) with a **live preview** and one-click export to:

- **Markdown** (`POST /api/reports/markdown`) — structured like a real pentest report.
- **PDF** (`POST /api/reports/pdf`) — generated server-side with PDFKit.
- **Print / Save as PDF** — a print stylesheet for browser-native PDF export.

Click **Load example finding** to see a complete SQL Injection write-up instantly.

### 4. Recon Scanner (`tools/recon_scanner.py`)

Simulates the **Scanning** phase against your local lab:

- Verifies the target resolves to a **loopback address** and refuses anything else.
- TCP-connect scans common web ports (`80, 443, 3000, 5000, 8000, 8080, 8443`).
- Fetches HTTP response headers and fingerprints the server.
- Flags **missing security headers** (CSP, X-Content-Type-Options, etc.).
- Performs light content discovery against a small, safe wordlist and highlights sensitive paths like `/admin-backup`.
- Prints a readable, colorized report (or `--json` for machine-readable output).

```bash
python3 tools/recon_scanner.py http://127.0.0.1:3000
python3 tools/recon_scanner.py 127.0.0.1 --ports 80,443,3000,8080
python3 tools/recon_scanner.py http://127.0.0.1:3000 --json
```

---

## Educational objectives

By working through the lab you will be able to:

1. State the **ethical and legal ground rules** of security testing and why they come first.
2. Describe each stage of the **penetration-testing lifecycle** and what it produces.
3. **Identify and exploit** four foundational web vulnerability classes in a safe sandbox.
4. **Read the fix**: understand parameterized queries, output encoding, access control, and safe file handling by comparing vulnerable and secure code.
5. Run a basic **reconnaissance scan** and interpret its output.
6. Produce a **professional security report** that a real team could act on.

**Suggested path:** Rules of Engagement → Methodology → run the recon scanner → exploit each scenario → read the `HOW TO FIX` comments in `backend/routes/vulnerable.js` → write it up in the Report Generator.

---

## Rules of Engagement

These apply to using this lab **and** to any real-world testing you do afterwards:

1. **Explicit authorization.** Never test a system without written, signed permission from its owner. Your authorized scope for this project is the White Hat Lab running on your own `127.0.0.1` — and nothing else.
2. **Scope definition.** Only interact with the assets explicitly in scope. Anything not listed is out of scope.
3. **Responsible disclosure.** Report real vulnerabilities privately and give owners time to fix them before any public discussion.
4. **Safety first — do no harm.** Prefer non-destructive proofs of concept. Do nothing that could damage data or disrupt availability.
5. **Legal awareness.** Understand the laws that apply to you and your target (e.g. the US CFAA, the UK Computer Misuse Act, GDPR for personal data).
6. **Confidentiality.** Treat anything you access as sensitive; minimize, protect, and dispose of it responsibly.
7. **Never attack without permission.** The skills you learn here are for defense and authorized testing only.

---

## Safety considerations

- **Loopback only.** `backend/config.js` hard-codes the bind address to `127.0.0.1`. `backend/server.js` additionally (a) refuses to start on any non-loopback host and (b) rejects any request that did not arrive over loopback. Do not change these.
- **Do not deploy.** This code is intentionally insecure. Never run it on a shared host, a VM reachable from a network, a cloud instance, or behind a public reverse proxy.
- **Fake data only.** All credentials, secrets, and "PII" in this project are obviously fake and authenticate to nothing.
- **The recon scanner is loopback-locked.** It refuses to scan any target that does not resolve to `127.0.0.1` / `::1`.
- **Firewall as defense in depth.** If you want extra assurance, block inbound connections to the lab's port at your OS firewall.

---

## Legal disclaimer

This software is provided **strictly for educational purposes** and for use **only against systems you own or are explicitly authorized in writing to test.**

Unauthorized access to computer systems is **illegal** in virtually every jurisdiction. The techniques demonstrated here can cause serious harm and carry serious legal consequences when used without permission. The authors and contributors of White Hat Lab accept **no liability** for any misuse of this software or any damage arising from it. By using this project you agree that you are solely responsible for your actions and for complying with all applicable laws.

**If you do not have explicit authorization, do not test it.**

---

## Extending the lab

The project is structured so new learning modules are easy to add:

- **New theory module:** add data to `frontend/js/data/`, a view in `frontend/js/views/`, and one entry to the `ROUTES` array in `frontend/js/app.js`.
- **New vulnerability scenario:** add an entry to the catalog and a handler in `backend/routes/vulnerable.js` (and, ideally, a secure counterpart in `secure.js`), then a tester in `frontend/js/views/trainingEnv.js`.
- **New report format:** add an endpoint to `backend/routes/reports.js`.

---

*Built for learning. Local scope only. Do no harm.* 🛡️
