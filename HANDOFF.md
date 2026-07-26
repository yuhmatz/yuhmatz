# ACHILLES v5.36 — Remediation Handoff

**For:** whoever picks up the security/quality work on ACHILLES next (including future-me).
**Companion doc:** `SECURITY_AUDIT_v5.36.md` — the findings. This doc is *what to do about them*.
**Branch:** `claude/security-quality-audit-4ya46b`
**Audit date:** 2026-07-26 · **Code audited:** `jarvis_v536_2.py` (14,453 lines), `worldview_25.html` (4,281 lines)

---

## 1. Status in one paragraph

An audit has been completed. **No code has been changed.** The repo contains the audit report and
this handoff; `jarvis.py` and `worldview.html` on this branch are the *older* versions that were
already committed — the audited v5.36 files were supplied as uploads and are **not** in the repo.
That is the first thing to fix (§3). 44 findings: 6 Critical, 11 High, 15 Medium, 12 Low. Nothing
is blocked on a decision except the four open questions in §7. Phase 0 is roughly 150 lines of
work and closes every remote-attacker path.

---

## 2. The one thing to understand before touching anything

Everything security-relevant in this codebase traces back to a single missing concept: **there is
no definition of "who is allowed to do this."** The check is re-derived inline at each of ~25 HTTP
routes, and it is wrong or absent at most of them.

Three servers run:

| Port | Server | Binds | Auth today | Reachable by |
|------|--------|-------|-----------|--------------|
| 7777 | guarded static (subprocess, `_static_server.py`) | `0.0.0.0` | none | LAN, tailnet |
| 7778 | `_FlightsProxyHandler` (in-process, threaded) | `0.0.0.0` | none¹ | LAN, tailnet, **and any web page on the host** |
| 7779 | `_LocationShareHandler` (in-process) | `127.0.0.1` | token / owner-key | public via Tailscale Funnel |

¹ Five routes check `client_address[0] == "127.0.0.1"`. That is not authentication — a browser
running on the PC *is* 127.0.0.1, so any page the owner opens passes the check. Combined with
`Access-Control-Allow-Origin: *` on every response, the attacker can also read the replies.

Note the asymmetry: **:7779, the genuinely public server, is the best-built one in the file** —
strict CSP, constant-time token compare, rate limiting, socket timeout, no CORS, fixed filenames
only. :7778, which is the one actually exposed to hostile input, has none of that. When fixing
:7778, copy the patterns from `_LocationShareHandler`; they are already correct and already in
this codebase.

Read §2 of the audit ("Executive summary") and finding **C-1** before writing any code.

---

## 3. Do this first (before any remediation)

1. **Get v5.36 into the repo.** The audited files exist only as chat uploads. Commit them —
   otherwise every line reference in the audit points at code nobody can see, and the next person
   re-does the audit.
   ```bash
   git checkout claude/security-quality-audit-4ya46b
   cp <uploads>/jarvis_v536_2.py       jarvis.py
   cp <uploads>/worldview_25.html      worldview.html
   git add -A && git commit -m "Import audited v5.36 sources"
   ```
   Verify the line numbers still line up: `sed -n '3795,3814p' jarvis.py` should be the `/keys`
   route. If it isn't, the audit's line refs are off by an import artefact — re-anchor by
   searching for the function name instead.

2. **Rotate the keys.** Assume compromise if this has ever run on a shared network. See §6.

3. **Take a backup of the live state files** before any schema migration touches them:
   `training_log.json`, `tasks.json`, `search_history.json`, `Obsidian_Vault/`. H-1 involves an
   in-place rewrite and there is no undo.

---

## 4. Work queue

Ordered. Each item is independently shippable. Line refs are against the audited v5.36 file.

### Phase 0 — network hardening · ~150 lines · do it in one sitting

| # | Task | Where | Acceptance criteria |
|---|------|-------|---------------------|
| 0.1 | Delete the `/keys` route; proxy OWM tiles server-side instead | L3795–3814; add `/owm_tile` mirroring `_handle_webcams` L4374 | `curl http://<host>:7778/keys` → 404. Clouds layer still renders. No API key appears in any HTTP response body. |
| 0.2 | Add `_authorized()` + explicit-origin CORS; call it from `do_GET`/`do_POST` before dispatch | `_cors_headers` L3651, `do_GET` L3673, `do_POST` L3663 | Every route except `/state` returns 401 without the key. Cross-origin `fetch()` from a scratch HTML file gets a CORS error, not data. WorldView still works. |
| 0.3 | Restrict `/warwatch_headlines` to URLs already in `_warwatch`, http(s) only, private IPs rejected | `_handle_warwatch_headlines` L5044, `_ww_unfurl_one` L3386 | `?urls=file:///etc/hosts` → empty results. `?urls=http://127.0.0.1:7778/keys` → empty. Real WARWATCH headlines still load. |
| 0.4 | Make the static-server fallback fail closed | `_ensure_worldview_server` L6271–6274 | Simulate `_write_static_server` returning `None` → server does not start, and the failure is logged. `curl http://<host>:7777/` never returns a directory listing. |
| 0.5 | Make the Anthropic budget enforcing | `_wrapped_anth_create` L8396 | With the month's `cost_usd` forced above the cap, any `messages.create` raises and the assistant says so out loud rather than spending. |

**Phase 0 verification script** — keep this, it is the regression test:
```bash
H=<host>
for p in /keys /briefing /calendar /training /quant /ask?q=hi /shop?q=x /company?sym=AAPL; do
  printf '%-28s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' "http://$H:7778$p")"
done
# every line must read 401 (or 404 for /keys). Any 200 is a failure.
curl -s "http://$H:7778/warwatch_headlines?urls=file:///etc/hosts" | grep -q '"results":\[\]' && echo "SSRF closed"
curl -s -o /dev/null -w '%{http_code}\n' "http://$H:7777/"      # must not be 200
```

### Phase 1 — data integrity · days · **the user is losing data now**

| # | Task | Where | Acceptance criteria |
|---|------|-------|---------------------|
| 1.1 | Unify the training-log schema + migrate on load | `_normalize_workout` per audit H-1; `_load_training_log` L8647, `_handle_training._load` L4865 | A log containing both shapes loads, normalises, and round-trips. Voice-logged workouts survive >120 HTTP writes. `recent_workouts()` and the Training tile show the same set. |
| 1.2 | Move `_training_lock` into the accessors | L8647–8676 | No writer touches the file outside `with training_log()`. Grep for `_save_training_log(` returns only the accessor. |
| 1.3 | `_atomic_write_json()` everywhere | `_tasks_save` L6417, `_save_queue` L1569, `_handle_training` L4953, L2366, token writes L11096/L11126/L6673 | `kill -9` mid-write leaves the previous complete file, never a truncated one. |
| 1.4 | Fix the nutrition key names | `weekly_summary` L9700–9701 | Log 500 kcal by voice, ask for the weekly summary, see 500 — not 0. |

**Before 1.1 ships**, check whether records have already been lost:
```bash
python3 - <<'EOF'
import json; d=json.load(open("training_log.json"))
w=d.get("workouts",[])
print("total:", len(w),
      "| voice-schema:", sum(1 for x in w if "date" in x),
      "| http-schema:", sum(1 for x in w if "d" in x))
print("weights:", len(d.get("weights",[])),
      "| voice-schema:", sum(1 for x in d.get("weights",[]) if "date" in x))
EOF
```
If `total` is at or near 120 and `voice-schema` is 0, entries have already been truncated away.
Restore from `backups/obsidian_vault_*.zip` if the vault happens to hold an older copy; otherwise
say so plainly rather than pretending the history is intact.

### Phase 2 — correctness · 1–2 weeks

H-6 (structured data instead of server-rendered HTML) → H-11 (SRI + CSP) → H-4 (crypto pairing
code) → H-5 (split spam-move from sender-block) → M-1/2/3/5 (lock scope, history normalisation,
speech serialisation, deep-learn race) → H-8/9/10 (timeouts, semaphores, bounded caches, drop the
home-dir globs) → M-7/8/9 (one address helper, narrow the doc and learning intercepts).

### Phase 3 — structural

A-1 per-channel `Session` → A-2 split the module (start with `http/auth.py` and `store.py`) →
A-3 pin dependencies, add the regression tests named in the audit.

---

## 5. Landmines for whoever edits this file

Things that will bite you, learned from reading all 14,453 lines:

- **`os.chdir` at L620 is wrapped in a bare `except: pass`.** Several paths are still relative
  (`token.json`, `credentials.json`, `anthropic_usage.json`, `spotify_token.json`, `./backups`).
  If the chdir ever fails these silently resolve elsewhere, and the symptom is "Google logged me
  out" — not an error. Anchor them to `_FILES_DIR` while you are in there (L-3).
- **`getaddrinfo` is monkey-patched twice** (L703 and L9948) and IPv6 is globally disabled for the
  process. Any new endpoint that is IPv6-only will fail with a confusing DNS error (L-2).
- **`_track_anthropic_usage` wraps `Messages.create` globally.** Anything you add that calls the
  Anthropic SDK is billed and counted automatically — but also inherits the 600 s default timeout
  unless you pass one (M-1).
- **`_think_lock` is held across the whole API turn.** Do not call anything slow, interactive, or
  blocking from a tool handler; it freezes voice, Telegram and HTTP simultaneously (M-1).
- **`_training_lock` is not reentrant.** If you move it into the accessors (1.2), the HTTP handler
  must stop taking it directly or you deadlock. Use `RLock` or strict `_unlocked` internals.
- **The tool whitelist inside `think()` (L10650–10664) duplicates `LOCAL_TOOLS`.** It has gone out
  of sync three times (v4.3, v4.22, v5.16k), each time producing a 400 that looked like an API
  bug. Derive it: `frozenset(t["name"] for t in LOCAL_TOOLS)` (M-2).
- **`clean_text()` strips anything in square brackets** and anything that looks like a domain. If
  a reply mysteriously loses content, that is where it went (L1324).
- **Intercepts run before the model and cannot be declined.** Adding one is adding an action the
  assistant will take with no judgement applied. Two current ones already misfire on ordinary
  sentences (M-8, M-9).
- **`_static_server.py` is written to disk and executed on every WorldView open.** Anyone who can
  write that one file gets code execution as the user. Prefer serving in-process (C-6).
- **Windows:** `os.chmod(path, 0o600)` is a no-op. `_write_private()`'s promise of owner-only
  permissions is not delivered on the target platform (M-13).

---

## 6. Secrets inventory

Everything below lives in the project folder and must never be reachable from :7777 or :7778.
`.gitignore` already covers them — verify with `git status --ignored` after any change.

| File | Contains | Rotate how |
|------|----------|-----------|
| `.env` | Anthropic, ElevenLabs, Google Maps, Windy, OWM, AISStream, Telegram token, Spotify id/secret, `BROTHER_TELEGRAM_CHAT_ID` | per provider console |
| `credentials.json` | Google OAuth client | Google Cloud console |
| `token.json` | calendar + **gmail.modify** + drive.file + documents | delete → re-consent |
| `spotify_token.json` | access + refresh token | delete → re-auth |
| `location_owner_key.txt` | uploader key for the **public** share server | delete → restart mints a new one |
| `share_tokens.json` | live share tokens | delete to revoke all shares |
| `telegram_pairing.txt` | pairing code (while unpaired) | auto-removed on pair |
| `backups/*.zip` | the entire Obsidian vault | — |

**Rotate all of these** if ACHILLES has run on a network you do not control. `/keys` (C-2) hands
out the Maps and OWM keys to anyone who asks, so treat those two as public until rotated.

**Scope reduction worth doing:** `token.json` currently carries `gmail.modify`, which permits
deleting mail. If Gmail is only read and labelled, `gmail.readonly` + `gmail.labels` covers
everything except the Trash filter — which H-5 recommends removing anyway.

---

## 7. Open questions — need the owner's answer

These change what gets built. Everything else can proceed without them.

1. **Who is meant to reach :7778?** Options: (a) loopback only, phone goes through Tailscale to
   :7779; (b) tailnet with a shared secret; (c) LAN with a shared secret. This decides whether
   0.2 uses a static key in `.env` or something per-device. *Recommendation: (b).*
2. **Is `deep_learn_domain` allowed to spend $35 unattended?** If not, the confirmation step in
   C-5 needs a spending ceiling per invocation, not just a yes/no.
3. **Should the Gmail spam filter ever use `TRASH`?** H-5 proposes label-only, which contradicts
   the current "block the sender" feature as designed. Losing the auto-block is a real
   functionality regression — the owner should decide, not the implementer.
4. **Is `_geoloc_display_fix`'s rewriting intended to apply worldwide?** As written it renames
   Palestine, Texas. A coordinate-boxed version (M-14) keeps the intended display convention
   without the false positives — confirm that is the intent before changing it.

---

## 8. What was *not* reviewed

Not supplied, so not audited. Two of these sit on the publicly-funnelled server and should be
audited before any further exposure:

- `share_location.html`, `share_upload.html`, `request_join.html` ← **public via Funnel**
- `achilles.html`, `hermes.html`, `roadmap.html`
- `geoloc_baseline_server.py` (localhost:8850)
- `.env`, `start_jarvis.bat`, `reauth_google.py`
- The Obsidian vault contents and any live `training_log.json` / `tasks.json`

Also not done: dependency CVE scan (no lockfile exists — A-3), dynamic testing against a running
instance, and any review of the Vosk/Whisper model files.

---

## 9. Reference — moving parts

Background threads started at boot or on first use, all daemon:

```
main()
├─ App._boot                    models, memory, briefing, backup, then _wake_loop
├─ App._signal_watch            polls .jarvis_show every 0.4s
├─ App._telegram_loop           long-poll getUpdates
├─ App._wake_loop               Vosk; falls back to _wake_loop_whisper
├─ _wv_autostart ─────────────► _ensure_worldview_server
│                               ├─ _start_flights_proxy      :7778  in-process
│                               ├─ _start_vessels_relay      aisstream WebSocket
│                               ├─ _start_warwatch_relay     GDELT 15-min zips
│                               ├─ _ensure_geoloc_baseline   :8850  subprocess
│                               └─ _static_server.py         :7777  subprocess
└─ (lazy) _ensure_location_sharing  :7779 + tailscale funnel
```

Shared mutable globals — all process-wide, all shared across voice/Telegram/HTTP (A-1):
`conversation_history`, `_quiz_state`, `_gmail_pending_spam`, `_last_action`,
`_deep_learn_state`, `_achilles_state`, `_last_timer_lang`.

Locks: `_think_lock`, `_training_lock`, `_tasks_lock`, `_quiz_lock`, `_deep_learn_lock`,
`_usage_lock`, `_location_lock`, `_vessels_lock`, `_warwatch_lock`, `_rate_lock`,
`_quotes_lock`, `_ww_market_lock`, `_ww_company_lock`, `_ww_brief_lock`, `_HISTORY_LOCK`,
`_last_action_lock`, `_warwatch_headline_lock`.

---

## 10. Definition of done

Phase 0 is done when the verification script in §4 shows 401/404 on every line, and WorldView
still loads and renders quakes, flights, vessels, WARWATCH and the property card from the phone.

The whole engagement is done when, in addition: the training log round-trips both schemas with no
loss, no state file can be torn by a kill -9, the CDN scripts carry SRI, a CSP is served with the
pages, and there is a test file that fails if any route stops requiring authentication.
