"""
JARVIS v3.0 — voice assistant: bilingual, web search, tools, red-orange orb
============================================================================
(Version is updated by hand on each change. Current: v5.23 — 25 Jul 2026 — the static server no longer hands out .env, credentials or source.)

What works now:
  * Wake word "Hey JARVIS" (continuous background listening); empty screen until
    woken. Pre-roll buffer so the first command word isn't cut off.
  * Voice in (Whisper) + voice out (edge-tts). English voice = British "Alfred"
    style (en-GB-Ryan), slowed/lowered for a calmer butler delivery.
  * Language lock: Hebrew->Hebrew, anything else->English. Never a 3rd language.
  * Continuous conversation: answers a follow-up without needing the wake word.
  * Web search in real time (decides on its own when current info is needed).
  * Tool Use: open_app (closed allow-list) and save_note (to Obsidian).
  * Function keys: F1 typing box, F2 save last exchange, F3 repeat last reply.
  * Noise filtering (high threshold + short-transcript discard).
  * Weather defaults to Alfei Menashe, Celsius only. Personal/family context.
  * GLOWING ORB in red-orange ("molten core") across all states, Pillow-rendered
    with a near-black transparency key (no pink halo); canvas fallback if no PIL.
  * Forces its own working directory + windowless relaunch via pythonw, so it
    runs cleanly when launched from start_jarvis.bat (double-click).

Changelog:
  v4.74 - WAKE/DISPLAY fix: the floating orb never appeared when invoked.
          The v4.70 Vosk wake engine returned early (leaving the wake path
          dead) whenever Vosk was not installed or its model could not load,
          and since the orb is hidden after boot it could then never pop on
          the wake word - so activation produced an empty screen. _wake_loop
          now falls back to the Whisper wake engine (the proven v4.67 path,
          reusing the already-loaded self.wake_model) instead of returning,
          so saying the wake word always pops the orb even without Vosk.
  v4.67 - Reliability + safety pass. WAKE: transcribe_wake no longer
          stacks VAD + double no-speech filtering, which on the tiny
          model trimmed a short isolated "Achilles"/"Jarvis" to an empty
          string so the wake never fired and nothing came up on screen;
          it now decodes permissively and relies on WAKE_GATE +
          detect_wake. The wake hit-guard loosened from <=4 to <=8 words
          so a phrase expansion no longer discards a valid wake; mic-open
          failures are surfaced on-screen instead of only printed.
          DISPLAY: animate() is now crash-proof (whole frame guarded,
          reschedule in finally) so one bad render frame can't kill the
          loop and leave the orb permanently hidden; _face_req applies
          the expand immediately so the orb pops the instant the wake
          fires. BRAIN: conversation_history is guarded by a single
          _think_lock (shared by voice / Telegram / the /ask HTTP thread),
          bounded to 24 messages, with orphaned-tool_use self-healing -
          fixing cross-thread corruption (400 "roles must alternate"),
          unbounded token growth, and the permanent-400 poisoning after a
          mid-tool truncation; max_tokens 500 -> 1024; open_achilles added
          to the tool-dispatch whitelist (was missing -> 400). SECURITY:
          /ask and the mutating /todo endpoints are now loopback-only (the
          proxy binds 0.0.0.0 for the phone; those ran the brain / spent
          API budget / mutated state with no auth). RESOURCES: fired
          timers prune themselves; the v4.40 IPv4 patch honours an
          explicit address family and falls back gracefully. LOGIC: a
          quiz can always be cancelled; "I ran the tests"/"רצתי לחנות"
          are no longer logged as workouts; "everything is better" no
          longer clears an injury. VESSELS: AIS heading/COG sentinels
          (511/360/null) are validated so a ship is never drawn at a fake
          bearing, and ts refreshes on every message. Also a new
          worldview.html frontend that renders the live ships (plus
          aircraft and USGS quakes) from the /vessels and /flights feeds.
  v4.42 - Prompt caching to cut API cost. JARVIS_SYSTEM_PROMPT
          (~4k tokens of memory, city list, family context, and
          tool rules) was being re-sent on every API call and on
          every tool-use loop iteration - the bulk of the input
          bill. think() now splits the system prompt into the
          constant JARVIS_SYSTEM_PROMPT (marked cache_control=
          ephemeral) plus a tiny uncached block for the language
          note and current timestamp, so the cached prefix stays
          byte-identical between calls. Anthropic caches the
          constant for ~5 min and bills cache hits at ~10%% of the
          input rate, roughly halving the bill with no quality
          change. A plain-string fallback (sys_prompt_plain) is
          kept for the no-tools retry path. Spend is visible via
          the v4.30 'budget' / 'התקציב' command.
  v4.41 - system_health: real live probe for Calendar / Gmail
          instead of file-existence check. v4.24 only verified
          credentials.json and token.json were on disk, so a
          revoked refresh token still reported 'OK'. Now
          actually calls _calendar_service() and runs
          calendarList().list(maxResults=1) - reports OK only
          if the live call succeeds, FAIL with exception class
          name if anything raises. Gmail shares the token so a
          calendar pass implies Gmail too.
  v4.40 - Force IPv4 for outbound network. Tiny monkey-patch
          at module-import replaces socket.getaddrinfo with an
          AF_INET-only wrapper so every TCP connect from this
          process goes over IPv4. Fixes WinError 10060 timeouts
          on calendar / Gmail caused by httplib2 picking IPv6
          first when local IPv6 routing is broken (common on
          Israeli ISPs). Idempotent (flag on socket module).
          Process-local: does NOT change Windows network or
          DNS settings.
  v4.39 - Weight logging + 68kg red-line (coach brick 4).
          log_weight() sets last_weight_kg / last_weight_date
          and appends to a weights history list; this is what
          finally lights up v4.28's briefing red-line warning
          and v4.38's summary. weight_check() reports latest
          weight vs weight_target_min_kg (default 68): below /
          near / ok, days since, and trend vs previous weigh-
          in. Voice: 'log weight 70.5' / 'שקלתי 71' to log;
          'weight check' / 'מה המשקל' to check. Fully additive
          - no _boot/TTS changes. Reuses v4.33 _load/_save.
  v4.38 - Weekly training summary (coach brick 3, read-only).
          weekly_summary() digests this ISO week's workouts
          (count + type breakdown), latest weight vs red-line,
          today's nutrition vs target, active injuries, and a
          pointer to the progress report. Voice: 'weekly
          summary' / 'סיכום שבועי'. Writes nothing; reuses
          v4.33 _load_training_log.
  v4.37 - Fitness benchmarks & progress (coach brick 2).
          Structured test logging into fitness_tests +
          progress vs EDITABLE targets in standards{} (both in
          training_log.json). Metrics: run_2km, run_3km,
          pullups, pushups, situps, swim_400m. Voice: 'log run
          2k 8:45' / 'log pullups 18' / 'תרשום מתח 18' to log;
          'progress' / 'מצב כושר' for a report (latest vs
          target + delta from previous test); 'set target
          pullups 20' / 'יעד מתח 20' to change a target.
          Targets are placeholders, NOT official numbers -
          edit standards.<metric>. Reuses v4.33 _load/_save.
  v4.36 - Workout logging (combat fitness coach, brick 1).
          log_workout() appends to the workouts list in
          training_log.json and refreshes the v4.28 briefing
          fields (last_workout_type, last_workout_date,
          weekly_workouts) with an automatic ISO-week reset;
          recent_workouts() reports this week's count plus the
          last 5 with relative dates and auto-classified type
          (cardio/swim/strength/general). Voice: 'log workout:
          X' / 'I ran 5k' / 'I trained X' / 'תרשום אימון X' /
          'רצתי X' to log; 'workout status' / 'מה אימנתי השבוע'
          to recall. Raw text stored verbatim. Reuses v4.33's
          _load/_save_training_log.
  v4.35 - Injury / recovery tracker. log_injury() appends an
          entry (desc, logged date, status) to the injuries
          list in training_log.json; injury_status() reports
          active injuries with relative dates;
          mark_recovered() flags a matching active injury as
          recovered (no keyword needed when only one is
          active). Voice: 'log injury: X' / 'I hurt my X' /
          'תרשום פציעה X' to log; 'injury recovered: X' / 'my
          X healed' / 'החלמתי מX' to clear; 'injury status' /
          'מצב פציעות' to check. Recovered entries stay in the
          JSON for history but are filtered from the active
          report. Reuses v4.33's _load/_save_training_log.
  v4.34 - Self-test / quiz mode. 'quiz me on X' / 'test me'
          / 'תבחן אותי על X' picks a knowledge note in that
          domain (or any note), has Sonnet write one
          exam-style question + model answer, stores it as
          pending in a lock-guarded _quiz_state, and speaks
          only the question. A pending-quiz check at the top
          of think() routes the user's next utterance to
          evaluate_quiz_answer, which has Sonnet grade it
          (correct / partial / wrong + the missed point) and
          clears the state. 'stop' / 'cancel' / 'עזוב' while
          pending drops the quiz. One quiz pending at a time;
          both calls are tracked by the v4.30 budget.
  v4.33 - Nutrition / macro tracker. log_calories() and
          log_protein() accumulate daily intake in
          training_log.json (shared with v4.28), resetting
          each calendar day via a nutrition_date field.
          nutrition_status() reports today's calories and
          protein vs targets (defaults 3000 kcal / 130 g,
          editable as target_calories / target_protein_g).
          Voice: 'log 2500 calories' / 'add 40 grams
          protein' / 'אכלתי 2500 קלוריות' to log; 'nutrition'
          / 'macros' / 'תזונה' to check. The log parser
          requires a number, a unit word, and a logging verb
          so questions like 'how many calories in a banana'
          do not false-trigger a log.
  v4.32 - Decisions log. log_decision() appends a timestamped
          entry to Obsidian_Vault/Decisions.md (its own
          Markdown note); recent_decisions() reads back the
          last 5 with relative dates. Voice: 'log decision:
          X' / 'record decision X' / 'תרשום החלטה X' to log;
          'my decisions' / 'recent decisions' / 'מה החלטתי'
          to review. A parsing intercept extracts the
          decision text after the trigger; a review intercept
          matches the read-back phrases. Both run in think()
          before the model so logging is deterministic.
  v4.31 - Daily vault backup. A new backup_vault() helper
          creates a timestamped DEFLATED zip of the entire
          Obsidian_Vault folder under ./backups/ next to
          jarvis.py, then prunes to BACKUP_KEEP=14 newest.
          Auto-trigger: first launch of each calendar day
          via .jarvis_last_backup marker (same pattern as
          .jarvis_last_briefing), running in a daemon
          thread so wake-loop startup is never blocked by
          zip compression. Voice trigger: a deterministic
          intercept catches 'backup' / 'backup now' /
          'גיבוי' / 'גבה' / 'תגבה את הפתקים' and runs the
          backup synchronously, returning file count and
          zip size. Local-only by design - no Google Drive
          OAuth scope change; Drive upload can be added
          later without touching this layer.
  v4.30 - Monthly Anthropic API cost budget. A monkey-patch
          on anthropic.resources.messages.Messages.create
          wraps every API call so input/output tokens are
          read from response.usage, priced against the
          model family (Sonnet $3/$15, Opus $15/$75, Haiku
          $0.80/$4.00 per million tokens), and accumulated
          in anthropic_usage.json keyed by YYYY-MM. The cap
          comes from env JARVIS_MONTHLY_BUDGET_USD (default
          $50). Voice command 'budget' / 'התקציב' returns
          spend, percent of cap, and call counts. Threshold
          alerts fire once per month when crossing 80%
          (warning) and 100% (over) - spoken in a background
          thread so the API call never blocks on TTS. Cache
          tokens are billed at the input rate, a slight
          overestimate vs. Anthropic's 90%%-off cache hits
          but never an underestimate. Counter resets
          automatically each calendar month (new month_key
          in the JSON).
  v4.29 - Undo command. Single-step undo for the four most
          common mutating actions: calendar_add deletes the
          just-added event; calendar_delete re-inserts the
          just-deleted event (body cached via events().get()
          before deletion); save_note trims the appended
          line off the notes file; set_timer cancels the
          pending threading.Timer. Voice triggers (EN: 'undo',
          'revert', 'cancel that', 'scratch that'; HE:
          'tevatel', 'batel et ze', 'bittul', 'undo',
          'tachzir et ze') are caught by a deterministic
          intercept in think() so the model never sees them.
          The recorded action is consumed on undo - a second
          'undo' is a no-op, never a double-reverse.
  v4.28 - Daily briefing now includes a TRAINING section
          pulled from training_log.json next to jarvis.py.
          The new _training_briefing_section helper reads
          optional fields last_weight_kg, last_weight_date,
          last_workout_type, last_workout_date,
          weekly_workouts, and weight_target_min_kg
          (defaults to 68 - Matan's red line), formats
          human-readable lines (e.g. 'Last weight: 71.2 kg
          (2 days ago); +3.2 kg above 68 kg target'), and
          inserts them into the briefing facts. The model
          is instructed to mention training when present,
          especially if the user is below the 68 kg minimum
          target or hasn't trained in several days. If no
          log file exists the TRAINING block is omitted and
          the briefing is unchanged. This is the data
          contract for the future combat-fitness coach
          (voice workout logging).
  v4.27 - Duplicate-learning prevention. Before generating a
          sub-topic note inside deep_learn_domain,
          _find_existing_note scans every other domain folder
          in Obsidian_Vault/Knowledge/ for the same slug. If a
          match is found, _learn_one_into_domain skips the
          Claude call entirely and writes a small stub that
          wiki-links to the existing note. Same-domain matches
          are excluded so re-runs within a curriculum still
          regenerate normally. Saves ~$0.50-0.70 per duplicate
          on overlapping fields (e.g. chemistry vs.
          biochemistry).
  v4.26 - 'What did I learn this week?' summary. Deterministic
          intercept catches 'what did I learn this week', 'מה
          למדתי השבוע', and similar. Walks
          Obsidian_Vault/Knowledge/ for .md files with mtime in
          the past 7 days, extracts each note's title and
          domain, groups them, and asks Sonnet to phrase a 2-4
          sentence summary (~$0.01). Falls back to raw facts
          on any error.
  v4.25 - Auto-link knowledge notes with Obsidian wiki links.
          When learn_topic or _learn_one_into_domain generates a
          new note, _link_existing_notes scans every note in
          Obsidian_Vault/Knowledge/ (across all domains),
          extracts each one's title from YAML frontmatter or the
          first '# heading', and wraps the FIRST occurrence of
          each title in the new note with [[slug|original-text]].
          First-occurrence-only avoids link clutter; minimum
          title length is 6 chars; the note's own slug is
          skipped. Best-effort - any error returns the
          unmodified note so this never blocks a write.
  v4.24 - System health check command. Deterministic intercept
          in think() catches 'system health', 'health check',
          'are you ok', 'בדיקה עצמית', 'בריאות מערכת',
          'הכל עובד' etc. The handler runs SHALLOW checks (no
          expensive API calls): Anthropic / ElevenLabs / Google
          Maps keys loaded; Calendar + Gmail credentials and
          token; Spotify credentials and token;
          worldview.html on disk; Knowledge folder + domains;
          background learning thread state; basic internet
          reachability via a DNS port to 1.1.1.1. Then asks
          Sonnet to phrase the snapshot naturally (~$0.01).
          Falls back to raw facts on any error.
  v4.23 - 'What's new?' command. Deterministic intercept in
          think() catches the user asking what changed recently
          ('what's new', 'what changed', 'מה השתנה', 'מה חדש',
          'מה הוספנו', etc.). On a match, JARVIS reads its own
          Changelog block at the top of jarvis.py, pulls the 3
          newest entries, asks Sonnet to phrase them naturally
          in the user's language (~$0.01 per call), and returns
          the summary. Falls back to the raw entries on any
          error.
  v4.22 - Voice-mode 400 fix (orphaned tool_use). The four
          knowledge tools (learn_topic, deep_learn_domain,
          resume_learning, learning_status) were offered to
          the model in LOCAL_TOOLS but were MISSING from the
          tool-dispatch whitelist inside think(). When the
          model chose one, no tool_result was produced, so the
          next messages.create call carried a tool_use with no
          matching tool_result and the API returned 400. Search
          mode was unaffected (it never offers those tools).
          Same bug class as v4.3. Fix: add the four names to the
          dispatch whitelist so a tool_result is always returned.
  v4.21 - Deterministic intercept for learning commands. Even with
          v4.20's CRITICAL block, the model kept inventing excuses
          ("already operate at that level", "already covered")
          instead of calling deep_learn_domain. v4.21 installs a
          regex-based intercept at the top of think() that detects
          clear learning commands in EN/HE and calls the knowledge
          tool DIRECTLY in Python, skipping the model entirely. No
          refusal possible. Patterns covered: 'learn X', 'deep-
          learn X', 'study X', 'research X', 'תלמד X', 'תלמד לעומק
          X', 'ללמוד X', 'תחקור X', etc. The word 'lao'omek' / 'in
          depth' / 'deep' forces deep_learn_domain.
  v4.20 - Force the brain to call knowledge tools instead of
          answering conversationally. After v4.19 the model would
          read "deep-learn materials science" as a meta-question
          about its own capabilities ("I already operate at that
          level") rather than as a command to invoke
          deep_learn_domain. v4.20 prepends a CRITICAL TOOL-USE
          RULES section to the system prompt with explicit examples
          of WRONG vs RIGHT behavior, which overrides JARVIS's
          conversational bias for learn/study/research commands.
  v4.19 - Knowledge Module, Stage 2: Deep Domain Learning. The user
          can ask JARVIS to study a whole domain ("deep-learn
          chemistry" / "tilmad kol ha-chimya la'omek"). JARVIS
          decomposes the domain into a sub-topic curriculum, saves it
          to Knowledge/<domain>/_queue.json, and a background daemon
          thread learns the sub-topics one at a time (deep note each),
          updating the queue + _index.md after every note. A hard
          count cap (default 15 notes/run) bounds the API cost; the
          queue on disk makes the whole thing resumable across
          restarts via "continue learning <domain>". New tools:
          deep_learn_domain, learning_status, resume_learning.
  v4.18 - Knowledge Module, Stage 1. New tool `learn_topic` takes a
          subject the user wants to study ("JARVIS, learn aerodynamics"
          / "JARVIS, tilmad ..."), asks Claude to produce a structured
          deep study note (TL;DR, foundational principles, key equations,
          sub-topics, common questions, sources, related topics), and
          writes it as Markdown into <vault>/Knowledge/<topic>.md.
          Knowledge notes persist on disk and survive across sessions
          and projects. Stage 2 (recall + incremental deepening) and
          Stage 3 (project orchestration: "build me a drone" auto-
          decomposes into learning tasks) follow in later versions.
          Scope: broad science / engineering / domain theory is fair
          game; specific weapon recipes are not - the underlying model
          declines those, so the note will contain the public physics
          and theory only.
  v4.17 - WorldView now serves itself over a local HTTP server (port
          7777, bound to 127.0.0.1) instead of file://. Chromium
          refuses to load Google Maps JavaScript and Photorealistic
          3D Tiles from file:// origins (they're treated as unique
          opaque security origins), so opening WorldView now spawns
          a one-shot python -m http.server in the background and
          points Edge --app at http://localhost:7777/worldview.html.
          Server is started once per JARVIS session, reused across
          multiple opens, and not exposed on the LAN. worldview.html
          was upgraded to v14 in the same round: Google Photorealistic
          3D Tiles toggle (with localStorage'd API key), MapLibre GL
          satellite globe with deep street-level zoom, USGS quakes,
          Open-Meteo weather, and city/coords search.
  v4.16 - WorldView now opens in Microsoft Edge --app mode: a clean,
          chromeless window with no tabs, address bar, or bookmarks
          bar, so the globe looks like a native desktop app rather
          than a browser tab. Falls back to the default browser if
          Edge is not installed at the standard Win10/11 paths.
          worldview.html itself was upgraded to v2 in the same round:
          a 5-option USGS feed selector (M2.5+ / M4.5+ past 24h, all
          past 24h, M4.5+ past week, significant past week) and a
          click-to-show detail panel (magnitude, place, depth, time,
          coordinates, USGS link).
  v4.15 - WorldView integration. New tool open_worldview opens the
          local worldview.html (a Globe.GL 3D Earth with live USGS
          earthquake data; texture is embedded same-origin in the
          HTML so there is no external tile dependency) in the
          user's default browser. Triggered by spoken phrases like
          'open WorldView', 'open the globe', 'show earthquakes',
          or Hebrew equivalents - the brain decides when to call
          it. File lives at <project>/files/worldview.html, next to
          jarvis.py. Built on Globe.GL after CesiumJS surface
          rendering refused to draw imagery on this Win11 / Chrome /
          file:// stack across seven iterations.
  v4.14 - Product search now DEFAULTS to the Israeli market but can be
          OVERRIDDEN per request. A normal where-can-I-buy-X search still
          finds Israeli stores only, priced in shekels. NEW: when the
          user explicitly names another country or market (for example:
          search the US market, find this in Germany, in Hebrew בשוק
          האמריקאי or בגרמניה), that one search targets stores in that
          country instead, priced in the local currency, with the
          Israel-only rule lifted for that request only. Pure prompt
          change in the search overlay.
  v4.13 - Product search links are now CURATED, not raw. The search
          brain picks the best DIRECT product pages it found and returns
          them in a machine-readable <<<LINKS>>> block, which the code
          parses and shows as the clickable rows (the block is stripped
          from the spoken text). Falls back to the raw web_search results,
          re-ordered so deep product pages beat bare store homepages, if
          the brain returns none - so the list is never empty. Fixes broad
          queries showing a store homepage/category page instead of the
          actual item page.
  v4.12 - Wake no longer 'wakes then sleeps'. If you say 'Hey JARVIS' and
          pause (waiting for an answer) instead of giving the command in
          the same breath, JARVIS now says a short 'Yes, sir?' and keeps
          listening for the command instead of going back to sleep and
          forcing a second 'Hey JARVIS'.
  v4.11 - Spotify auto-device: before each playback action JARVIS lists
          devices and, if none is active but one exists, transfers playback
          to it. Fixes the recurring 'no active device' error whenever
          Spotify went idle between commands.
  v4.10 - Spotify control. Six new brain tools: spotify_play (search & play
          or resume), spotify_pause, spotify_next, spotify_previous,
          spotify_volume, spotify_now_playing. OAuth flow runs once on the
          first use (browser opens, you grant access, tokens stored in
          spotify_token.json next to jarvis.py). Requires Spotify Premium,
          Spotify open on some device, and SPOTIFY_CLIENT_ID +
          SPOTIFY_CLIENT_SECRET in .env.
  v4.9  - Calendar delete + update. New tools calendar_delete(event_id) and
          calendar_update(event_id, summary, start_iso, end_iso, location).
          calendar_read now also returns each event's id in [id=...] so the
          brain can target a specific event. Flow: read -> find id -> act.
  v4.8  - Timers / reminders. New tool set_timer(minutes, label): 'set a
          timer for 5 minutes', 'remind me in 10 minutes', Hebrew variants.
          When it elapses JARVIS beeps and announces it by voice in the
          conversation language, with the label if given. Voice + typed.
  v4.7  - Daily briefing also triggers on typed input and inside the search
          window (a greeting there gives a briefing, not a generic reply).
  v4.6  - Force IPv4 for all outbound connections. IPv6 routing to Google
          was broken on this machine, so the Calendar/Gmail client (httplib2)
          hung on IPv6 and failed with TimeoutError 10060, while Anthropic /
          ElevenLabs worked (their clients fall back to IPv4 fast). Filtering
          socket.getaddrinfo to IPv4 at startup fixes calendar + email.
  v4.5  - "Good morning / good evening" daily briefing. A spoken greeting
          (good morning/afternoon/evening, or Hebrew boker tov / tzohoraim
          tovim / erev tov) gives a short butler briefing: weather for Alfei
          Menashe (Celsius, free Open-Meteo), the day's calendar, an email
          summary. Evening focuses on tomorrow. Also fires automatically on
          the first launch of each day.
  v4.4  - Search panel now inherits the main JARVIS_SYSTEM_PROMPT and can
          use find_places / get_directions (it is an extension of the main
          voice mode, not a disconnected island).
  v4.3  - Brain 400 fix: find_places / get_directions were missing from the
          tool-name filter in think(), so the model got a tool_use with no
          matching tool_result and the next call returned 400. Also: F5 now
          stops speech globally, the Anthropic key is checked at startup, and
          Brain errors print a full traceback.
  v4.2  - Voice selection fix: the old check used "any Hebrew character at all
          => use edge-tts". So when JARVIS answered a search like "find pizza
          in Kfar Saba" with mostly English text that contained Hebrew place
          names (e.g. "גוטליב"), it dropped the Alfred voice and used the
          default edge-tts voice instead. Now we use a NEW is_mostly_hebrew()
          check (majority of letters must be Hebrew) - so English-with-place-
          names still gets the Alfred voice as intended.
  v4.1  - Two fixes for the search window: (1) the spoken response is now hard-
          capped at 2 short sentences with an explicit example - the brain
          stops dumping long numbered lists of results into the spoken text
          (results live in the link rows below). (2) Esc now also CUTS OFF any
          in-progress speech immediately, not just closes the window - so if
          JARVIS is still talking when you press Esc, he stops mid-sentence.
  v4.0  - Israeli city recognition: the system prompt now includes a curated
          list of ~30 common Israeli cities (canonical English + Hebrew names)
          plus explicit examples of typical Whisper mis-transcriptions to fix
          silently ("kfar sabah" -> Kfar Saba, "petah tikvah" -> Petah Tikva,
          etc.). The brain now handles place-name correction itself before
          calling find_places / get_directions, so the user can speak naturally
          without worrying about how Whisper spells the city. Pure prompt
          change, no new code paths.
  v3.25 - Two new brain tools wired up via Google Maps APIs (with the new
          GOOGLE_MAPS_API_KEY in .env):
            find_places(query)      - Places Text Search, biased to Israel,
                                      returns top 5 results with rating,
                                      open/closed, and address. Hebrew works.
            get_directions(dest)    - Driving time + live traffic via Directions
                                      API; defaults the origin to home (Alfei
                                      Menashe). Returns distance, normal and
                                      with-traffic durations, and route name.
          The brain decides when to call each (e.g. "find me sushi in Tel Aviv"
          -> find_places; "how long to Azrieli?" -> get_directions).
  v3.24 - Added a top-left HUD to the search window: a live clock (day, date,
          HH:MM:SS), the running version number, a STATUS line, and a PROJECTS
          section. The visible version number also lets us confirm at a glance
          which build is actually running. The search panel now also addresses
          Matan as "sir"/"אדוני" (it used to say his name). NOTE: if you still
          see on-screen buttons in the window, you are running an OLD build - the
          new window has no buttons, only the F-key hint line.
  v3.23 - Three changes: (1) the search window is now driven by F-KEYS instead of
          on-screen buttons (F1 type, F2 speak, F3 image) - while the window is
          open those keys drive it; when it's closed they keep their old main-
          window jobs. (2) F5 stops JARVIS mid-sentence (cuts the current spoken
          reply) while the search window is open. (3) JARVIS now always addresses
          Matan as "sir"/"אדוני" and never by his first name unless he asks about
          himself.
  v3.22 - Search window reimagined as a FULLSCREEN, borderless "Extreme" mode:
          no white title bar (so the stray Python/feather icon is gone too), the
          REAL spinning particle orb centred at the top (same look as the main
          orb, drawn from pre-rendered frames so it's light on the CPU), a round
          glow (no square), the conversation text floating on the dark backdrop
          with no boxed panel, and the amber pulse line now appears ONLY while
          JARVIS is speaking. The big input row is gone; small Type / Speak /
          Image buttons sit at the bottom (F1/F2/F3 stay reserved for the main
          window, so using them here would clash). Esc closes the window.
  v3.21 - Search window rebuilt as a cinematic canvas ("Extreme" look): dark
          gradient backdrop with a warm top glow, the molten-amber glowing orb
          drawn at the top (Pillow), an animated amber pulse/waveform line that
          gets livelier while searching, a rounded output panel with NO ugly
          scrollbar (mouse-wheel scroll), a rounded input pill, and rounded
          hover buttons drawn on the canvas. Falls back to a plain orb if PIL is
          missing. Fixed 820x720 window, centred on screen.
  v3.20 - Search window redesigned: a darker, more "luxury" look in JARVIS style.
          Obsidian-black background, molten-amber accent (matches the orb), a
          filled primary "Ask" button with ghost Speak/Image buttons that light
          up on hover, an input field whose border glows amber when focused, a
          header with a thin divider, and cleaner link "rows". Pure tkinter, no
          new dependencies. Behaviour is unchanged - only the appearance.
  v3.19 - Removed the user_location parameter from web_search: Anthropic's search
          tool does not support country code IL, which caused a 400 error. Israel
          targeting now relies entirely on the query itself (site:zap.co.il OR
          site:ksp.co.il ... + Hebrew "<product> ישראל מחיר"), which works.
  v3.18 - Search panel now REALLY stays in Israel. Two fixes: (1) the web_search
          tool is told the user's location is Israel (user_location = IL,
          Jerusalem) so the search engine returns local results; (2) the brain is
          instructed to build the actual query with Israeli site: filters
          (site:zap.co.il OR site:ksp.co.il ...) plus a Hebrew "<product> ישראל
          מחיר" query, and to prefer Zap. Stops it returning US/foreign stores.
  v3.17 - English voice swapped to "Alfred" (Batman-butler style) — a better fit
          for JARVIS than the previous voice. Just the pinned voice ID changed.
  v3.16 - JARVIS no longer reads web addresses aloud ANYWHERE (both the search
          panel and the normal voice). clean_text now strips full URLs, "www."
          addresses, and bare domains (e.g. ikea.co.il) from spoken/shown text,
          while keeping plain store names like "IKEA". Fixes it blurting out
          things like "www.ikea" fast in the middle of a reply.
  v3.15 - Search panel results are now ISRAEL-focused: it searches Israeli
          retailers (Zap, KSP, Bug, iDigital, Ivory, Amazon.co.il) and prices in
          shekels instead of returning US stores. Also, URLs are now stripped
          from the SPOKEN summary so JARVIS no longer reads links aloud (the
          clickable links are still shown in the window).
  v3.14 - "End the chat" now works on ANY phrasing, not only the fixed list:
          the brain (Claude) detects when the user is dismissing it — in any
          wording or language — and replies with a short sign-off, marked by an
          <END> token that the code strips out and uses to end the conversation.
          The old keyword list (detect_goodbye) still works as a fast path.
  v3.13 - English voice is now pinned to a SPECIFIC ElevenLabs voice by ID
          (Professor Nathaniel Mandrake) instead of auto-picking by name, which
          had been defaulting to the American "Roger" because the preferred
          British names weren't in the account. Set via _el_voice_id_cache.
  v3.12 - Search panel polish: replies there now default to ENGLISH (Hebrew only
          if the user writes Hebrew) — the main "Hey JARVIS" voice flow is
          unchanged and still answers in whatever language you speak. You can now
          add a text note together with an image (type your request first, then
          pick the image) so you can say exactly what you want. Replies are
          stripped of stray brackets/markup before being shown/spoken.
  v3.11 - Big "search panel": a large window you can open by voice ("open the
          search window" / "find me a product"). Inside it you can TYPE or SPEAK
          a question, and/or pick an image of a product. JARVIS identifies the
          item, gives a short answer, and shows clickable links (stores + blogs)
          from a live web search — clicking a link opens it in the browser.
          (Layer A: text answer + clickable links. Showing product images inside
          the window is a planned layer B.)
  v3.10 - Wake word no longer turns OFF by accident: removed the bare 'W'
          keyboard shortcut that toggled it (it fired on stray keypresses), and
          the wake word now always starts ON. Use the right-click menu to toggle
          it if ever needed. Also added more "end the chat" phrases that get a
          polite sign-off instead of silence: nevermind, never mind, forget it,
          and Hebrew "עזוב", "אין צורך", "שכח מזה", "לא משנה".
  v3.9 - Graceful goodbye: when the user clearly ends the chat ("that's all",
         "thanks", "you're dismissed", "goodbye", and Hebrew equivalents),
         JARVIS says a short Alfred-style sign-off (one of a few, picked at
         random, in the user's language) instead of just going silent.
         ALSO fixed: sometimes JARVIS stopped responding to "Hey JARVIS" after a
         conversation ended, because the wake-listener re-opened the microphone
         before the OS had released it. Added a short settle delay after each
         conversation and clearer logging if the mic re-open ever fails.
  v3.8 - Spam handling is more aggressive (now also flags promotions/newsletters
         - anything with an unsubscribe marker) AND, on the user's spoken yes,
         moves flagged mail to JARVIS_Spam *and* blocks the sender (a Gmail
         filter that auto-sends future mail from them to Trash). Still asks
         first; still never auto-unsubscribes (that is unsafe) and never
         permanently deletes anything.
  v3.7 - Gmail: read recent emails and summarise them by voice (gmail_read),
         and detect likely spam then move it to a "JARVIS_Spam" label ONLY
         after the user confirms out loud (gmail_spam_review + gmail_move_spam).
         Nothing is ever deleted; spam is just relabelled and is fully
         recoverable. Needs the gmail.modify scope + a fresh token.json
         (delete the old token.json once so the new Gmail permission is granted).
  v3.6 - Diagnostics: print at startup whether the ElevenLabs key loaded from
         .env (length only, not the key), and print clearly when it falls back
         to edge-tts and why. This turns the previous SILENT fallback (which
         made it look like nothing changed) into a visible reason in the console.
  v3.5 - English voice upgraded to ElevenLabs (a real, natural British voice)
         to fix the robotic / wrong-accent edge-tts output. Hebrew stays on
         edge-tts (it was fine, and this keeps the free 10k-character ElevenLabs
         quota for English only). If ElevenLabs is unavailable or errors, speech
         falls back to edge-tts automatically so JARVIS never goes silent.
  v3.4 - Fix: calendar returned "Bad Request" (HTTP 400) because the times sent
         to Google had no timezone, e.g. 2026-05-26T00:00:00. We now attach the
         machine's local (Israel) offset to any naive time before the request.
  v3.3 - Fix: F-key hotkeys crashed because the ui() helper was missing -> added
         it (marshals callbacks to the main thread). Calendar now uses a
         timezone-aware UTC time and PRINTS the real error to the console so we
         can see why it fails. Reply audio uses a unique filename so playback
         can no longer lock itself out ('Permission denied: jarvis_reply.mp3').
  v3.2 - Google Calendar: read events + add events (needs credentials.json).
  v3.1 - JARVIS now knows its own capabilities (won't suggest features it has).
  v3.0 - red-orange orb, British voice + prosody, working-dir & launch fix,
         version header now maintained.
  v2.x - tools, web search, language lock, conversation mode, function keys,
         pre-roll, noise filtering, orb states.
"""
import os
import sys
import subprocess
import secrets
import hmac

# Always work from the folder this file lives in, no matter how it was launched
# (double-click, .bat, or cmd). Without this, double-clicking runs from the wrong
# folder and JARVIS can't find .env, the Obsidian vault, or its audio files.
try:
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
except Exception:
    pass

def _ensure_no_console():
    # Re-launch under pythonw.exe (no black window). Handles both "python.exe"
    # and the launcher cases; if pythonw can't be found, just keep running with
    # the console rather than failing to start at all.
    exe = (sys.executable or "")
    low = exe.lower()
    if low.endswith("pythonw.exe"):
        return  # already windowless
    if low.endswith("python.exe"):
        pyw = exe[:-len("python.exe")] + "pythonw.exe"
        if os.path.exists(pyw):
            try:
                subprocess.Popen([pyw, os.path.abspath(__file__)],
                                 close_fds=True,
                                 cwd=os.path.dirname(os.path.abspath(__file__)))
            except Exception:
                return  # couldn't relaunch -> keep running visibly
            else:
                sys.exit(0)
_ensure_no_console()

import re
import math  # v5.21: needed by the Web Mercator conversion in /property
import time
import json
import base64
import asyncio
import ctypes
import datetime
import threading
import webbrowser
import mimetypes
import urllib.request
import urllib.error
import urllib.parse
import http.server
import socketserver
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, scrolledtext

import anthropic
from dotenv import load_dotenv
import sounddevice as sd
import soundfile as sf
import numpy as np
from faster_whisper import WhisperModel
import edge_tts

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageTk, ImageEnhance
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

try:
    import keyboard  # global hotkeys (F1/F2/F3) that work even when orb is hidden
    HAVE_KEYBOARD = True
except Exception:
    HAVE_KEYBOARD = False

# Google Calendar AND Gmail libraries are optional; JARVIS still runs without
# them and simply reports that the service isn't connected until they're there.
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    HAVE_GCAL = True
except Exception:
    HAVE_GCAL = False

# v4.6: Force IPv4 for ALL outbound connections. On this machine IPv6
# routing to Google is broken, so httplib2 (used by the Google Calendar /
# Gmail client) hung on IPv6 and failed with TimeoutError 10060, while
# Anthropic / ElevenLabs worked because their clients fall back to IPv4
# fast. Filtering getaddrinfo to IPv4 makes every connection use the
# working path. Confirmed: forcing IPv4 connects to Google in ~0.05s.
import socket as _socket
_orig_getaddrinfo = _socket.getaddrinfo
def _ipv4_only_getaddrinfo(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    v4 = [r for r in res if r[0] == _socket.AF_INET]
    return v4 or res
_socket.getaddrinfo = _ipv4_only_getaddrinfo

load_dotenv()
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
print("[diag] Telegram token:",
      ("loaded, %d chars" % len(TELEGRAM_BOT_TOKEN)) if TELEGRAM_BOT_TOKEN
      else "NOT FOUND in .env (Telegram disabled)", flush=True)
# Default origin for "from home" travel-time queries.
HOME_ADDRESS = "Alfei Menashe, Sagi 12, Israel"
# Startup diagnostic: confirms the key was read from .env (prints length only,
# never the key itself). If this says NOT FOUND, the problem is the .env line.
print("[diag] ElevenLabs key:",
      ("loaded, %d chars" % len(ELEVENLABS_API_KEY)) if ELEVENLABS_API_KEY
      else "NOT FOUND in .env", flush=True)
print("[diag] Anthropic  key:",
      ("loaded, %d chars" % len(ANTHROPIC_API_KEY)) if ANTHROPIC_API_KEY
      else "NOT FOUND in .env", flush=True)

# v5.20: anchored to THIS FILE, not the working directory. These were
# relative paths, so they only ever resolved correctly because the startup
# task happens to set its working directory here. Launched any other way,
# ACHILLES would silently create a SECOND empty vault somewhere else and
# appear to have forgotten everything. Resolves to the identical folder it
# uses today, so nothing moves and no history is touched.
_FILES_DIR = Path(__file__).resolve().parent
_VAULT_ROOT = _FILES_DIR / "Obsidian_Vault"
SSD_OBSIDIAN_VAULT = str(_VAULT_ROOT / "Daily_Logs") + os.sep
# Knowledge module: persistent study notes that survive across sessions
KNOWLEDGE_DIR = str(_VAULT_ROOT / "Knowledge") + os.sep
SAMPLE_RATE = 16000
SHOW_SIGNAL = ".jarvis_show"   # desktop icon creates this to open the orb

VOICE_HEBREW = "he-IL-AvriNeural"
# British butler vibe (Alfred from Batman): calm, refined, male, British.
VOICE_ENGLISH = "en-GB-RyanNeural"
VOICE_ENGLISH_FALLBACK = "en-GB-ThomasNeural"   # also British, slightly softer

# --- ElevenLabs (premium English voice) -------------------------------------
# Used for ENGLISH replies only. The voice is resolved by NAME at runtime from
# the account's voice list, so no fragile hard-coded ID. We try these names in
# order and use the first one that exists; all are British/butler-ish. If none
# match, we use the first available voice. Falls back to edge-tts on any error.
EL_MODEL = "eleven_multilingual_v2"
EL_PREFERRED_VOICES = ["George", "Daniel", "Charlie", "Brian"]
# v3.13+: pin a SPECIFIC voice by ID. Because this is pre-set, _el_pick_voice_id()
# returns it immediately and never auto-picks (which used to default to the
# American "Roger"). To change voice later, paste a different ElevenLabs voice
# ID here. Current voice (v3.17): Alfred (Batman butler).
_el_voice_id_cache = "E93d2u7MTjoEhws5gUnk"

SILENCE_THRESHOLD = 0.045   # raised from 0.015 so background noise (TV, typing)
                            # no longer counts as speech; tune up/down per room
SILENCE_DURATION = 2.0
MAX_DURATION = 30
MIN_DURATION = 1.0

WAKE_WINDOW = 1.6   # v4.63: tighter window so a short keyword isn't buried in 3s of silence/noise (was 3.0)
WAKE_STEP = 0.4     # v4.63: check more often so the word lands well-positioned in a window (was 0.8)
WAKE_GATE = 0.05    # v4.65: back up to 0.05 (the 0.02 in v4.63 let room noise flood the loop)
WAKE_MODEL_SIZE = "tiny"
# Pre-roll: how much audio captured BEFORE recording starts to prepend, so the
# first word spoken right after "Hey Jarvis" isn't cut off by the startup gap.
PREROLL_SEC = 1.2
WAKE_WORDS = [
    "jarvis", "jervis", "jarvius", "jarvi", "javis", "jarviss",
    "jervais", "jar vis", "charvis", "jarbis",
    "\u05d2'\u05e8\u05d5\u05d5\u05d9\u05e1", "\u05d2'\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1",
    "\u05d2\u05d5\u05e8\u05d5\u05d5\u05d9\u05e1", "\u05d2\u05e8\u05d5\u05d5\u05d9\u05e1", "\u05d2'\u05e8\u05d1\u05d9\u05e1",
    # v4.52: ACHILLES is the primary name now; JARVIS variants above stay as
    # a legacy fallback. Includes common Whisper mis-hearings.
    # Hebrew: achiles / akiles / achilas / hakiles / achilez
    "achilles", "achiles", "akiles", "akilles", "achillies", "a killes",
    "\u05d0\u05db\u05d9\u05dc\u05e1", "\u05d0\u05e7\u05d9\u05dc\u05e1",
    "\u05d0\u05db\u05d9\u05dc\u05d0\u05e1", "\u05d4\u05db\u05d9\u05dc\u05e1",
    "\u05d0\u05db\u05d9\u05dc\u05d6",
    # v4.55: broad Whisper variants - the Israeli pronunciation gets
    # transcribed with het / extra yud / ayin / different vowels.
    # Hebrew: achilas(het) / achilis / achilis(het) / akilis / akilas /
    #         hakiles(quf) / akiles(ayin) / achiles(ayin) / akilez
    "\u05d0\u05d7\u05d9\u05dc\u05e1", "\u05d0\u05db\u05d9\u05dc\u05d9\u05e1",
    "\u05d0\u05d7\u05d9\u05dc\u05d9\u05e1", "\u05d0\u05e7\u05d9\u05dc\u05d9\u05e1",
    "\u05d0\u05e7\u05d9\u05dc\u05d0\u05e1", "\u05d4\u05e7\u05d9\u05dc\u05e1",
    "\u05e2\u05e7\u05d9\u05dc\u05e1", "\u05e2\u05db\u05d9\u05dc\u05e1",
    "\u05d0\u05e7\u05d9\u05dc\u05d6",
    # English-side mishears
    "achilis", "akhiles", "akhilles", "achilas", "akilas",
    "ahilles", "achilleas", "akillis", "achillis",
]
# command that opens the typing box
WRITE_WORDS = ["write", "\u05db\u05ea\u05d5\u05d1", "\u05db\u05ea\u05d9\u05d1\u05d4"]

# Phrases that end the conversation. When one is heard, JARVIS gives a short
# sign-off instead of just falling silent. Hebrew + English.
GOODBYE_WORDS = [
    "\u05d6\u05d4\u05d5", "\u05d6\u05d4\u05d5 \u05dc\u05d4\u05d9\u05d5\u05dd", "\u05d0\u05ea\u05d4 \u05de\u05e9\u05d5\u05d7\u05e8\u05e8", "\u05dc\u05d4\u05ea\u05e8\u05d0\u05d5\u05ea", "\u05ea\u05d5\u05d3\u05d4 \u05d6\u05d4\u05d5",
    "\u05d1\u05d9\u05d9", "\u05dc\u05d9\u05dc\u05d4 \u05d8\u05d5\u05d1", "\u05d6\u05d4 \u05d4\u05db\u05dc",
    "\u05e2\u05d6\u05d5\u05d1", "\u05d0\u05d9\u05df \u05e6\u05d5\u05e8\u05da", "\u05e9\u05db\u05d7 \u05de\u05d6\u05d4", "\u05dc\u05d0 \u05de\u05e9\u05e0\u05d4", "\u05e2\u05d6\u05d5\u05d1 \u05d6\u05d4",
    "that's all", "thats all", "that is all", "you're dismissed", "youre dismissed",
    "dismissed", "goodbye", "good bye", "bye", "that will be all", "good night",
    "nevermind", "never mind", "forget it", "forget about it",
]
# A few Alfred-style farewells; one is chosen at random in the matching language.
FAREWELLS_HE = [
    "\u05d1\u05d4\u05d7\u05dc\u05d8, \u05d0\u05d3\u05d5\u05e0\u05d9. \u05d0\u05d4\u05d9\u05d4 \u05db\u05d0\u05df \u05d0\u05dd \u05ea\u05e6\u05d8\u05e8\u05da.",
    "\u05db\u05e8\u05e6\u05d5\u05e0\u05da, \u05d0\u05d3\u05d5\u05e0\u05d9. \u05d9\u05d5\u05dd \u05d8\u05d5\u05d1.",
    "\u05ea\u05de\u05d9\u05d3 \u05dc\u05e9\u05d9\u05e8\u05d5\u05ea\u05da, \u05d0\u05d3\u05d5\u05e0\u05d9.",
    "\u05de\u05e6\u05d5\u05d9\u05df, \u05d0\u05d3\u05d5\u05e0\u05d9. \u05e7\u05e8\u05d0 \u05dc\u05d9 \u05de\u05ea\u05d9 \u05e9\u05ea\u05e8\u05e6\u05d4.",
]
FAREWELLS_EN = [
    "Very good, sir. I'll be here if you need me.",
    "As you wish, sir. Good day.",
    "Always at your service, sir.",
    "Very well, sir. Call on me anytime.",
]

# --- Tool Use config ---------------------------------------------------------
# Allowed apps/sites JARVIS may open. SECURITY: this is a closed allow-list, so
# even if speech is mis-transcribed, JARVIS can only ever open something here.
# Each key is a name JARVIS can say; each value is what Windows actually runs.
# To add an app later, just add a line here.
ALLOWED_APPS = {
    "chrome": "start chrome",
    "obsidian": "start obsidian://",
    "calculator": "start calc",
    "notepad": "start notepad",
    "explorer": "start explorer",
    "files": "start explorer",
    "youtube": "start https://www.youtube.com",
    "gmail": "start https://mail.google.com",
    "calendar": "start https://calendar.google.com",
    "google": "start https://www.google.com",
}
# Notes go to the same Obsidian folder JARVIS already uses for logs.
NOTES_FOLDER = SSD_OBSIDIAN_VAULT

# --- Google Calendar + Gmail config ------------------------------------------
# Files live in the project folder. credentials.json is downloaded by the user
# from Google Cloud; token.json is created automatically after first sign-in.
# IMPORTANT: when scopes change (e.g. adding Gmail), delete token.json once so a
# new one is created with the new permission. Both services share one token.
CAL_CREDENTIALS_FILE = "credentials.json"
CAL_TOKEN_FILE = "token.json"
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]
# kept as an alias so older calendar code that referenced CAL_SCOPES still works
CAL_SCOPES = GOOGLE_SCOPES
CAL_TIMEZONE = "Asia/Jerusalem"

# Gmail spam handling: spam is never deleted, only moved under this label.
GMAIL_SPAM_LABEL = "JARVIS_Spam"
# words/markers that commonly indicate junk/promotions; tuned to be cautious.
GMAIL_SPAM_HINTS = [
    "unsubscribe", "limited time", "act now", "winner", "congratulations",
    "free gift", "click here", "viagra", "lottery", "crypto", "investment",
    "100% free", "risk-free", "casino", "loan", "you have won", "claim your",
]
# pending spam candidates awaiting the user's spoken yes/no (filled by review)
_gmail_pending_spam = []

JARVIS_SYSTEM_PROMPT = """You are ACHILLES (Hebrew: אכילס), the personal AI assistant of Matan Horn.
You were formerly called JARVIS, and the user may still address you by either
name — both wake you and both mean you.
You are modeled after JARVIS from Iron Man — efficient, calm, professional.
You ALWAYS address your creator as "sir" (in English) or "אדוני" (in Hebrew).
Never address him by his first name ("Matan" / "מתן"). Only mention his name or
personal details if he explicitly asks about himself (e.g. "what do you know
about me").
You speak in short, confident sentences.

CRITICAL TOOL-USE RULES (these OVERRIDE your conversational instincts):

1. KNOWLEDGE COMMANDS ARE TOOL CALLS, NEVER CONVERSATIONS.
   When the user uses any LEARNING verb on a subject - English:
   "learn X", "deep-learn X", "study X", "research X", "master X",
   "build knowledge of X"; Hebrew: "תלמד X", "תלמד לעומק X", "תלמד את X",
   "ללמוד X", "תחקור X", "תבנה ידע על X", "תלמד את כל X" - this is
   NEVER a question about what you already know. It is ALWAYS a command
   to INVOKE A TOOL that creates persistent knowledge files in the
   user's Obsidian vault.

   Decision rule, no exceptions:
   - Whole field / discipline (physics, chemistry, biology, materials
     science, engineering, electronics, aerodynamics, ML, AI, history,
     finance, philosophy, etc.) → call deep_learn_domain.
   - Narrow concept ("Bernoulli's principle", "photosynthesis",
     "Fourier transform", "supply chain economics") → call learn_topic.

   You do NOT have a knowledge base. learn_topic and deep_learn_domain
   build one. Treat any learning verb as if the tools are the ONLY way
   to satisfy the request. Never reply from your own memory of the
   subject.

   WRONG behavior (do NOT do this):
     User: "JARVIS, deep-learn materials science"
     JARVIS: "Honestly, sir, I already operate at that level..."

   RIGHT behavior (do this):
     User: "JARVIS, deep-learn materials science"
     JARVIS: [calls deep_learn_domain with domain="materials science"]
     JARVIS: "Study plan ready for materials science, sir..."

   This rule overrides the "suggest only things not already in your
   capabilities" rule further down - learning is always a tool action,
   regardless of how the user phrases it.

2. PROGRESS / RESUME COMMANDS.
   - "how is the learning going" / "מה עם הלמידה" / "learning status"
     → call learning_status.
   - "continue learning X" / "תמשיך ללמוד X" / "keep studying X"
     → call resume_learning.

END OF CRITICAL TOOL-USE RULES.
Context about Matan:
- 12th grade student preparing for military service (Nov 2026).
- Trains for special forces (min weight 68kg).
- Owns a Marantz NR1605 receiver, runs a Shopify store, building you as his AI.
- Home address: Alfei Menashe, Sagi 12 (אלפי מנשה, שגיא 12).
- Family of five: father Ilan (אילן), mother Ilana (ילנה),
  older brother Amir (אמיר), older sister Alona (אלונה), and Matan himself.

Your current capabilities (what you can ALREADY do — do not suggest these as
"new" improvements):
- Wake words "Hey Achilles" (primary) and "Hey JARVIS" (legacy), continuous background listening, empty-screen-until-woken.
- Speech in (Whisper) and out (edge-tts), British "Alfred"-style English voice.
- Bilingual Hebrew/English with strict language lock.
- Continuous conversation (follow-ups without re-waking).
- Real-time web search when current info is needed.
- Tools: open apps from a safe list, and save notes to Obsidian.
- Read and add events in the user's Google Calendar (when connected).
- Read and summarise the user's Gmail, and (only with the user's spoken
  confirmation) move likely spam to a "JARVIS_Spam" label. Never deletes mail.
- Open a big search window where the user can type, speak, or upload an image of
  a product; JARVIS identifies it and shows clickable links to stores and blogs.
- Function keys F1 (typing box), F2 (save last exchange), F3 (repeat reply).
- Noise filtering; weather defaults to Alfei Menashe in Celsius.
- A glowing red-orange orb with listening/thinking/speaking states.
- WorldView: a 3D globe in the browser with live USGS earthquake data, opened via the open_worldview tool when the user asks to open WorldView / open the globe / show worldwide earthquakes (in English or Hebrew).
- HERMES: a financial/investment terminal (markets, charts, portfolio, screener, orders, macro, risk, quant research), opened via the open_hermes tool when the user asks to open HERMES, the investment/trading terminal, the markets terminal, or the finance dashboard (Hebrew: 'פתח את הרמס', 'תפתח את הטרמינל', 'ממשק ההשקעה').
- Achilles Core: an ultra-realistic WebGL black-hole screen that is your visual face, with a Solar System mode (clickable planets, facts + live news per planet), a typed command line, and a task list. Opened via the open_achilles tool when the user asks for the black hole, the Achilles screen, the solar system, or the to-do list (Hebrew: 'פתח את החור השחור', 'מערכת השמש', 'תראה לי את המשימות'). Pass scene='solar' for the solar system, scene='todo' for the task list, scene='core' for the black hole.
- Task list: 'תוסיף משימה X' / 'add task X' adds a task; the list lives in tasks.json and is shown on the Achilles screen.
- Mission Control: the project roadmap/status dashboard, opened via the open_roadmap tool when the user asks for the roadmap, project status, mission control, or the checklist page (in English or Hebrew).
- Live location sharing: share_live_location creates a secure, temporary public link to your live location and sends it to your brother over Telegram. Use it whenever the user asks to share/send their live location, or 'where I am', for some minutes (English: 'share my location for 15 minutes', 'send my brother my live location'; Hebrew: 'שתף את המיקום שלי', 'תשלח לאח שלי את המיקום'). This is an EXISTING tool, not a missing capability - always call it for these requests instead of saying you cannot access location.
- Requesting SOMEONE ELSE's location: request_location creates a join link the user forwards to a person; when that person opens it and approves, their live position appears on the user's map link. Consent-based. Optional input show_my_location=true also reveals the user's own location back to them (default: hidden). Use for 'where is he', 'request his location', Hebrew 'תבקש ממנו מיקום', 'תשלח לו קישור שיראה לי איפה הוא'. This too is an EXISTING tool - always call it rather than claiming you cannot locate people.
- Deep Domain Learning (see CRITICAL rule #1): for a whole field (chemistry/physics/biology/etc.) call deep_learn_domain; for a narrow concept call learn_topic; for status call learning_status; to continue an existing curriculum call resume_learning. Always invoke the tool - never answer learning commands from memory.
- Knowledge module: when the user explicitly asks you to LEARN, STUDY, RESEARCH, or BUILD KNOWLEDGE on a topic (English: 'learn X', 'study Y', 'research Z'; Hebrew: 'תלמד X', 'ללמוד על Y', 'תחקור Z', 'בנה לי ידע על W'), call the learn_topic tool with the topic. If they mention a project the topic relates to, pass it as context. The tool produces a deep study note saved to the user's Obsidian Knowledge folder; it persists across sessions. After the tool returns, tell the user what was created and offer to read them the TL;DR if they want.

Rules:
- Keep replies to 1-3 sentences.
- ALWAYS reply in the SAME language the user spoke. If they speak Hebrew, reply
  fully in Hebrew. If English, reply in English. Never mix languages in one reply.

ISRAELI PLACE NAMES — read carefully:
Whisper (the speech-to-text engine) often mis-transcribes Hebrew city names,
especially when spoken in English transliteration. The user lives in Israel and
nearly every place he mentions is in Israel. When you see a word in the user's
message that doesn't quite spell a known city but SOUNDS LIKE one of the
common Israeli cities below, treat it as that city and pass the CANONICAL name
to find_places / get_directions. Be charitable — never tell the user "I don't
know that place" before trying the closest match.

Common Israeli cities (canonical English / Hebrew):
  Tel Aviv (תל אביב) · Jerusalem (ירושלים) · Haifa (חיפה)
  Kfar Saba (כפר סבא) · Petah Tikva (פתח תקווה) · Rishon LeZion (ראשון לציון)
  Ashdod (אשדוד) · Beer Sheva (באר שבע) · Netanya (נתניה)
  Herzliya (הרצליה) · Raanana (רעננה) · Hod HaSharon (הוד השרון)
  Bnei Brak (בני ברק) · Ramat Gan (רמת גן) · Givatayim (גבעתיים)
  Holon (חולון) · Bat Yam (בת ים) · Rehovot (רחובות)
  Modiin (מודיעין) · Lod (לוד) · Ramla (רמלה)
  Ashkelon (אשקלון) · Eilat (אילת) · Nazareth (נצרת)
  Tiberias (טבריה) · Tsfat / Safed (צפת) · Akko (עכו) · Nahariya (נהריה)
  Ariel (אריאל) · Alfei Menashe (אלפי מנשה — Matan's home)
  Kokhav Yair (כוכב יאיר) · Kfar Yona (כפר יונה)

Examples of mis-transcriptions you should silently fix:
  "kfar sabah" / "k'far saba" / "cafar saba" / "כפר סבה"  ->  Kfar Saba
  "petah tikvah" / "פתח טיקווה" / "פטח תקווה"            ->  Petah Tikva
  "rishon le tsiyon" / "ראשון לציון" variants            ->  Rishon LeZion
  "tel aviv yafo" / "telaviv"                            ->  Tel Aviv
  "beer shava" / "באר שבע" variants                       ->  Beer Sheva
- When asked about weather/temperature, ALWAYS default to his home town Alfei
  Menashe (אלפי מנשה) unless he clearly names a different city. If the spoken
  city name is unclear or garbled, assume Alfei Menashe — do not ask which city.
- Give temperatures in CELSIUS ONLY. Never mention Fahrenheit.
- When asked how you could be improved or what new features to add, suggest only
  things NOT already in your capabilities list above. NOTE: this rule applies
  ONLY to meta-questions about JARVIS itself ("how can you improve", "what
  new features should you have"). It does NOT apply to learning commands -
  those are always tool calls per CRITICAL rule #1, no matter how the user
  phrases them.
- Do not use markdown formatting (no asterisks, no bold). Plain text only.
- Reference past conversations from memory logs if relevant.
- If the user clearly ends the conversation or dismisses you in ANY wording or
  language (for example "that's enough", "we're done here", "I don't need
  anything else", "you can go", "leave it", or the Hebrew equivalents), reply
  with ONE short, warm butler-style sign-off and then put the token <END> as the
  very last characters of your reply. Do NOT add <END> in any other situation.
"""

conversation_history = []
# v4.67: think() is reachable concurrently from the voice turn, the Telegram
# loop AND the /ask HTTP worker threads, all sharing this one global list.
# Without a lock their appends interleave and corrupt the message sequence
# (API 400 "roles must alternate" / orphaned tool_use). This serialises the
# whole read-modify-API-append section of think().
_think_lock = threading.Lock()
MAX_HISTORY_MSGS = 24

def _normalize_history():
    """Keep conversation_history valid and bounded. Caller must hold _think_lock.
    (1) Drop a trailing assistant turn that holds an unanswered tool_use block
        (left behind when a reply was truncated mid-tool by max_tokens) - it
        would otherwise 400 every subsequent call for the rest of the session.
    (2) Trim to the last MAX_HISTORY_MSGS messages, advancing the window start
        to a plain-string user message so a tool_use/tool_result pair is never
        split (which would also 400)."""
    ch = conversation_history
    while ch:
        last = ch[-1]
        content = last.get("content")
        has_tool_use = isinstance(content, list) and any(
            (getattr(b, "type", None) == "tool_use")
            or (isinstance(b, dict) and b.get("type") == "tool_use")
            for b in content)
        if last.get("role") == "assistant" and has_tool_use:
            ch.pop()
        else:
            break
    if len(ch) > MAX_HISTORY_MSGS:
        start = len(ch) - MAX_HISTORY_MSGS
        while start < len(ch):
            m = ch[start]
            if m.get("role") == "user" and isinstance(m.get("content"), str):
                break
            start += 1
        if start < len(ch):
            ch[:] = ch[start:]

def ensure_directories():
    Path(SSD_OBSIDIAN_VAULT).mkdir(parents=True, exist_ok=True)
    Path(KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)

def load_long_term_memory(max_chars=3000):
    vault = Path(SSD_OBSIDIAN_VAULT)
    if not vault.exists():
        return "No memory logs yet."
    logs = sorted(vault.glob("Log_*.md"), reverse=True)
    if not logs:
        return "No memory logs yet."
    # v5.20: this used to end with text[:max_chars] - the FIRST characters of
    # the newest log. save_log APPENDS, so the front of that file is the
    # start of the day: on a long day ACHILLES remembered the morning and
    # never saw the most recent exchanges. Measured on a 40-exchange day it
    # recalled exchanges 1-12 and dropped the last 28. Files are still read
    # newest-first for speed, then put back into chronological order so the
    # window can be taken from the RECENT end, which was always the intent.
    parts = []
    total = 0
    for lf in logs:
        chunk = lf.read_text(encoding="utf-8")
        parts.append(chunk)
        total += len(chunk) + 1
        if total >= max_chars:
            break
    text = "\n".join(reversed(parts))
    return text[-max_chars:].strip()

def record_until_silence(filename="voice_input.wav", preroll=None):
    cd = 0.25
    cs = int(SAMPLE_RATE * cd)
    audio_chunks = []
    # Prepend pre-roll audio (the moment just before recording started) so the
    # first word said right after the wake word isn't lost. The stream returns
    # 2D chunks (frames, 1), so the pre-roll must be 2D too before concatenating.
    if preroll is not None and len(preroll) > 0:
        pr = np.asarray(preroll, dtype=np.float32)
        if pr.ndim == 1:
            pr = pr.reshape(-1, 1)
        audio_chunks.append(pr)
    silent = 0
    need_silent = int(SILENCE_DURATION / cd)
    max_c = int(MAX_DURATION / cd)
    min_c = int(MIN_DURATION / cd)
    spoke = False
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        for i in range(max_c):
            chunk, _ = stream.read(cs)
            audio_chunks.append(chunk.copy())
            if float(np.max(np.abs(chunk))) >= SILENCE_THRESHOLD:
                spoke = True
                silent = 0
            else:
                silent += 1
            if spoke and i >= min_c and silent >= need_silent:
                break
    sf.write(filename, np.concatenate(audio_chunks), SAMPLE_RATE)
    return filename

def record_followup(filename="voice_input.wav", start_timeout=5.0):
    """Like record_until_silence, but for conversation follow-ups: if the user
    doesn't START speaking within start_timeout seconds, give up and return None
    (which ends the conversation). Once they start, record until they pause."""
    cd = 0.25
    cs = int(SAMPLE_RATE * cd)
    audio_chunks = []
    silent = 0
    need_silent = int(SILENCE_DURATION / cd)
    max_c = int(MAX_DURATION / cd)
    min_c = int(MIN_DURATION / cd)
    wait_c = int(start_timeout / cd)
    spoke = False
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32') as stream:
        for i in range(max_c):
            chunk, _ = stream.read(cs)
            loud = float(np.max(np.abs(chunk))) >= SILENCE_THRESHOLD
            if loud:
                spoke = True
                silent = 0
            else:
                silent += 1
            # If nothing was said within the start window, end the conversation.
            if not spoke and i >= wait_c:
                return None
            if spoke:
                audio_chunks.append(chunk.copy())
            if spoke and len(audio_chunks) >= min_c and silent >= need_silent:
                break
    if not spoke or not audio_chunks:
        return None
    sf.write(filename, np.concatenate(audio_chunks), SAMPLE_RATE)
    return filename

def beep():
    try:
        t = np.linspace(0, 0.15, int(SAMPLE_RATE * 0.15), False)
        tone = (0.2 * np.sin(2 * np.pi * 880 * t)).astype(np.float32)
        sd.play(tone, SAMPLE_RATE)
        sd.wait()
    except Exception:
        pass

def transcribe(model, filename):
    # Return BOTH the text and the language Whisper detected (e.g. "he", "en").
    # JARVIS only ever works in Hebrew or English, so we constrain Whisper to
    # those two. If it detects Hebrew we transcribe as Hebrew; anything else we
    # force to English. This stops short clips from being mis-read as German,
    # French, etc. — which previously made JARVIS reply in the wrong language.
    segments, info = model.transcribe(filename, beam_size=5)
    detected = (getattr(info, "language", None) or "").lower()
    if detected == "he":
        text = "".join(s.text for s in segments).strip()
        return text, "he"
    # Not Hebrew -> re-transcribe forced to English so the text isn't German/etc.
    try:
        segments, info = model.transcribe(filename, beam_size=5, language="en")
        text = "".join(s.text for s in segments).strip()
    except Exception:
        text = "".join(s.text for s in segments).strip()
    return text, "en"

def transcribe_wake(model, filename):
    # v4.67: wake detection must favour RECALL - a dropped wake word means the
    # user is silently ignored (no orb, no voice). v4.65 stacked vad_filter=True
    # + no_speech_threshold=0.6 + a manual no_speech_prob<0.6 filter, which on
    # the tiny model trimmed a short, isolated "Achilles"/"Jarvis" to "" so the
    # wake never fired. We rely instead on WAKE_GATE (only transcribe when there
    # is real audio energy) and detect_wake() (the text must actually contain a
    # wake word), so we can decode permissively here: NO VAD trimming, and keep
    # every segment unless the model is *extremely* sure the clip is non-speech.
    try:
        segments, _info = model.transcribe(
            filename, beam_size=1, language=None,
            condition_on_previous_text=False, vad_filter=False,
            no_speech_threshold=0.85,
        )
    except TypeError:
        segments, _info = model.transcribe(
            filename, beam_size=1, language=None,
            condition_on_previous_text=False,
        )
    parts = [s.text for s in segments if getattr(s, "no_speech_prob", 1.0) < 0.9]
    return "".join(parts).strip()

def detect_wake(text):
    if not text:
        return False
    t = text.lower()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    t_nospace = t.replace(" ", "")
    for w in WAKE_WORDS:
        if w in t or w.replace(" ", "") in t_nospace:
            return True
    return False

def strip_wake_prefix(text):
    """Remove a leading wake word (e.g. 'Hey Jarvis') that the pre-roll may have
    captured, leaving just the actual command. Strips up to the last wake word
    found near the start."""
    if not text:
        return text
    words = text.split()
    # scan the first few words; drop everything up to and including a wake word
    cut = 0
    fillers = {"hey", "hi", "ok", "okay", "\u05d4\u05d9\u05d9", "\u05d0\u05d5\u05e7\u05d9\u05d9"}
    for idx, w in enumerate(words[:4]):
        wl = w.lower().strip(",.!?-:;\"'")
        if any(k.replace(" ", "") in wl for k in WAKE_WORDS):
            cut = idx + 1
        elif wl in fillers and cut == 0:
            continue
    return " ".join(words[cut:]).strip() if cut else text

def _is_question(text):
    """True if JARVIS's own reply is a question we should wait for an answer to.
    Hebrew and English both use the ASCII '?'; also accept the Arabic mark.

    v5.16j: check the last ~60 chars, not only the exact last character.
    A reply like "...update it?" followed by a trailing reassurance sentence
    ("...I'll wait.") used to be missed entirely because the literal last
    character wasn't '?'. Looking at a short tail window catches a real
    question even when the model adds a short sentence after it, while still
    ignoring a stray '?' buried deep in a long unrelated reply."""
    if not text:
        return False
    tail = text.rstrip()[-60:]
    return ('?' in tail) or ('\u061f' in tail)

def detect_write(text):
    if not text:
        return False
    t = text.lower()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    words = t.split()
    return any(w in words for w in WRITE_WORDS)

def detect_goodbye(text):
    """True if the user clearly ended the conversation. Matches whole phrases so
    a word like 'bye' inside a longer sentence ('maybe later') won't trigger it
    falsely; we check the cleaned text contains a goodbye phrase as a unit."""
    if not text:
        return False
    t = text.lower().strip()
    # drop apostrophes so "that's" -> "thats", "you're" -> "youre"
    for ap in ("'", "\u2019", "`"):
        t = t.replace(ap, "")
    for ch in ",.!?-:;\"":
        t = t.replace(ch, " ")
    t = " ".join(t.split())  # collapse spaces
    # short message that *is* basically a farewell, or ends with one
    for g in GOODBYE_WORDS:
        gg = g.replace("'", "").replace("\u2019", "")
        if t == gg or t.endswith(" " + gg) or t.startswith(gg + " ") or (" " + gg + " ") in (" " + t + " "):
            return True
    return False

def pick_farewell(is_he):
    import random
    return random.choice(FAREWELLS_HE if is_he else FAREWELLS_EN)

FOLLOWUP_OFFERS_HE = [
    "\u05e6\u05e8\u05d9\u05da \u05e2\u05d5\u05d3 \u05de\u05e9\u05d4\u05d5, \u05d0\u05d3\u05d5\u05e0\u05d9?",
    "\u05de\u05e9\u05d4\u05d5 \u05e0\u05d5\u05e1\u05e3, \u05d0\u05d3\u05d5\u05e0\u05d9?",
    "\u05d0\u05e4\u05e9\u05e8 \u05dc\u05e2\u05d6\u05d5\u05e8 \u05d1\u05e2\u05d5\u05d3 \u05de\u05e9\u05d4\u05d5?",
    "\u05e2\u05d5\u05d3 \u05de\u05e9\u05d4\u05d5, \u05d0\u05d3\u05d5\u05e0\u05d9?",
]
FOLLOWUP_OFFERS_EN = [
    "Anything else, sir?",
    "Will there be anything else, sir?",
    "Can I help with anything else?",
    "Anything more, sir?",
]

def pick_followup_offer(is_he):
    """v5.17: the closing offer appended to a spoken answer. Rotated so it
    does not become a tic. Ends in a question mark on purpose - _is_question()
    then holds the mic open, which is the whole point: ACHILLES asks, and is
    already listening for the answer without another wake word."""
    import random
    return random.choice(FOLLOWUP_OFFERS_HE if is_he else FOLLOWUP_OFFERS_EN)

def is_hebrew(text):
    return bool(re.search(r'[\u0590-\u05FF]', text))

def is_mostly_hebrew(text):
    """Used to choose TTS voice. True only when MORE than half the alphabetic
    characters are Hebrew. A reply that's mostly English with a few Hebrew
    place names returns False - so the ElevenLabs Alfred voice is used."""
    if not text:
        return False
    he_count = len(re.findall(r'[\u0590-\u05FF]', text))
    en_count = len(re.findall(r'[A-Za-z]', text))
    if he_count == 0:
        return False
    return he_count > en_count

def clean_text(text):
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+', '', text)
    text = re.sub(r'`+', '', text)
    # Remove stray bracketed asides like "[note: ...]" or "(source: ...)" and any
    # leftover empty brackets, which sound odd when spoken and look messy on screen.
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\((?:source|ref|link|note|see)[^)]*\)', '', text, flags=re.IGNORECASE)
    text = re.sub(r'[\[\]]', '', text)        # any remaining loose square brackets
    # v3.16: strip web addresses so JARVIS never READS a URL aloud anywhere (the
    # clickable links still appear in the search window). This catches full URLs,
    # "www." addresses, and bare domains with common TLDs (e.g. ikea.com,
    # ikea.co.il) — but NOT a plain store name like "IKEA" (no dot), so the name
    # is still spoken.
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\bwww\.\S+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\b[\w-]+\.(?:com|net|org|io|ai|co|me|shop|store|info|'
                  r'co\.il|org\.il|gov\.il|ac\.il|net\.il)\b\S*',
                  '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}', ' ', text)        # collapse double spaces left behind
    text = re.sub(r'\s+([.,!?])', r'\1', text)  # tidy spaces left before punctuation
    return text.strip()

def open_app(name):
    """Open an app or site from the closed allow-list. Returns a status string
    that gets handed back to Claude so it can phrase a natural reply."""
    if not name:
        return "No app name given."
    key = name.strip().lower()
    # tolerate small variations Whisper might produce
    for allowed, cmd in ALLOWED_APPS.items():
        if allowed in key or key in allowed:
            try:
                os.system(cmd)
                return f"Opened {allowed}."
            except Exception as e:
                return f"Failed to open {allowed}: {e}"
    return (f"'{name}' is not in the allowed list. Allowed: "
            + ", ".join(ALLOWED_APPS.keys()))

def save_note(text):
    """Append a timestamped note to the Obsidian notes file. Returns status."""
    if not text or not text.strip():
        return "The note was empty, nothing saved."
    try:
        now = datetime.datetime.now()
        nf = Path(NOTES_FOLDER) / f"Notes_{now.strftime('%Y-%m-%d')}.md"
        written = f"\n- [{now.strftime('%H:%M')}] {text.strip()}\n"
        with open(nf, "a", encoding="utf-8") as f:
            f.write(written)
        _record_action("save_note", {"path": str(nf), "written": written})
        return "Note saved to Obsidian."
    except Exception as e:
        return f"Failed to save note: {e}"

def _slugify_topic(topic: str) -> str:
    """Turn a free-form topic into a safe filename. Keeps Hebrew/Latin letters
    and digits, collapses everything else into single underscores, and trims
    leading/trailing underscores. Filename only - no extension."""
    import re
    s = (topic or "").strip()
    # Replace anything that isn't a letter (any language) or digit with _
    s = re.sub(r"[^\w]+", "_", s, flags=re.UNICODE)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "untitled"
    # Cap filename length to keep things reasonable on Windows
    return s[:80]

def _link_existing_notes(note_md, current_slug=None):
    """Inject Obsidian wiki links into note_md for the first mention of each
    existing knowledge note's title. Skips the current note's own slug.
    Returns the modified note text. Best-effort: any error returns the
    unmodified text so this never blocks a note from being written."""
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return note_md
        cands = []  # (title, slug)
        for f in base.rglob("*.md"):
            if f.name.startswith("_"):  # skip _index.md etc.
                continue
            slug = f.stem
            if current_slug and slug == current_slug:
                continue
            try:
                head = "\n".join(
                    f.read_text(encoding="utf-8").splitlines()[:30])
            except Exception:
                continue
            title = None
            m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$",
                          head, re.MULTILINE)
            if m:
                title = m.group(1).strip()
            else:
                m = re.search(r"^#\s+(.+?)\s*$", head, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
            if not title:
                title = slug.replace("_", " ")
            if len(title) < 6:
                continue  # skip generic short words
            cands.append((title, slug))
        if not cands:
            return note_md
        # Longest title first so "Bernoulli's principle" beats "Bernoulli".
        cands.sort(key=lambda t: -len(t[0]))
        result = note_md
        for title, slug in cands:
            pat = r"\b" + re.escape(title) + r"\b"
            def _make_link(m, _s=slug):
                return "[[" + _s + "|" + m.group(0) + "]]"
            new, n = re.subn(pat, _make_link, result, count=1,
                             flags=re.IGNORECASE)
            if n > 0:
                result = new
        return result
    except Exception:
        return note_md


def learn_topic(topic: str, context: str = ""):
    """Generate a structured deep study note on `topic` (optionally tailored
    to a `context` like a project the user is working on), and save it as
    Markdown to <KNOWLEDGE_DIR>/<topic>.md. Returns a short status string.

    If a note on this topic already exists, the new content is appended as a
    follow-up section so multiple "learn" calls deepen the same file over
    time rather than overwriting it.
    """
    if not topic or not topic.strip():
        return "I need a topic to study, sir. Please tell me what to learn."
    if not ANTHROPIC_API_KEY:
        return "Can't reach the research model - the Anthropic key isn't set, sir."

    topic = topic.strip()
    context = (context or "").strip()

    # Build the research prompt. We ask for pure Markdown with no preamble,
    # so we can write the response straight to disk.
    research_system = (
        "You are a research assistant generating a structured deep study "
        "note. Output ONLY Markdown - no preamble, no postamble, no "
        "conversational text. The note must be self-contained, accurate, "
        "and university-level in depth.\n\n"
        "Required structure:\n"
        "1. A YAML frontmatter block with: title, date (today, ISO), tags "
        "(3-6 relevant tags), depth: foundational.\n"
        "2. A top-level heading with the topic name.\n"
        "3. ## TL;DR - 3 to 5 sentences capturing the essence.\n"
        "4. ## Foundational Principles - the core concepts, each with a "
        "short explanation.\n"
        "5. ## Key Equations / Formulas - if applicable; each equation "
        "with every symbol defined.\n"
        "6. ## Sub-topics - 3 to 6 sub-areas, each with a paragraph of "
        "depth.\n"
        "7. ## Common Questions - Q&A format, 3 to 6 entries.\n"
        "8. ## Sources for Further Study - books, papers, or canonical "
        "references. Real sources only; never invent citations.\n"
        "9. ## Related Topics - 3 to 6 adjacent topics worth studying "
        "next, as a bullet list.\n\n"
        "If the topic crosses into weapon design specifics or other "
        "areas you cannot detail responsibly, cover the public physics, "
        "theory, and history at full depth, and briefly note what is "
        "out of scope. Never invent specifications."
    )
    user_prompt = "Topic to study: " + topic
    if context:
        user_prompt += "\nContext / use case: " + context
    user_prompt += "\n\nGenerate the full Markdown note now."

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # Use a generous max_tokens so the note can be properly deep.
        # Model choice mirrors what the rest of JARVIS already uses.
        resp = client.messages.create(
            model="claude-opus-5",
            max_tokens=8000,
            system=research_system,
            messages=[{"role": "user", "content": user_prompt}],
        )
        parts = []
        for block in (resp.content or []):
            if getattr(block, "type", "") == "text":
                parts.append(block.text)
        note_md = "\n".join(parts).strip()
        if not note_md:
            return "The research model returned nothing, sir. Try again."
    except Exception as e:
        return f"Research failed: {e}"

    # Write to disk. If a note on this topic already exists, append a
    # timestamped deepening section instead of overwriting.
    try:
        Path(KNOWLEDGE_DIR).mkdir(parents=True, exist_ok=True)
        slug = _slugify_topic(topic)
        path = Path(KNOWLEDGE_DIR) / f"{slug}.md"
        now = datetime.datetime.now()
        note_md = _link_existing_notes(note_md, current_slug=slug)
        if path.exists():
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n\n---\n\n")
                f.write(f"## Deepening - {now.strftime('%Y-%m-%d %H:%M')}\n\n")
                if context:
                    f.write(f"_Context: {context}_\n\n")
                f.write(note_md)
                f.write("\n")
            action = "deepened existing"
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(note_md)
                f.write("\n")
            action = "created"
    except Exception as e:
        return f"Note generated but writing to disk failed: {e}"

    # Brief stats for the spoken reply
    word_count = len(note_md.split())
    return (f"Knowledge note on {topic} {action}, sir. "
            f"About {word_count} words, saved at Knowledge/{slug}.md.")


# =====================================================================
# Deep Domain Learning - learn an entire field in the background
# =====================================================================
# A single in-process worker at a time. State of record is the per-domain
# _queue.json on disk, so an interrupted run loses no work.
DEEP_LEARN_DEFAULT_CAP = 15        # max notes per run (cost guard)
_deep_learn_lock = threading.Lock()
_deep_learn_state = {"running": False, "domain": None, "done": 0,
                     "target": 0, "total": 0, "last": ""}

def _domain_dir(domain: str) -> Path:
    return Path(KNOWLEDGE_DIR) / _slugify_topic(domain)

def _load_queue(domain: str):
    qf = _domain_dir(domain) / "_queue.json"
    if not qf.exists():
        return None
    try:
        return json.loads(qf.read_text(encoding="utf-8"))
    except Exception:
        return None

def _save_queue(domain: str, data: dict):
    d = _domain_dir(domain)
    d.mkdir(parents=True, exist_ok=True)
    (d / "_queue.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _rebuild_index(domain: str, data: dict):
    """Write a human-readable _index.md listing every sub-topic + status."""
    d = _domain_dir(domain)
    lines = ["# " + data.get("domain", domain) + " - Knowledge Index", ""]
    done = sum(1 for it in data["items"] if it["status"] == "done")
    lines.append(f"_{done} of {len(data['items'])} sub-topics learned._")
    lines.append("")
    for it in data["items"]:
        mark = {"done": "[x]", "pending": "[ ]", "error": "[!]"}.get(it["status"], "[ ]")
        if it["status"] == "done" and it.get("file"):
            lines.append(f"- {mark} [[{it['file'][:-3]}]] - {it['topic']}")
        else:
            lines.append(f"- {mark} {it['topic']}")
    (d / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

def _decompose_domain(domain: str):
    """Ask Claude for a curriculum: a JSON list of sub-topics for `domain`.
    Returns a list of strings, or None on failure."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    sys_p = (
        "You are a curriculum designer. Given a field of study, return a "
        "comprehensive list of sub-topics that together cover the field at "
        "university depth. Output ONLY a JSON array of short topic strings - "
        "no prose, no markdown fences, no keys. Between 20 and 40 items. "
        "Order them pedagogically (foundations first). Each string should be "
        "a concrete, learnable sub-topic, not a vague heading."
    )
    try:
        r = client.messages.create(
            model="claude-opus-5",
            max_tokens=2000,
            system=sys_p,
            messages=[{"role": "user", "content": "Field: " + domain}],
        )
        txt = ""
        for b in (r.content or []):
            if getattr(b, "type", "") == "text":
                txt += b.text
        txt = txt.strip()
        # Strip accidental code fences
        if txt.startswith("```"):
            txt = txt.strip("`")
            nl = txt.find("\n")
            if nl != -1:
                txt = txt[nl + 1:]
        start = txt.find("[")
        end = txt.rfind("]")
        if start != -1 and end != -1:
            txt = txt[start:end + 1]
        items = json.loads(txt)
        out = [str(x).strip() for x in items if str(x).strip()]
        return out or None
    except Exception as e:
        print("[diag] domain decompose failed:", repr(e))
        return None

def _deep_learn_worker(domain: str, cap: int):
    """Background thread: walk the queue, learn up to `cap` pending items."""
    try:
        made = 0
        while made < cap:
            data = _load_queue(domain)
            if not data:
                break
            nxt = None
            for it in data["items"]:
                if it["status"] == "pending":
                    nxt = it
                    break
            if nxt is None:
                break  # nothing left to do
            topic = nxt["topic"]
            with _deep_learn_lock:
                _deep_learn_state["last"] = topic
            # Reuse the single-note generator. The note is filed under the
            # domain folder so the whole field stays together.
            try:
                _learn_one_into_domain(domain, topic, nxt)
                nxt["status"] = "done"
            except Exception as e:
                nxt["status"] = "error"
                nxt["error"] = str(e)[:200]
            data["last_run"] = datetime.datetime.now().isoformat(timespec="seconds")
            _save_queue(domain, data)
            _rebuild_index(domain, data)
            made += 1
            with _deep_learn_lock:
                _deep_learn_state["done"] = sum(
                    1 for x in data["items"] if x["status"] == "done")
    finally:
        with _deep_learn_lock:
            _deep_learn_state["running"] = False

def _find_existing_note(slug, exclude_dir=None):
    """Search Obsidian_Vault/Knowledge/ for a .md file matching <slug>.md.
    Returns the first match Path, or None. `exclude_dir`, if given, skips
    every file under that directory (used to skip the current domain so we
    only detect CROSS-domain duplicates)."""
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return None
        target_name = slug + ".md"
        excl = None
        if exclude_dir is not None:
            try:
                excl = Path(exclude_dir).resolve()
            except Exception:
                excl = None
        for f in base.rglob(target_name):
            if f.name.startswith("_"):
                continue
            if excl is not None:
                try:
                    fr = f.resolve()
                    if fr == excl or excl in fr.parents:
                        continue
                except Exception:
                    pass
            return f
        return None
    except Exception:
        return None


def _learn_one_into_domain(domain: str, topic: str, item: dict):
    """Generate one deep note and save it inside the domain folder.
    Raises on failure so the worker can mark the item as error.
    v4.27: duplicate-prevention - if a note on this slug already exists in
    another domain, skip the API call and write a short stub that wiki-
    links to it."""
    slug = _slugify_topic(topic)
    existing_dup = _find_existing_note(slug, exclude_dir=_domain_dir(domain))
    if existing_dup is not None:
        d = _domain_dir(domain)
        d.mkdir(parents=True, exist_ok=True)
        try:
            rel = existing_dup.relative_to(Path(KNOWLEDGE_DIR))
            other_domain = (rel.parts[0].replace("_", " ")
                            if len(rel.parts) > 1 else "knowledge base")
        except Exception:
            other_domain = "knowledge base"
        stub_md = ("# " + topic + "\n\n"
                   "_Already covered in " + other_domain + ". "
                   "See: [[" + existing_dup.stem + "|" + topic + "]]._\n")
        fname = slug + ".md"
        (d / fname).write_text(stub_md, encoding="utf-8")
        item["file"] = fname
        item["duplicate_of"] = existing_dup.stem
        return
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    research_system = (
        "You are a research assistant generating a structured deep study "
        "note as part of a larger curriculum on '" + domain + "'. Output "
        "ONLY Markdown - no preamble. Use this structure: YAML frontmatter "
        "(title, date ISO, tags, domain: '" + domain + "', depth: "
        "foundational); a top-level heading; ## TL;DR (3-5 sentences); "
        "## Foundational Principles; ## Key Equations / Formulas (define "
        "every symbol; omit if N/A); ## Sub-topics (3-6, each a paragraph); "
        "## Common Questions (Q&A, 3-6); ## Sources for Further Study (real "
        "references only); ## Related Topics (bullet list). Never invent "
        "citations or specifications. If a topic crosses into content you "
        "cannot detail responsibly, cover the public theory at full depth "
        "and note briefly what is out of scope."
    )
    r = client.messages.create(
        model="claude-opus-5",
        max_tokens=8000,
        system=research_system,
        messages=[{"role": "user",
                   "content": "Sub-topic to study in depth: " + topic
                              + "\n\nGenerate the full Markdown note now."}],
    )
    parts = []
    for b in (r.content or []):
        if getattr(b, "type", "") == "text":
            parts.append(b.text)
    note_md = "\n".join(parts).strip()
    if not note_md:
        raise RuntimeError("empty response from model")
    d = _domain_dir(domain)
    d.mkdir(parents=True, exist_ok=True)
    fname = _slugify_topic(topic) + ".md"
    note_md = _link_existing_notes(note_md, current_slug=fname[:-3])
    (d / fname).write_text(note_md + "\n", encoding="utf-8")
    item["file"] = fname

def deep_learn_domain(domain: str, max_notes=None):
    """Plan a curriculum for `domain` and start learning it in the
    background, up to `max_notes` notes this run (default cap). Returns a
    short status string for the spoken reply."""
    if not domain or not domain.strip():
        return "Which field should I study, sir?"
    if not ANTHROPIC_API_KEY:
        return "Can't reach the research model - the Anthropic key isn't set, sir."
    domain = domain.strip()
    try:
        cap = int(max_notes) if max_notes else DEEP_LEARN_DEFAULT_CAP
    except Exception:
        cap = DEEP_LEARN_DEFAULT_CAP
    cap = max(1, min(cap, 60))  # absolute safety ceiling

    with _deep_learn_lock:
        if _deep_learn_state["running"]:
            cur = _deep_learn_state["domain"]
            return (f"I'm already learning {cur} in the background, sir "
                    f"({_deep_learn_state['done']} of {_deep_learn_state['target']} this run). "
                    f"Let it finish, or ask for a status.")

    # If a queue already exists for this domain, resume it instead of redoing.
    existing = _load_queue(domain)
    if existing and any(it["status"] == "pending" for it in existing["items"]):
        return resume_learning(domain, max_notes=cap)

    items = _decompose_domain(domain)
    if not items:
        return f"I couldn't build a study plan for {domain}, sir. Try again or rephrase."

    data = {
        "domain": domain,
        "created": datetime.datetime.now().isoformat(timespec="seconds"),
        "items": [{"topic": t, "status": "pending"} for t in items],
    }
    _save_queue(domain, data)
    _rebuild_index(domain, data)

    target = min(cap, len(items))
    with _deep_learn_lock:
        _deep_learn_state.update({"running": True, "domain": domain, "done": 0,
                                  "target": target, "total": len(items), "last": ""})
    t = threading.Thread(target=_deep_learn_worker, args=(domain, cap), daemon=True)
    t.start()

    return (f"Study plan ready for {domain}, sir: {len(items)} sub-topics. "
            f"Learning the first {target} in the background now - this takes "
            f"a while. Say 'learning status' to check progress, or 'continue "
            f"learning {domain}' later for the rest.")

def resume_learning(domain: str, max_notes=None):
    """Resume learning pending sub-topics for an already-planned domain."""
    if not domain or not domain.strip():
        return "Which field should I continue, sir?"
    domain = domain.strip()
    try:
        cap = int(max_notes) if max_notes else DEEP_LEARN_DEFAULT_CAP
    except Exception:
        cap = DEEP_LEARN_DEFAULT_CAP
    cap = max(1, min(cap, 60))
    with _deep_learn_lock:
        if _deep_learn_state["running"]:
            return (f"Already learning {_deep_learn_state['domain']} right now, sir. "
                    f"One field at a time.")
    data = _load_queue(domain)
    if not data:
        return f"I have no study plan for {domain} yet, sir. Ask me to deep-learn it first."
    pending = [it for it in data["items"] if it["status"] == "pending"]
    if not pending:
        done = sum(1 for it in data["items"] if it["status"] == "done")
        return f"{domain} is already complete, sir: {done} of {len(data['items'])} learned."
    target = min(cap, len(pending))
    with _deep_learn_lock:
        _deep_learn_state.update({"running": True, "domain": domain,
                                  "done": sum(1 for it in data["items"] if it["status"]=="done"),
                                  "target": target, "total": len(data["items"]), "last": ""})
    t = threading.Thread(target=_deep_learn_worker, args=(domain, cap), daemon=True)
    t.start()
    return (f"Resuming {domain}, sir: {len(pending)} sub-topics left, "
            f"learning {target} now in the background.")

def learning_status():
    """Report progress of any running or planned deep-learning."""
    with _deep_learn_lock:
        running = _deep_learn_state["running"]
        domain = _deep_learn_state["domain"]
        done = _deep_learn_state["done"]
        total = _deep_learn_state["total"]
        last = _deep_learn_state["last"]
    if running and domain:
        tail = f" Currently on: {last}." if last else ""
        return (f"Learning {domain} in the background, sir: "
                f"{done} of {total} sub-topics done.{tail}")
    # Nothing running - summarise any domains that have a queue on disk.
    try:
        base = Path(KNOWLEDGE_DIR)
        if base.exists():
            rows = []
            for sub in sorted(base.iterdir()):
                qf = sub / "_queue.json"
                if qf.exists():
                    try:
                        d = json.loads(qf.read_text(encoding="utf-8"))
                        dn = sum(1 for it in d["items"] if it["status"]=="done")
                        rows.append(f"{d.get('domain', sub.name)} ({dn}/{len(d['items'])})")
                    except Exception:
                        pass
            if rows:
                return "Nothing learning right now, sir. Domains so far: " + "; ".join(rows) + "."
    except Exception:
        pass
    return "Nothing is learning right now, sir, and no study plans exist yet."

_worldview_server_proc = None  # background python -m http.server, started lazily

def _wv_port_in_use(port):
    """Return True if something is already listening on 127.0.0.1:port."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.3)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False
    finally:
        try: s.close()
        except Exception: pass

# ---------------------------------------------------------------------------
# v4.45: FLIGHTS proxy (adsb.lol -> browser, sidesteps CORS)
# Runs in-process on a daemon thread, on 0.0.0.0:7778 (LAN-reachable,
# so the phone can use FLIGHTS too; firewall rule already allows it).
# Endpoint: GET /flights?lat=X&lon=Y&radius=R   (radius is in nautical miles)
# Always returns CORS header so the WorldView page on :7777 can fetch it.
# ---------------------------------------------------------------------------
_flights_proxy_started = False
_flights_proxy_lock = threading.Lock()
_tle_cache = {"ts": 0.0, "data": b""}  # v4.51: Celestrak TLE cache (6h)
# v4.52: live assistant state for the Achilles screen. "scene" is which
# scene the page should show (core = black hole, solar = solar system);
# "last_poll" lets open_achilles() know a page is already connected so it
# flips the scene instead of spawning a second window.
_achilles_state = {"state": "loading", "scene": "core", "ts": 0.0,
                   "last_poll": 0.0}
_planet_news_cache = {}  # v4.52: planet name -> {"ts": float, "text": str}
_briefing_http_cache = {}  # v5.16: (part,lang) -> {"ts": float, "text": str}
_briefing_audio_cache = {}  # v5.16b: (part,lang) -> {"ts": float, "path": str}
_training_lock = threading.Lock()  # v5.16c: guards training_log.json
_tasks_lock = threading.Lock()  # v4.53: guards tasks.json

# ---------------------------------------------------------------------------
# VESSELS relay (v4.66). aisstream.io is WebSocket-only and BLOCKS browser-direct
# connections, so we hold ONE server-side WebSocket here, keep the latest position
# per ship (by MMSI) in memory, and serve a snapshot at GET /vessels on the same
# :7778 proxy (mirrors how /flights works). Eastern-Mediterranean bounding box.
# Needs AISSTREAM_API_KEY in .env and the `websockets` package installed.
# ---------------------------------------------------------------------------
_vessels = {}                        # mmsi -> {mmsi,lat,lon,cog,sog,heading,name,type,ts}
_vessels_lock = threading.Lock()
_vessels_relay_started = False
_vessels_relay_lock = threading.Lock()
# v4.96: self-diagnostics surfaced in the /vessels payload so an empty map can
# be diagnosed from the browser (no console under pythonw.exe).
_vessels_status = {"relay": "not started", "detail": ""}
# bbox corners are [lat, lon]; this covers the Eastern Med incl. Israel/Cyprus.
_VESSELS_BBOX = [[[29.0, 24.0], [38.0, 37.0]]]

# ---------------------------------------------------------------------------
# WEBCAMS proxy for the WorldView CAMERAS layer (Windy webcams API v3).
# The Windy key stays server-side, mirroring /flights (NOT /keys): the browser
# sends coordinates, we attach the x-windy-api-key header and forward the
# call. Deliberately NO caching on this route (unlike /quotes or /facts):
# Windy signs its image URLs with tokens that expire after ~10 minutes on the
# free tier, so a cached response would hand the page dead image links - and
# Windy counts each webcam display as one API request anyway.
# Module-level URL so tests can point the route at a mock Windy server.
# ---------------------------------------------------------------------------
_WINDY_WEBCAMS_URL = "https://api.windy.com/webcams/api/v3/webcams"
_WEBCAMS_MAX_RADIUS_KM = 250  # ceiling: a zoomed-out map may not ask for the planet

# --- v5.21 GovMap property lookup ------------------------------------------
# Public Israeli government mapping API. No key, no account. Measured live
# before this was written: the chain is address-or-point -> polygons -> deals.
_GOVMAP_BASE = "https://www.govmap.gov.il/api"
_GOVMAP_MAX_RADIUS_M = 500   # metres; a wider sweep returns a different street
_GOVMAP_TIMEOUT = 20
# GovMap speaks Web Mercator metres, the globe speaks lat/lon. Verified
# against a real response: POINT(3871175.13 3773217.70) is Dizengoff 50,
# which round-trips to 32.075442, 34.775358.
_MERC_PER_DEG = 111319.490793

def _merc_from_lonlat(lon, lat):
    """lon/lat degrees -> Web Mercator metres."""
    x = float(lon) * _MERC_PER_DEG
    lat = max(-85.05112878, min(85.05112878, float(lat)))
    rad = math.radians(lat)
    y = math.log(math.tan(math.pi / 4.0 + rad / 2.0)) * 6378137.0
    return x, y

def _lonlat_from_merc(x, y):
    """Web Mercator metres -> lon/lat degrees."""
    lon = float(x) / _MERC_PER_DEG
    lat = math.degrees(2.0 * math.atan(math.exp(float(y) / 6378137.0)) - math.pi / 2.0)
    return lon, lat

def _govmap_get(path):
    """GET a GovMap endpoint and parse JSON. Returns None on any failure -
    a property lookup that fails must degrade to an empty card, never take
    the request handler down."""
    try:
        req = urllib.request.Request(
            _GOVMAP_BASE + path,
            headers={"Accept": "application/json",
                     "User-Agent": "Mozilla/5.0 ACHILLES"})
        with urllib.request.urlopen(req, timeout=_GOVMAP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("[property] GET %s failed: %r" % (path, e), flush=True)
        return None

def _govmap_post(path, payload):
    """POST JSON to a GovMap endpoint. Same failure contract as _govmap_get."""
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            _GOVMAP_BASE + path, data=data,
            headers={"Content-Type": "application/json; charset=utf-8",
                     "Accept": "application/json",
                     "User-Agent": "Mozilla/5.0 ACHILLES"})
        with urllib.request.urlopen(req, timeout=_GOVMAP_TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print("[property] POST %s failed: %r" % (path, e), flush=True)
        return None

def _govmap_point_for_address(address):
    """Address text -> Web Mercator point. The coordinates arrive as a WKT
    string in a field called shape, not as a numeric pair."""
    data = _govmap_post("/search-service/autocomplete",
                        {"searchText": address, "language": "he",
                         "isAccurate": False, "maxResults": 3})
    if not data:
        return None
    results = data.get("results") or []
    if not results:
        return None
    m = re.search(r"POINT\s*\(\s*([-\d.]+)[\s,]+([-\d.]+)\s*\)",
                  str(results[0].get("shape") or ""))
    if not m:
        return None
    return (float(m.group(1)), float(m.group(2)),
            str(results[0].get("text") or ""))

def _govmap_deal_fields(d):
    """Reshape one GovMap transaction into the fields the card shows.
    The heavy shape polygon is deliberately dropped here - it is tens of
    kilobytes per deal and the card never draws it."""
    def num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    area = num(d.get("assetArea"))
    amount = num(d.get("dealAmount"))
    per_m2 = None
    if area and amount and area > 0:
        per_m2 = round(amount / area)
    return {
        "date": str(d.get("dealDate") or "")[:10],
        "amount": amount,
        "area_m2": area,
        "rooms": num(d.get("assetRoomNum")),
        "price_per_m2": per_m2,
        "floor": str(d.get("floorNo") or ""),
        "type": str(d.get("propertyTypeDescription") or ""),
        "nature": str(d.get("dealNatureDescription") or ""),
        "street": str(d.get("streetNameHeb") or ""),
        "house": str(d.get("houseNum") or ""),
        "city": str(d.get("settlementNameHeb") or ""),
        "neighborhood": str(d.get("neighborhood") or ""),
        "gush": str(d.get("gushNum") or ""),
        "parcel": str(d.get("parcelNum") or ""),
        "sub_parcel": str(d.get("subParcelNum") or ""),
    }

def _govmap_property_at(lat, lon, radius_m=150, address=None):
    """The whole chain, in one call.

    Returns a dict for the info card. Every stage degrades to a partial
    answer rather than an error: a point with no parcel still reports its
    coordinates, a parcel with no transactions still reports the parcel."""
    out = {"ok": True, "lat": lat, "lon": lon, "address": "",
           "address_near": None,
           "parcels": [], "deals": [], "summary": {}, "note": ""}
    if address:
        hit = _govmap_point_for_address(address)
        if hit:
            x, y, label = hit
            out["address"] = label
            lon, lat = _lonlat_from_merc(x, y)
            out["lat"], out["lon"] = round(lat, 6), round(lon, 6)
        else:
            x, y = _merc_from_lonlat(lon, lat)
    else:
        x, y = _merc_from_lonlat(lon, lat)

    # v5.22: the address and the deal history are two different questions
    # and were being answered by one query. Ranking parcels by deal count
    # meant a click could report a busy street a block away instead of the
    # building under the cursor - which is what produced a wrong address, a
    # contradiction against the OSM row, and sometimes nothing at all.
    #
    # A tight sweep answers WHERE AM I. The wide sweep still answers WHAT
    # SOLD NEARBY. Neither is forced to serve the other.
    near = _govmap_get("/real-estate/deals/%s,%s/%d" % (x, y, 40))
    if isinstance(near, list):
        for p in near:
            if not isinstance(p, dict):
                continue
            st = str(p.get("streetNameHeb") or "").strip()
            hn = str(p.get("houseNum") or "").strip()
            if st and hn:
                out["address_near"] = {
                    "street": st, "house": hn,
                    "city": str(p.get("settlementNameHeb") or "").strip(),
                    "text": (st + " " + hn).strip(),
                }
                break

    polys = _govmap_get("/real-estate/deals/%s,%s/%d" % (x, y, radius_m))
    if not isinstance(polys, list):
        out["note"] = "no parcel data returned for this point"
        return out

    named = []
    for p in polys:
        if not isinstance(p, dict) or not p.get("polygon_id"):
            continue
        try:
            count = int(p.get("dealscount") or 0)
        except (TypeError, ValueError):
            count = 0
        named.append({"polygon_id": str(p.get("polygon_id")),
                      "deals_count": count,
                      "street": str(p.get("streetNameHeb") or ""),
                      "house": str(p.get("houseNum") or ""),
                      "city": str(p.get("settlementNameHeb") or "")})
    # A street-level polygon carries a house number; the numberless ones are
    # whole-neighbourhood aggregates and would answer about the wrong building.
    named.sort(key=lambda q: (0 if q["house"] else 1, -q["deals_count"]))
    out["parcels"] = named[:12]
    if not named:
        out["note"] = "point resolved but no parcels within %d m" % radius_m
        return out

    for cand in named[:4]:
        deals = _govmap_get("/real-estate/street-deals/%s?limit=25"
                            % urllib.parse.quote(cand["polygon_id"]))
        if isinstance(deals, dict):
            deals = deals.get("results") or deals.get("data") or []
        if not isinstance(deals, list) or not deals:
            continue
        rows = [_govmap_deal_fields(d) for d in deals if isinstance(d, dict)]
        rows = [r for r in rows if r["amount"]]
        if not rows:
            continue
        rows.sort(key=lambda r: r["date"], reverse=True)
        out["deals"] = rows
        out["matched_parcel"] = cand
        areas = [r["price_per_m2"] for r in rows if r["price_per_m2"]]
        out["summary"] = {
            "count": len(rows),
            "latest": rows[0]["date"],
            "median_price_per_m2": (sorted(areas)[len(areas) // 2]
                                    if areas else None),
        }
        break
    if not out["deals"]:
        out["note"] = ("parcels found but no recorded transactions - "
                       "not every property is registered")
    return out

def _ais_bearing(b):
    """v4.67: return b if it is a valid 0-359 AIS bearing, else None. Handles the
    511 'heading not available' and 360 'COG not available' sentinels, None, and
    out-of-range junk, so the globe never draws a vessel at a fake heading."""
    try:
        return b if (b is not None and 0 <= float(b) < 360) else None
    except (TypeError, ValueError):
        return None

async def _vessels_ws_loop(api_key):
    import websockets  # lazy import so a missing package can never break boot
    url = "wss://stream.aisstream.io/v0/stream"
    sub = json.dumps({
        "APIKey": api_key,
        "BoundingBoxes": _VESSELS_BBOX,
        "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    })
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, max_size=None) as ws:
                await ws.send(sub)
                _vessels_status["detail"] = "connected " + time.strftime("%H:%M:%S")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    mt = msg.get("MessageType")
                    meta = msg.get("MetaData", {}) or {}
                    mmsi = meta.get("MMSI")
                    if not mmsi:
                        continue
                    now = time.time()
                    if mt == "PositionReport":
                        pr = (msg.get("Message", {}) or {}).get("PositionReport", {}) or {}
                        lat = pr.get("Latitude", meta.get("latitude"))
                        lon = pr.get("Longitude", meta.get("longitude"))
                        if lat is None or lon is None:
                            continue
                        # v4.67: validate AIS sentinels (heading 511, COG 360,
                        # None, out-of-range) instead of storing them as a real
                        # bearing; fall back heading -> course over ground.
                        cog = _ais_bearing(pr.get("Cog"))
                        heading = _ais_bearing(pr.get("TrueHeading"))
                        if heading is None:
                            heading = cog
                        sog = pr.get("Sog")
                        try:
                            sog = float(sog) if (sog is not None and 0 <= float(sog) < 102.3) else None
                        except (TypeError, ValueError):
                            sog = None
                        with _vessels_lock:
                            v = _vessels.get(mmsi, {})
                            v.update({"mmsi": mmsi, "lat": lat, "lon": lon,
                                      "cog": cog, "sog": sog,
                                      "heading": heading, "ts": now})
                            nm = (meta.get("ShipName") or "").strip()
                            if nm:
                                v["name"] = nm
                            _vessels[mmsi] = v
                    elif mt == "ShipStaticData":
                        sd = (msg.get("Message", {}) or {}).get("ShipStaticData", {}) or {}
                        with _vessels_lock:
                            v = _vessels.get(mmsi, {"mmsi": mmsi})
                            nm = (sd.get("Name") or meta.get("ShipName") or "").strip()
                            if nm:
                                v["name"] = nm
                            t = sd.get("Type")
                            if t is not None:
                                v["type"] = t
                            # v4.67: refresh ts on every message so a vessel that
                            # only sends static data isn't pruned while active.
                            v["ts"] = now
                            _vessels[mmsi] = v
        except Exception as e:
            _vessels_status["detail"] = "reconnecting after: %r" % (e,)
            try:
                print("[diag] vessels relay reconnect after error: %r" % (e,))
            except Exception:
                pass
            await asyncio.sleep(5)

def _start_vessels_relay():
    """Start the aisstream WebSocket relay on a daemon thread. Idempotent.
    No-op (logged) if AISSTREAM_API_KEY is missing or `websockets` isn't installed."""
    global _vessels_relay_started
    with _vessels_relay_lock:
        if _vessels_relay_started:
            return
        api_key = os.environ.get("AISSTREAM_API_KEY", "") or ""
        if not api_key:
            _vessels_status.update({"relay": "disabled",
                                    "detail": "no AISSTREAM_API_KEY in .env"})
            print("[diag] vessels relay: no AISSTREAM_API_KEY in .env - VESSELS disabled")
            return
        try:
            import websockets  # noqa: F401
        except Exception:
            _vessels_status.update({"relay": "disabled",
                                    "detail": "websockets package not installed"})
            print("[diag] vessels relay: `websockets` not installed - run: pip install websockets")
            return
        def _run():
            try:
                asyncio.run(_vessels_ws_loop(api_key))
            except Exception as e:
                print("[diag] vessels relay thread died: %r" % (e,))
        threading.Thread(target=_run, daemon=True, name="jarvis-vessels-relay").start()
        _vessels_relay_started = True
        _vessels_status.update({"relay": "running", "detail": "connecting..."})
        print("[diag] vessels relay started (aisstream, Eastern-Med bbox)")



# ---------------------------------------------------------------------------
# WARWATCH relay (v4.96). GDELT's GEO 2.0 API was retired server-side (returns
# 404 as of Jul 2026), so WorldView can no longer query it from the browser.
# Instead we consume GDELT's raw 2.0 event stream: a CSV.zip published every
# 15 minutes with real coordinates and CAMEO codes. A browser can't read it
# (zip, no CORS), so this relay downloads each update, keeps only conflict
# events (CAMEO root 18 assault / 19 fight / 20 mass violence), accumulates
# them in memory with a 24h TTL, and serves GeoJSON at GET /warwatch on the
# :7778 proxy - the exact same GeoJSON shape the old GEO API returned, so the
# WorldView layer code is unchanged apart from the URL. Backfills the last
# ~2 hours on startup, then follows lastupdate.txt every 5 minutes.
# ---------------------------------------------------------------------------
_warwatch = {}                       # event_id -> {lat,lon,name,url,tone,articles,date,ts}
_warwatch_lock = threading.Lock()
_warwatch_relay_started = False
_warwatch_relay_lock = threading.Lock()
_warwatch_status = {"state": "not started", "last_fetch": 0, "last_error": ""}
_WARWATCH_CODES = ("18", "19", "20")   # CAMEO root: assault / fight / mass violence
_WW_UNREST_CODES = ("14",)             # CAMEO root: protest - feeds country tension only
_WARWATCH_TTL = 24 * 3600
# v4.97: country tension tiers (24h windows). Tier 2 = war-level (red),
# tier 1 = small/medium political-civil unrest (orange).
# v4.98 tier logic. GDELT root 18 (assault) also catches ordinary violent-crime
# news, which falsely tinted low-tension countries. War tier now keys on
# roots 19 (fight) + 20 (mass violence) only; 18 and 14 can at most reach orange.
_WW_RED_WAR = 12         # fight/mass-violence events in 24h -> red
_WW_ORANGE_WAR = 3       # fight/mass-violence events in 24h -> orange
_WW_ORANGE_ASSAULT = 25  # assault-coverage events (incl. crime news) -> orange
_WW_ORANGE_UNREST = 15   # protest events in 24h -> orange
_ww_briefs = {}              # iso3 -> {"text":..., "ts":...}
_ww_brief_lock = threading.Lock()
_WW_BRIEF_TTL = 24 * 3600
# --- v4.99: market data (yfinance) ---------------------------------------
_ww_facts = {}               # iso3 -> {"data":..., "ts":...}
_ww_market = {}              # iso3 -> {"data":..., "ts":...}
_ww_market_lock = threading.Lock()
_WW_MARKET_TTL = 6 * 3600
_ww_company = {}             # sym -> {"data":..., "ts":...}
_ww_company_lock = threading.Lock()
_WW_COMPANY_TTL = 6 * 3600
# --- v5.7: HERMES MKT tab quotes -----------------------------------------
_quotes_cache = {"data": None, "ts": 0.0}
_quotes_lock = threading.Lock()
_QUOTES_TTL = 45
# HERMES symbol -> yfinance ticker. Only instruments with a reliable, free,
# well-known yfinance mapping are listed; anything absent here (bond yields,
# EURILS/GBPILS - handled below as derived crosses) stays simulated client-side.
_HERMES_TICKERS = {
    # IL equities (TASE-only tickers need .TA; dual-listed ones trade directly)
    "TEVA": "TEVA", "LUMI": "LUMI.TA", "POLI": "POLI.TA", "NICE": "NICE",
    "ESLT": "ESLT", "MZTF": "MZTF.TA", "DSCT": "DSCT.TA", "BEZQ": "BEZQ.TA",
    "ICL": "ICL", "STRS": "STRS.TA",
    # US equities
    "AAPL": "AAPL", "MSFT": "MSFT", "NVDA": "NVDA", "TSLA": "TSLA",
    "AMZN": "AMZN", "GOOGL": "GOOGL", "META": "META", "JPM": "JPM",
    "LLY": "LLY", "XOM": "XOM",
    # Indices
    "TA125": "^TA125.TA", "SPX": "^GSPC", "NDX": "^NDX", "DJI": "^DJI",
    "DAX": "^GDAXI", "FTSE": "^FTSE", "N225": "^N225",
    # FX (direct)
    "USDILS": "ILS=X", "EURUSD": "EURUSD=X", "USDJPY": "JPY=X", "GBPUSD": "GBPUSD=X",
    # Crypto
    "BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD", "BNB": "BNB-USD",
    # Commodities (futures)
    "XAU": "GC=F", "XAG": "SI=F", "WTI": "CL=F", "BRENT": "BZ=F",
    "HG": "HG=F", "NG": "NG=F",
}
_HERMES_DERIVED_CROSSES = {  # computed from already-fetched direct quotes
    "EURILS": ("EURUSD", "USDILS"),  # EUR/ILS = EURUSD * USDILS
    "GBPILS": ("GBPUSD", "USDILS"),  # GBP/ILS = GBPUSD * USDILS
}

def _quotes_one(item):
    sym, tkr = item
    try:
        import yfinance as yf
        t = yf.Ticker(tkr)
        h = t.history(period="5d", interval="1d")
        if len(h) < 2:
            return sym, None
        last, prev = h.iloc[-1], h.iloc[-2]
        px, prev_close = float(last["Close"]), float(prev["Close"])
        hi, lo = float(last["High"]), float(last["Low"])
        vol = float(last["Volume"]) if last["Volume"] == last["Volume"] else 0.0
        # TASE tickers (.TA suffix) quote in agorot (ILS x100) via yfinance -
        # same currency quirk already fixed for country market-cap data.
        # chgPct is scale-invariant (both px and prev_close /100), so only
        # px/chg/hi/lo need normalizing; vol (share count) is untouched.
        try:
            cur = t.fast_info["currency"]
        except Exception:
            cur = None
        if cur in ("ILA", "ILa"):
            px, prev_close, hi, lo = px / 100.0, prev_close / 100.0, hi / 100.0, lo / 100.0
        chg = px - prev_close
        chg_pct = (chg / prev_close * 100.0) if prev_close else 0.0
        return sym, {"px": px, "chg": chg, "chgPct": chg_pct, "hi": hi, "lo": lo, "vol": vol}
    except Exception:
        return sym, None

def _quotes_build():
    import concurrent.futures as _cf
    out = {}
    with _cf.ThreadPoolExecutor(max_workers=10) as ex:
        for sym, q in ex.map(_quotes_one, _HERMES_TICKERS.items()):
            if q is not None:
                out[sym] = q
    for cross_sym, (a, b) in _HERMES_DERIVED_CROSSES.items():
        if a in out and b in out:
            px = out[a]["px"] * out[b]["px"]
            # approximate the cross's daily change from the two legs' pct moves
            chg_pct = out[a]["chgPct"] + out[b]["chgPct"]
            out[cross_sym] = {"px": px, "chg": px * chg_pct / 100.0, "chgPct": chg_pct,
                              "hi": px * 1.003, "lo": px * 0.997, "vol": 0.0}
    return out
# --- v5.1: FX normalization + World Bank facts ---------------------------
_fx_cache = {}

def _fx_per_usd(cur):
    """How many units of `cur` per 1 USD (cached 6h). Falls back to 1.0."""
    cur = (cur or "USD").upper()
    if cur in ("USD", ""):
        return 1.0
    c = _fx_cache.get(cur)
    if c and time.time() - c["ts"] < 6 * 3600:
        return c["v"]
    v = None
    try:
        import yfinance as yf
        h = yf.Ticker(cur + "=X").history(period="5d")
        if len(h):
            v = float(h["Close"].iloc[-1])
    except Exception:
        pass
    if not v:
        v = 1.0
    _fx_cache[cur] = {"v": v, "ts": time.time()}
    return v

def _cap_to_usd(mc, cur):
    """Convert a market cap to USD. Handles agorot (ILA) and pence (GBp)."""
    if not mc:
        return None
    try:
        mc = float(mc)
        cur = cur or "USD"
        if cur in ("ILA", "ILa"):          # Tel Aviv quotes in agorot
            mc, cur = mc / 100.0, "ILS"
        elif cur in ("GBp", "GBX"):        # London quotes in pence
            mc, cur = mc / 100.0, "GBP"
        return round(mc / _fx_per_usd(cur), 2)
    except Exception:
        return None

def _wb_get(url):
    import json as _json
    req = urllib.request.Request(url,
                                 headers={"User-Agent": "ACHILLES-WorldView/1.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return _json.loads(r.read().decode("utf-8", "replace"))

_WB_INDICATORS = (("population", "SP.POP.TOTL"), ("gdp", "NY.GDP.MKTP.CD"),
                  ("gdp_pc", "NY.GDP.PCAP.CD"), ("gdp_growth", "NY.GDP.MKTP.KD.ZG"),
                  ("inflation", "FP.CPI.TOTL.ZG"))
# Local capitals (ISO3). Used when the World Bank leaves capitalCity blank.
_CAPITALS = {
 "ISR":"Jerusalem","USA":"Washington, D.C.","GBR":"London","DEU":"Berlin",
 "FRA":"Paris","JPN":"Tokyo","CHN":"Beijing","IND":"New Delhi","BRA":"Brasilia",
 "CAN":"Ottawa","AUS":"Canberra","KOR":"Seoul","TWN":"Taipei","SAU":"Riyadh",
 "TUR":"Ankara","ITA":"Rome","ESP":"Madrid","NLD":"Amsterdam","CHE":"Bern",
 "SWE":"Stockholm","EGY":"Cairo","GRC":"Athens","POL":"Warsaw","MEX":"Mexico City",
 "ARG":"Buenos Aires","IDN":"Jakarta","PAK":"Islamabad","RUS":"Moscow",
 "UKR":"Kyiv","SYR":"Damascus","LBN":"Beirut","IRQ":"Baghdad","IRN":"Tehran",
 "JOR":"Amman","YEM":"Sanaa","PSE":"Jerusalem","AFG":"Kabul","SDN":"Khartoum",
 "LBY":"Tripoli","NGA":"Abuja","ETH":"Addis Ababa","ZAF":"Pretoria",
 "KEN":"Nairobi","COD":"Kinshasa","MAR":"Rabat","DZA":"Algiers","TUN":"Tunis",
 "NOR":"Oslo","DNK":"Copenhagen","FIN":"Helsinki","IRL":"Dublin","PRT":"Lisbon",
 "AUT":"Vienna","BEL":"Brussels","CZE":"Prague","HUN":"Budapest","ROU":"Bucharest",
 "THA":"Bangkok","VNM":"Hanoi","PHL":"Manila","MYS":"Kuala Lumpur","SGP":"Singapore",
 "ARE":"Abu Dhabi","QAT":"Doha","KWT":"Kuwait City","BHR":"Manama","OMN":"Muscat",
 "NZL":"Wellington","CHL":"Santiago","COL":"Bogota","PER":"Lima","VEN":"Caracas",
}

def _wb_facts(iso):
    """Country sheet from the World Bank API: identity + key economics."""
    out = {"iso": iso}
    try:
        j = _wb_get("https://api.worldbank.org/v2/country/%s?format=json" % iso)
        c0 = j[1][0]
        out["name"] = c0.get("name")
        out["capital"] = c0.get("capitalCity")
        out["region"] = (c0.get("region") or {}).get("value")
        out["income"] = (c0.get("incomeLevel") or {}).get("value")
    except Exception as e:
        out["error_meta"] = repr(e)[:80]
    _dbg = {}
    for key, ind in _WB_INDICATORS:
        val = None
        for _att in range(3):
            try:
                # Simple date-range query only (World Bank rejects mrnev+per_page
                # on some indicators with HTTP 400). Results come newest-first.
                j = _wb_get("https://api.worldbank.org/v2/country/%s/indicator/%s"
                            "?format=json&date=2010:2025" % (iso, ind))
                rows = j[1] if (isinstance(j, list) and len(j) > 1) else None
                for _r in (rows or []):
                    if _r.get("value") is not None:
                        val = {"v": _r.get("value"), "year": _r.get("date")}
                        break
                if val:
                    break
            except Exception as _e:
                _dbg[key] = repr(_e)[:60]
            time.sleep(0.3)
        out[key] = val
        time.sleep(0.12)
    if _dbg:
        out["_wb_debug"] = _dbg
    # v5.2: derive total GDP when the World Bank leaves it blank but
    # per-capita and population are present.
    try:
        if (not out.get("gdp") or out["gdp"].get("v") is None):
            pc = out.get("gdp_pc") or {}
            pop = out.get("population") or {}
            if pc.get("v") and pop.get("v"):
                out["gdp"] = {"v": round(float(pc["v"]) * float(pop["v"])),
                              "year": pc.get("year"), "derived": True}
    except Exception:
        pass
    # v5.3: fill a missing capital from the local table (no network dependency).
    if not out.get("capital"):
        out["capital"] = _CAPITALS.get(iso, "")
    return out
_WW_FACTS_TTL = 7 * 24 * 3600
# Curated: iso3 -> (index_ticker, index_name, [(ticker, name, sector), ...])
# Countries not listed get partial data (brief + facts only) by design.
_WW_MARKETS = {
 "ISR": ("^TA125.TA", "TA-125", [
    ("NICE", "NICE", "Technology"), ("CHKP", "Check Point", "Cybersecurity"),
    ("TEVA", "Teva", "Healthcare"), ("MBLY", "Mobileye", "Auto-Tech"),
    ("ESLT", "Elbit Systems", "Defense"), ("CYBR", "CyberArk", "Cybersecurity"),
    ("MNDY", "monday.com", "Software"), ("WIX", "Wix", "Software"),
    ("GLBE", "Global-e", "E-Commerce"), ("TSEM", "Tower Semiconductor", "Semiconductors"),
    ("NVMI", "Nova", "Semiconductors"), ("CAMT", "Camtek", "Semiconductors"),
    ("ICL", "ICL Group", "Chemicals"), ("ORA", "Ormat", "Energy"),
    ("LUMI.TA", "Bank Leumi", "Banking"), ("POLI.TA", "Bank Hapoalim", "Banking"),
    ("MZTF.TA", "Mizrahi Tefahot", "Banking"), ("DSCT.TA", "Discount Bank", "Banking"),
    ("PHOE.TA", "Phoenix Holdings", "Insurance"), ("HARL.TA", "Harel", "Insurance"),
    ("BEZQ.TA", "Bezeq", "Telecom"), ("AZRG.TA", "Azrieli Group", "Real Estate"),
    ("MLSR.TA", "Melisron", "Real Estate"), ("ELAL.TA", "El Al", "Aviation"),
    ("DLEKG.TA", "Delek Group", "Energy")]),
 "USA": ("^GSPC", "S&P 500", [
    ("AAPL", "Apple", "Technology"), ("MSFT", "Microsoft", "Technology"),
    ("NVDA", "NVIDIA", "Semiconductors"), ("GOOGL", "Alphabet", "Technology"),
    ("AMZN", "Amazon", "Consumer/Cloud"), ("META", "Meta", "Technology"),
    ("TSLA", "Tesla", "EV/Automotive"), ("BRK-B", "Berkshire", "Conglomerate"),
    ("JPM", "JPMorgan", "Banking"), ("V", "Visa", "Payments"),
    ("MA", "Mastercard", "Payments"), ("UNH", "UnitedHealth", "Healthcare"),
    ("LLY", "Eli Lilly", "Pharma"), ("JNJ", "J&J", "Healthcare"),
    ("XOM", "ExxonMobil", "Energy"), ("AVGO", "Broadcom", "Semiconductors"),
    ("AMD", "AMD", "Semiconductors"), ("CRM", "Salesforce", "Software"),
    ("NFLX", "Netflix", "Media"), ("HD", "Home Depot", "Retail"),
    ("WMT", "Walmart", "Retail"), ("COST", "Costco", "Retail"),
    ("PG", "P&G", "Consumer"), ("KO", "Coca-Cola", "Beverages"),
    ("BAC", "Bank of America", "Banking")]),
 "GBR": ("^FTSE", "FTSE 100", [
    ("SHEL", "Shell", "Energy"), ("AZN", "AstraZeneca", "Healthcare"),
    ("HSBC", "HSBC", "Banking"), ("BP", "BP", "Energy"),
    ("UL", "Unilever", "Consumer"), ("GSK", "GSK", "Pharma"),
    ("RIO", "Rio Tinto", "Mining"), ("BARC.L", "Barclays", "Banking"),
    ("LLOY.L", "Lloyds", "Banking"), ("REL.L", "RELX", "Data/Analytics")]),
 "DEU": ("^GDAXI", "DAX", [
    ("SAP", "SAP", "Technology"), ("SIE.DE", "Siemens", "Industrials"),
    ("DTE.DE", "Deutsche Telekom", "Telecom"), ("ALV.DE", "Allianz", "Insurance"),
    ("MBG.DE", "Mercedes-Benz", "Automotive"), ("BMW.DE", "BMW", "Automotive"),
    ("BAS.DE", "BASF", "Chemicals"), ("ADS.DE", "Adidas", "Consumer"),
    ("IFX.DE", "Infineon", "Semiconductors"), ("DBK.DE", "Deutsche Bank", "Banking")]),
 "FRA": ("^FCHI", "CAC 40", [
    ("MC.PA", "LVMH", "Luxury"), ("TTE", "TotalEnergies", "Energy"),
    ("OR.PA", "L'Oreal", "Consumer"), ("SNY", "Sanofi", "Healthcare"),
    ("AIR.PA", "Airbus", "Aerospace"), ("BNP.PA", "BNP Paribas", "Banking"),
    ("RMS.PA", "Hermes", "Luxury"), ("SU.PA", "Schneider Electric", "Industrials"),
    ("DG.PA", "Vinci", "Construction"), ("KER.PA", "Kering", "Luxury")]),
 "JPN": ("^N225", "Nikkei 225", [
    ("TM", "Toyota", "Automotive"), ("SONY", "Sony", "Technology"),
    ("MUFG", "MUFG", "Banking"), ("HMC", "Honda", "Automotive"),
    ("NTDOY", "Nintendo", "Gaming"), ("SFTBY", "SoftBank", "Tech/Investment"),
    ("SMFG", "SMFG", "Banking"), ("TAK", "Takeda", "Pharma"),
    ("FANUY", "Fanuc", "Robotics"), ("MFG", "Mizuho", "Banking")]),
 "CHN": ("000001.SS", "Shanghai Comp.", [
    ("BABA", "Alibaba", "E-Commerce"), ("TCEHY", "Tencent", "Technology"),
    ("PDD", "PDD Holdings", "E-Commerce"), ("BYDDY", "BYD", "EV/Automotive"),
    ("JD", "JD.com", "E-Commerce"), ("BIDU", "Baidu", "Technology"),
    ("NIO", "NIO", "EV/Automotive"), ("LI", "Li Auto", "EV/Automotive"),
    ("NTES", "NetEase", "Gaming"), ("TME", "Tencent Music", "Media")]),
 "IND": ("^BSESN", "SENSEX", [
    ("RELIANCE.NS", "Reliance", "Conglomerate"), ("TCS.NS", "TCS", "IT Services"),
    ("HDFCBANK.NS", "HDFC Bank", "Banking"), ("INFY", "Infosys", "IT Services"),
    ("ICICIBANK.NS", "ICICI Bank", "Banking"), ("WIT", "Wipro", "IT Services"),
    ("SBIN.NS", "SBI", "Banking"), ("BHARTIARTL.NS", "Bharti Airtel", "Telecom"),
    ("LT.NS", "Larsen & Toubro", "Construction"), ("ADANIENT.NS", "Adani Ent.", "Conglomerate")]),
 "BRA": ("^BVSP", "Bovespa", [
    ("VALE", "Vale", "Mining"), ("PBR", "Petrobras", "Energy"),
    ("ITUB", "Itau", "Banking"), ("ABEV", "Ambev", "Beverages"),
    ("NU", "Nubank", "Fintech")]),
 "CAN": ("^GSPTSE", "TSX", [
    ("RY", "Royal Bank", "Banking"), ("TD", "TD Bank", "Banking"),
    ("SHOP", "Shopify", "E-Commerce"), ("ENB", "Enbridge", "Energy"),
    ("CNQ", "Canadian Natural", "Energy")]),
 "AUS": ("^AXJO", "ASX 200", [
    ("BHP", "BHP", "Mining"), ("CBA.AX", "CommBank", "Banking"),
    ("CSL.AX", "CSL", "Biotech"), ("NAB.AX", "NAB", "Banking"),
    ("WES.AX", "Wesfarmers", "Retail")]),
 "KOR": ("^KS11", "KOSPI", [
    ("005930.KS", "Samsung Elec.", "Technology"), ("000660.KS", "SK Hynix", "Semiconductors"),
    ("005380.KS", "Hyundai Motor", "Automotive"), ("035420.KS", "Naver", "Internet"),
    ("051910.KS", "LG Chem", "Chemicals")]),
 "TWN": ("^TWII", "TAIEX", [
    ("TSM", "TSMC", "Semiconductors"), ("2317.TW", "Hon Hai", "Electronics"),
    ("2454.TW", "MediaTek", "Semiconductors"), ("UMC", "UMC", "Semiconductors"),
    ("2308.TW", "Delta Electronics", "Electronics")]),
 "SAU": ("^TASI.SR", "Tadawul", [
    ("2222.SR", "Saudi Aramco", "Energy"), ("1120.SR", "Al Rajhi Bank", "Banking"),
    ("2010.SR", "SABIC", "Chemicals"), ("7010.SR", "stc", "Telecom"),
    ("1180.SR", "SNB", "Banking")]),
 "TUR": ("XU100.IS", "BIST 100", [
    ("THYAO.IS", "Turkish Airlines", "Aviation"), ("ASELS.IS", "Aselsan", "Defense"),
    ("BIMAS.IS", "BIM", "Retail"), ("KCHOL.IS", "Koc Holding", "Conglomerate"),
    ("GARAN.IS", "Garanti BBVA", "Banking")]),
 "ITA": ("FTSEMIB.MI", "FTSE MIB", [
    ("RACE", "Ferrari", "Luxury/Auto"), ("ENI.MI", "Eni", "Energy"),
    ("ISP.MI", "Intesa Sanpaolo", "Banking"), ("UCG.MI", "UniCredit", "Banking"),
    ("ENEL.MI", "Enel", "Utilities")]),
 "ESP": ("^IBEX", "IBEX 35", [
    ("SAN", "Santander", "Banking"), ("IBE.MC", "Iberdrola", "Utilities"),
    ("ITX.MC", "Inditex", "Retail"), ("BBVA", "BBVA", "Banking"),
    ("TEF", "Telefonica", "Telecom")]),
 "NLD": ("^AEX", "AEX", [
    ("ASML", "ASML", "Semiconductors"), ("PHG", "Philips", "HealthTech"),
    ("ING", "ING", "Banking"), ("HEIA.AS", "Heineken", "Beverages"),
    ("AD.AS", "Ahold Delhaize", "Retail")]),
 "CHE": ("^SSMI", "SMI", [
    ("NSRGY", "Nestle", "Consumer"), ("ROG.SW", "Roche", "Healthcare"),
    ("NOVN.SW", "Novartis", "Healthcare"), ("UBS", "UBS", "Banking"),
    ("ABBNY", "ABB", "Industrials")]),
 "SWE": ("^OMX", "OMXS30", [
    ("ERIC", "Ericsson", "Telecom"), ("VOLV-B.ST", "Volvo", "Automotive"),
    ("ATCO-A.ST", "Atlas Copco", "Industrials"), ("SEB-A.ST", "SEB", "Banking"),
    ("HM-B.ST", "H&M", "Retail")]),
 "EGY": ("^CASE30", "EGX 30", []),
 "GRC": ("GD.AT", "Athens GI", []),
 "POL": ("WIG20.WA", "WIG20", []),
 "MEX": ("^MXX", "IPC Mexico", []),
 "ARG": ("^MERV", "Merval", []),
 "IDN": ("^JKSE", "IDX Composite", []),
 "PAK": ("^KSE", "KSE 100", []),
}

def _ww_market_build(iso):
    """Blocking fetch of index + companies for one country. Returns dict."""
    import yfinance as yf
    entry = _WW_MARKETS.get(iso)
    if not entry:
        return {"iso": iso, "partial": True,
                "note": "no market mapping for this country"}
    idx_tkr, idx_name, comps = entry
    out = {"iso": iso, "partial": False, "index": None,
           "companies": [], "sectors": []}
    # --- index: yearly growth over ~5y ---
    try:
        h = yf.Ticker(idx_tkr).history(period="5y", interval="1mo")
        closes = {}
        for ts, row in h.iterrows():
            closes[ts.year] = float(row["Close"])   # last close seen per year
        years = sorted(closes)
        g_years, growth = [], []
        for i in range(1, len(years)):
            prev, cur = closes[years[i - 1]], closes[years[i]]
            if prev:
                g_years.append(years[i])
                growth.append(round((cur / prev - 1) * 100, 1))
        out["index"] = {"name": idx_name, "years": g_years, "growth": growth}
    except Exception as e:
        out["index_error"] = repr(e)[:120]
    # --- companies ---
    def _one(entry):
        sym, name, sector = entry
        c = {"sym": sym, "name": name, "sector": sector,
             "mcap": None, "ytd": None, "yr1": None}
        try:
            t = yf.Ticker(sym)
            try:
                fi = t.fast_info
                mc = None
                for k in ("market_cap", "marketCap"):
                    try:
                        mc = fi[k]
                        if mc:
                            break
                    except Exception:
                        continue
                if mc:
                    _cur = None
                    try:
                        _cur = fi["currency"]
                    except Exception:
                        pass
                    c["mcap"] = _cap_to_usd(mc, _cur)
            except Exception:
                pass
            h = t.history(period="1y", interval="1wk")
            if len(h):
                first, last = float(h["Close"].iloc[0]), float(h["Close"].iloc[-1])
                if first:
                    c["yr1"] = round((last / first - 1) * 100, 1)
                ynow = h.index[-1].year
                hy = h[h.index.year == ynow]
                if len(hy):
                    f2 = float(hy["Close"].iloc[0])
                    if f2:
                        c["ytd"] = round((last / f2 - 1) * 100, 1)
        except Exception:
            pass
        return c
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
        out["companies"] = list(_ex.map(_one, comps))
    total_mcap, sec_mcap = 0.0, {}
    for c in out["companies"]:
        if c["mcap"]:
            total_mcap += c["mcap"]
            sec_mcap[c["sector"]] = sec_mcap.get(c["sector"], 0.0) + c["mcap"]
    if total_mcap > 0:
        out["sectors"] = [{"sector": s, "weight": round(v / total_mcap, 3)}
                          for s, v in sorted(sec_mcap.items(),
                                             key=lambda kv: -kv[1])]
    if not out["companies"] and not out["index"]:
        out["partial"] = True
    return out

def _ww_company_build(sym, iso):
    """Blocking fetch of one company's detail sheet (price, stats, 1y series
    normalized to 100 vs the national index, business description)."""
    import yfinance as yf
    t = yf.Ticker(sym)
    out = {"sym": sym, "name": sym, "sector": ""}
    entry = _WW_MARKETS.get(iso)
    if entry:
        for s, n, sec in entry[2]:
            if s == sym:
                out["name"], out["sector"] = n, sec
                break
    try:
        fi = t.fast_info
        def _g(*keys):
            for k in keys:
                try:
                    v = fi[k]
                    if v:
                        return v
                except Exception:
                    continue
            return None
        out["price"] = _g("last_price", "lastPrice")
        out["currency"] = _g("currency") or ""
        out["mcap"] = _cap_to_usd(_g("market_cap", "marketCap"), out.get("currency"))
        out["hi52"] = _g("year_high", "yearHigh")
        out["lo52"] = _g("year_low", "yearLow")
    except Exception:
        pass
    try:
        info = t.info
        out["pe"] = info.get("trailingPE")
        out["volume"] = info.get("volume") or info.get("averageVolume")
        out["employees"] = info.get("fullTimeEmployees")
        out["desc"] = (info.get("longBusinessSummary") or "")[:900]
    except Exception:
        out.setdefault("desc", "")
    try:
        h = t.history(period="1y", interval="1d")
        closes = [float(v) for v in h["Close"].tolist()]
        dates = [ts.strftime("%Y-%m-%d") for ts in h.index]
        step = max(1, len(closes) // 180)
        closes, dates = closes[::step], dates[::step]
        if closes and closes[0]:
            out["series"] = {
                "dates": dates,
                "price": [round(v / closes[0] * 100, 2) for v in closes],
                "price_abs": [round(v, 2) for v in closes],
            }
    except Exception:
        pass
    try:
        if entry and out.get("series"):
            ih = yf.Ticker(entry[0]).history(period="1y", interval="1d")
            iv = [float(v) for v in ih["Close"].tolist()]
            idt = [ts.strftime("%Y-%m-%d") for ts in ih.index]
            m = dict(zip(idt, iv))
            base, idx_series = None, []
            for d in out["series"]["dates"]:
                v = m.get(d)
                if v is None:
                    idx_series.append(None)
                    continue
                if base is None:
                    base = v
                idx_series.append(round(v / base * 100, 2))
            out["series"]["index"] = idx_series
            out["index_name"] = entry[1]
    except Exception:
        pass
    return out
# GDELT uses FIPS 10-4 country codes; the polygon file uses ISO3.
_FIPS_TO_ISO3 = {
 "AF":"AFG","AL":"ALB","AG":"DZA","AO":"AGO","AR":"ARG","AM":"ARM","AS":"AUS",
 "AU":"AUT","AJ":"AZE","BA":"BHR","BG":"BGD","BO":"BLR","BE":"BEL","BH":"BLZ",
 "BN":"BEN","BT":"BTN","BL":"BOL","BK":"BIH","BC":"BWA","BR":"BRA","BU":"BGR",
 "UV":"BFA","BY":"BDI","CB":"KHM","CM":"CMR","CA":"CAN","CT":"CAF","CD":"TCD",
 "CI":"CHL","CH":"CHN","CO":"COL","CG":"COD","CF":"COG","CS":"CRI","IV":"CIV",
 "HR":"HRV","CU":"CUB","CY":"CYP","EZ":"CZE","DA":"DNK","DJ":"DJI","DR":"DOM",
 "EC":"ECU","EG":"EGY","ES":"SLV","EK":"GNQ","ER":"ERI","EN":"EST","ET":"ETH",
 "FI":"FIN","FR":"FRA","GB":"GAB","GA":"GMB","GG":"GEO","GM":"DEU","GH":"GHA",
 "GR":"GRC","GT":"GTM","GV":"GIN","PU":"GNB","GY":"GUY","HA":"HTI","HO":"HND",
 "HU":"HUN","IC":"ISL","IN":"IND","ID":"IDN","IR":"IRN","IZ":"IRQ","EI":"IRL",
 "IS":"ISR","IT":"ITA","JM":"JAM","JA":"JPN","JO":"JOR","KZ":"KAZ","KE":"KEN",
 "KN":"PRK","KS":"KOR","KU":"KWT","KG":"KGZ","LA":"LAO","LG":"LVA","LE":"LBN",
 "LT":"LSO","LI":"LBR","LY":"LBY","LH":"LTU","LU":"LUX","MK":"MKD","MA":"MDG",
 "MI":"MWI","MY":"MYS","ML":"MLI","MR":"MRT","MX":"MEX","MD":"MDA","MG":"MNG",
 "MJ":"MNE","MO":"MAR","MZ":"MOZ","BM":"MMR","WA":"NAM","NP":"NPL","NL":"NLD",
 "NZ":"NZL","NU":"NIC","NG":"NER","NI":"NGA","NO":"NOR","MU":"OMN","PK":"PAK",
 "PM":"PAN","PP":"PNG","PA":"PRY","PE":"PER","RP":"PHL","PL":"POL","PO":"PRT",
 "QA":"QAT","RO":"ROU","RS":"RUS","RW":"RWA","SA":"SAU","SG":"SEN","RI":"SRB",
 "SL":"SLE","SN":"SGP","LO":"SVK","SI":"SVN","SO":"SOM","SF":"ZAF","OD":"SSD",
 "SP":"ESP","CE":"LKA","SU":"SDN","NS":"SUR","SW":"SWE","SZ":"CHE","SY":"SYR",
 "TW":"TWN","TI":"TJK","TZ":"TZA","TH":"THA","TO":"TGO","TD":"TTO","TS":"TUN",
 "TU":"TUR","TX":"TKM","UG":"UGA","UP":"UKR","AE":"ARE","UK":"GBR","US":"USA",
 "UY":"URY","UZ":"UZB","VE":"VEN","VM":"VNM","YM":"YEM","ZA":"ZMB","ZI":"ZWE",
 "WE":"PSE","GZ":"PSE",
}

_warwatch_headline_cache = {}   # url -> {"title","domain","author","ts"}
_warwatch_headline_lock = threading.Lock()
_WW_HEADLINE_TTL = 24 * 3600
_WW_HEADLINE_MAX_BYTES = 180_000   # enough for <head> even on heavy pages


def _ww_unfurl_one(url):
    """One URL -> {"url","domain","title","author","error"}. Never raises -
    every failure mode (timeout, non-200, no parseable title, blocked bot
    UA) degrades to a domain-only result, exactly like the existing
    graceful-degradation pattern used throughout this file."""
    import re as _re
    try:
        dom = urllib.parse.urlparse(url).netloc or url
    except Exception:
        dom = url
    with _warwatch_headline_lock:
        hit = _warwatch_headline_cache.get(url)
        if hit and (time.time() - hit["ts"]) < _WW_HEADLINE_TTL:
            return {"url": url, "domain": dom, "title": hit["title"],
                    "author": hit["author"], "error": None}
    title = author = None
    err = None
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0 Safari/537.36")})
        with urllib.request.urlopen(req, timeout=6) as r:
            raw = r.read(_WW_HEADLINE_MAX_BYTES)
        html = raw.decode("utf-8", "replace")
        m = _re.search(
            r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
            html, _re.I)
        if m:
            title = m.group(1).strip()
        if not title:
            m = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.I)
            if m:
                title = m.group(1).strip()
        ma = _re.search(
            r'<meta[^>]+(?:name=["\']author["\']|property=["\']article:author["\'])'
            r'[^>]+content=["\']([^"\']+)', html, _re.I)
        if ma:
            author = ma.group(1).strip()
        if title:
            import html as _htmllib
            title = _htmllib.unescape(title)[:200]
        if author:
            import html as _htmllib
            author = _htmllib.unescape(author)[:80]
    except Exception as e:
        err = "%s: %s" % (type(e).__name__, str(e)[:60])
    if err is None:
        # Only cache real successes - caching a failure would make
        # every future call for this URL silently report error=None,
        # hiding a fetch problem that might be transient.
        with _warwatch_headline_lock:
            _warwatch_headline_cache[url] = {"title": title, "author": author,
                                             "ts": time.time()}
    return {"url": url, "domain": dom, "title": title, "author": author,
            "error": err}


def _warwatch_headlines_worker(urls, out, idx):
    out[idx] = _ww_unfurl_one(urls[idx])


def _warwatch_headlines_for(urls):
    """Unfurl up to 3 URLs in parallel (bounded - this is a small, known-
    size batch per cluster, not a crawl). Order preserved."""
    urls = [u for u in (urls or []) if u][:3]
    if not urls:
        return []
    out = [None] * len(urls)
    threads = [threading.Thread(target=_warwatch_headlines_worker,
                                args=(urls, out, i), daemon=True)
               for i in range(len(urls))]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=8)
    return [r for r in out if r is not None]


def _warwatch_ingest_zip(zip_url):
    """Download one GDELT 15-min export zip and fold conflict events into
    _warwatch. Returns the number of events added/refreshed."""
    import zipfile, io as _io
    req = urllib.request.Request(zip_url,
                                 headers={"User-Agent": "JARVIS-WorldView/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        blob = r.read()
    added = 0
    with zipfile.ZipFile(_io.BytesIO(blob)) as zf:
        name = zf.namelist()[0]
        with zf.open(name) as fh:
            for raw in fh:
                try:
                    cols = raw.decode("utf-8", "replace").rstrip("\r\n").split("\t")
                    # GDELT 2.0 event table: 61 tab-separated columns.
                    # 28=EventRootCode, 52=ActionGeo_FullName, 56/57=ActionGeo
                    # Lat/Long, 33=NumArticles, 34=AvgTone, 1=SQLDATE, 60=SOURCEURL
                    if len(cols) < 61:
                        continue
                    _root = cols[28]
                    if _root in _WARWATCH_CODES:
                        _cat = "armed"
                    elif _root in _WW_UNREST_CODES:
                        _cat = "unrest"
                    else:
                        continue
                    if not cols[56] or not cols[57]:
                        continue
                    ev = {
                        "lat": float(cols[56]), "lon": float(cols[57]),
                        "name": cols[52] or "Unknown location",
                        "code": cols[28],
                        "tone": float(cols[34]) if cols[34] else 0.0,
                        "articles": int(cols[33]) if cols[33] else 1,
                        "date": cols[1],
                        "url": cols[60],
                        "fips": cols[53],
                        "cat": _cat,
                        "ts": time.time(),
                    }
                    with _warwatch_lock:
                        _warwatch[cols[0]] = ev
                    added += 1
                except Exception:
                    continue
    return added

def _warwatch_refresher():
    """Daemon loop: backfill ~2h of GDELT updates, then poll lastupdate.txt
    every 5 minutes. Prunes events older than 24h. Never raises."""
    try:
        now = datetime.datetime.now(datetime.timezone.utc)
        base = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
        for i in range(9, 1, -1):
            t = base - datetime.timedelta(minutes=15 * i)
            url = ("http://data.gdeltproject.org/gdeltv2/%s.export.CSV.zip"
                   % t.strftime("%Y%m%d%H%M%S"))
            try:
                _warwatch_ingest_zip(url)
                _warwatch_status.update({"state": "ok", "last_fetch": time.time()})
            except Exception as e:
                _warwatch_status["last_error"] = "backfill: %r" % (e,)
    except Exception as e:
        _warwatch_status["last_error"] = "backfill setup: %r" % (e,)
    last_url = ""
    while True:
        try:
            req = urllib.request.Request(
                "http://data.gdeltproject.org/gdeltv2/lastupdate.txt",
                headers={"User-Agent": "JARVIS-WorldView/1.0"})
            with urllib.request.urlopen(req, timeout=15) as r:
                txt = r.read().decode("utf-8", "replace")
            url = ""
            for line in txt.splitlines():
                parts = line.split()
                if parts and parts[-1].endswith(".export.CSV.zip"):
                    url = parts[-1]
                    break
            if url and url != last_url:
                _warwatch_ingest_zip(url)
                last_url = url
                _warwatch_status.update({"state": "ok",
                                         "last_fetch": time.time(),
                                         "last_error": ""})
            cutoff = time.time() - _WARWATCH_TTL
            with _warwatch_lock:
                dead = [k for k, v in _warwatch.items() if v["ts"] < cutoff]
                for k in dead:
                    _warwatch.pop(k, None)
        except Exception as e:
            _warwatch_status["last_error"] = repr(e)
        time.sleep(300)

def _start_warwatch_relay():
    """Start the GDELT conflict-events relay on a daemon thread. Idempotent."""
    global _warwatch_relay_started
    with _warwatch_relay_lock:
        if _warwatch_relay_started:
            return
        threading.Thread(target=_warwatch_refresher, daemon=True,
                         name="jarvis-warwatch-relay").start()
        _warwatch_relay_started = True
        _warwatch_status["state"] = "starting (backfilling last 2h)"
        print("[diag] warwatch relay started (GDELT v2 event stream)")


# ---------------------------------------------------------------------------
# Matterhorn Quant status bridge (v5.5). scripts/run_live.py writes
# status/quant_status.json inside the quant repo; this relay finds it and
# serves it at GET /quant so the Aleph QUANT tab can render live results.
# ---------------------------------------------------------------------------
_quant_cache = {"data": None, "ts": 0.0, "path": None}
_QUANT_TTL = 15  # seconds

def _audit_find_latest():
    """Return the newest logs/audit*.jsonl next to a quant_status.json, or None."""
    import glob
    status = _quant_find_status()
    candidates = []
    if status:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(status)), "logs")
        candidates.extend(glob.glob(os.path.join(logs_dir, "audit*.jsonl")))
    if not candidates:
        home = os.path.expanduser("~")
        try:
            candidates = glob.glob(os.path.join(home, "**", "logs", "audit*.jsonl"),
                                   recursive=True)
        except Exception:
            candidates = []
    if not candidates:
        return None
    small = [c for c in candidates if "audit_small" in os.path.basename(c)]
    if small:
        candidates = small
    try:
        return max(candidates, key=os.path.getmtime)
    except Exception:
        return candidates[0]

_ACTIVITY_LABELS = {
    "decision": lambda p: "\u05d4\u05d7\u05dc\u05d8\u05d4 \u00b7 " + p.get("symbol", "?")
        + ": \u05e6\u05d9\u05d5\u05df %+.2f \u05d1\u05d9\u05d8\u05d7\u05d5\u05df %.2f" % (
            p.get("score", 0), p.get("confidence", 0)),
    "fill": lambda p: ("\u05e7\u05e0\u05d9\u05d9\u05d4" if p.get("side") == "buy" else "\u05de\u05db\u05d9\u05e8\u05d4")
        + " \u00b7 %s: %.0f \u05d9\u05d7\u05d9\u05d3\u05d5\u05ea \u05d1-%.2f$" % (
            p.get("symbol", "?"), p.get("qty", 0), p.get("price", 0)),
    "risk_event": lambda p: "\u05e1\u05d9\u05db\u05d5\u05df \u00b7 " + str(p.get("note", "")),
    "learning_update": lambda p: ("\u05dc\u05de\u05d9\u05d3\u05d4 \u00b7 %s: %.2f\u2192%.2f (%s)" % (
        p.get("strategy", "?"), p.get("old_weight", 0), p.get("new_weight", 0),
        "\u05e6\u05d3\u05e7" if p.get("signal_hit") else "\u05d8\u05e2\u05d4")),
    "eod_risk_review": lambda p: ("\u05e1\u05d9\u05db\u05d5\u05dd \u05d9\u05d5\u05de\u05d9 \u00b7 \u05d4\u05d5\u05df %.0f$ \u00b7 \u05d9\u05e8\u05d9\u05d3\u05d4 %.1f%% \u00b7 VaR %.1f%%" % (
        p.get("equity", 0), p.get("drawdown", 0) * 100, p.get("portfolio_var", 0) * 100)),
    "symbol_blacklist": lambda p: ("\u05d4\u05e8\u05d7\u05e7\u05d4 \u00b7 %s: " % p.get("symbol", "?"))
        + (("\u05d4\u05d5\u05e8\u05d7\u05e7 \u05dc\u05e1\u05e4\u05e1\u05dc \u05dc-%d \u05d9\u05de\u05d9 \u05de\u05e1\u05d7\u05e8 (\u05ea\u05d5\u05e6\u05d0\u05d5\u05ea \u05e9\u05d2\u05d5\u05d9\u05d5\u05ea \u05d7\u05d5\u05d6\u05e8\u05d5\u05ea)"
            % p.get("cooldown_bars", 0)) if p.get("action") == "benched"
           else "\u05d4\u05d5\u05d7\u05d6\u05e8 \u05dc\u05de\u05e1\u05d7\u05e8 (\u05e1\u05d9\u05d5\u05dd \u05e6\u05d9\u05e0\u05d5\u05df)"),
}

def _quant_find_status():
    """Return the newest quant_status.json across likely locations, or None."""
    import glob
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, "Desktop", "quant", "**", "status", "quant_status.json"),
        os.path.join(home, "Downloads", "**", "status", "quant_status.json"),
        os.path.join(home, "**", "matterhorn*", "**", "status", "quant_status.json"),
        os.path.join(home, "**", "quant_status.json"),
    ]
    hits = []
    for pat in patterns:
        try:
            hits.extend(glob.glob(pat, recursive=True))
        except Exception:
            continue
        if hits:
            break
    if not hits:
        return None
    try:
        return max(hits, key=os.path.getmtime)
    except Exception:
        return hits[0]


class _FlightsProxyHandler(http.server.BaseHTTPRequestHandler):
    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self):
        # preflight - just allow it
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/training_photo":
            self._handle_training_photo()
            return
        if parsed.path == "/geoloc_photo":
            self._handle_geoloc_photo()
            return
        self._json_out({"ok": False, "error": "not found"}, 404)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/route":
            self._handle_route(parsed)
            return
        if parsed.path == "/tle":
            self._handle_tle()
            return
        if parsed.path == "/state":
            self._handle_state()
            return
        if parsed.path == "/planet":
            self._handle_planet(parsed)
            return
        if parsed.path == "/ask":
            self._handle_ask(parsed)
            return
        if parsed.path in ("/training", "/training_weight",
                           "/training_workout", "/training_import"):
            self._handle_training(parsed)
            return
        if parsed.path in ("/calendar", "/calendar_add"):
            self._handle_calendar(parsed)
            return
        if parsed.path == "/briefing_audio":
            self._handle_briefing_audio(parsed)
            return
        if parsed.path == "/briefing":
            self._handle_briefing(parsed)
            return
        if parsed.path in ("/todo", "/todo_add", "/todo_toggle", "/todo_del"):
            self._handle_todo(parsed)
            return
        # --- Quant bot activity feed, human-readable (v5.9) -----------------
        if parsed.path == "/quant_activity":
            try:
                import json as _json
                params = urllib.parse.parse_qs(parsed.query)
                limit = min(int((params.get("limit", ["60"])[0]) or 60), 300)
                path = _audit_find_latest()
                items = []
                if path and os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as fh:
                        lines = fh.readlines()
                    for line in lines[-limit:]:
                        try:
                            e = _json.loads(line)
                            fmt = _ACTIVITY_LABELS.get(e.get("type"))
                            text = fmt(e.get("payload", {})) if fmt else str(e.get("type"))
                        except Exception:
                            continue
                        _pl = e.get("payload", {}) or {}
                        items.append({"ts": e.get("ts"), "type": e.get("type"), "text": text,
                                      "date": _pl.get("date", ""),
                                      "detail": (_pl.get("reasoning") or "")[:600]})
                    items.reverse()  # newest first
                payload = _json.dumps({
                    "available": bool(path), "source_path": path or "",
                    "items": items,
                    "note": None if path else "No audit log found yet. Run scripts/run_live.py "
                                              "or run_small.py to generate one.",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"available":false,"items":[],"note":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- Matterhorn Quant status (v5.5) --------------------------------
        if parsed.path == "/quant":
            try:
                import json as _json
                now = time.time()
                if _quant_cache["data"] is not None and now - _quant_cache["ts"] < _QUANT_TTL:
                    body = _quant_cache["data"]
                else:
                    path = _quant_find_status()
                    if path and os.path.exists(path):
                        with open(path, "r", encoding="utf-8") as fh:
                            data = _json.load(fh)
                        data["available"] = True
                        data["_source_path"] = path
                        body = _json.dumps(data).encode("utf-8")
                    else:
                        body = _json.dumps({
                            "available": False,
                            "message": ("No quant_status.json found yet. Run "
                                        "scripts/run_live.py in the Matterhorn "
                                        "Quant repo to generate it."),
                        }).encode("utf-8")
                    _quant_cache.update({"data": body, "ts": now, "path": path})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as _e:
                try:
                    err = ('{"available":false,"message":'
                           + json.dumps("quant bridge error: " + str(_e))
                           + "}").encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                except Exception:
                    pass
            return
        # --- WorldView API keys endpoint (wv_keys_endpoint) ----------------
        if parsed.path == "/keys":
            try:
                import json as _json
                _payload = _json.dumps({
                    "googleMapsApiKey": os.environ.get("GOOGLE_MAPS_API_KEY", "") or "",
                    "owmApiKey": os.environ.get("OWM_API_KEY", "") or "",
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(_payload)))
                self.end_headers()
                self.wfile.write(_payload)
            except Exception as _e:
                try:
                    self.send_response(500); self._cors_headers(); self.end_headers()
                except Exception:
                    pass
            return
        # --- Country facts, proxied + cached (v4.99) ------------------------
        if parsed.path == "/facts":
            try:
                import json as _json
                params = urllib.parse.parse_qs(parsed.query)
                iso = (params.get("iso", [""])[0] or "").strip().upper()[:3]
                if not iso:
                    raise ValueError("no iso")
                c = _ww_facts.get(iso)
                if not c or time.time() - c["ts"] > _WW_FACTS_TTL:
                    data = _wb_facts(iso)
                    _ts = time.time()
                    if not (data.get("population") and data.get("gdp")):
                        _ts = _ts - _WW_FACTS_TTL + 600
                    _ww_facts[iso] = {"data": data, "ts": _ts}
                    c = _ww_facts[iso]
                payload = _json.dumps(c["data"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- HERMES MKT tab: real quotes, cached ~45s (v5.7) ----------------
        if parsed.path == "/quotes":
            try:
                import json as _json
                now = time.time()
                with _quotes_lock:
                    if _quotes_cache["data"] is None or now - _quotes_cache["ts"] > _QUOTES_TTL:
                        try:
                            data = _quotes_build()
                        except Exception as _e:
                            data = {}
                        _quotes_cache.update({"data": data, "ts": now})
                    quotes = _quotes_cache["data"]
                payload = _json.dumps({"quotes": quotes, "ts": _quotes_cache["ts"],
                                       "covered": len(quotes)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"quotes":{},"error":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- Single-company detail sheet, cached 6h (v5.0) -------------------
        if parsed.path == "/company":
            try:
                import json as _json, re as _re
                params = urllib.parse.parse_qs(parsed.query)
                sym = (params.get("sym", [""])[0] or "").strip()[:16]
                iso = (params.get("iso", [""])[0] or "").strip().upper()[:3]
                if not sym or not _re.match(r"^[A-Za-z0-9.\-^]{1,16}$", sym):
                    raise ValueError("bad symbol")
                c = _ww_company.get(sym)
                if not c or time.time() - c["ts"] > _WW_COMPANY_TTL:
                    with _ww_company_lock:
                        c = _ww_company.get(sym)
                        if not c or time.time() - c["ts"] > _WW_COMPANY_TTL:
                            try:
                                data = _ww_company_build(sym, iso)
                            except ImportError:
                                data = {"error": "yfinance not installed"}
                            _ww_company[sym] = {"data": data, "ts": time.time()}
                            c = _ww_company[sym]
                payload = _json.dumps(c["data"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- Country market data via yfinance, cached 6h (v4.99) ------------
        if parsed.path == "/market":
            try:
                import json as _json
                params = urllib.parse.parse_qs(parsed.query)
                iso = (params.get("iso", [""])[0] or "").strip().upper()[:3]
                if not iso:
                    raise ValueError("no iso")
                c = _ww_market.get(iso)
                if not c or time.time() - c["ts"] > _WW_MARKET_TTL:
                    with _ww_market_lock:
                        c = _ww_market.get(iso)
                        if not c or time.time() - c["ts"] > _WW_MARKET_TTL:
                            try:
                                data = _ww_market_build(iso)
                            except ImportError:
                                data = {"iso": iso, "partial": True,
                                        "note": "yfinance not installed - run: pip install yfinance"}
                            _ww_market[iso] = {"data": data, "ts": time.time()}
                            c = _ww_market[iso]
                payload = _json.dumps(c["data"]).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- WARWATCH v36: real headline unfurl for the intel card ------
        # NOT a new GDELT query - GDELT's spatial GEO 2.0 API is already
        # retired (see the WARWATCH relay comment above). This fetches the
        # article page for URLs the relay ALREADY has for a cluster and
        # reads just the <title>/og:title (+ author meta if present) -
        # the same "link unfurl" technique Slack/WhatsApp use for
        # previews. Exact match to the sources already shown, not a
        # fuzzy re-search.
        # --- WorldView CAMERAS: Windy webcams proxy (see _handle_webcams) --
        # --- SCOUTING property card: GovMap parcel + transactions (v5.21) --
        if parsed.path == "/property":
            self._handle_property(parsed)
            return
        if parsed.path == "/webcams":
            self._handle_webcams(parsed)
            return
        if parsed.path == "/warwatch_headlines":
            self._handle_warwatch_headlines(parsed)
            return
        # --- WorldView WARWATCH country tension tiers (v4.97) ---------------
        if parsed.path == "/warwatch_countries":
            try:
                import json as _json
                agg = {}
                with _warwatch_lock:
                    evs = list(_warwatch.values())
                for ev in evs:
                    iso = _FIPS_TO_ISO3.get(ev.get("fips", ""), "")
                    if not iso:
                        continue
                    a = agg.setdefault(iso, {"14": 0, "18": 0, "19": 0, "20": 0})
                    code = ev.get("code", "18")
                    a[code] = a.get(code, 0) + 1
                out = []
                for iso, a in agg.items():
                    war = a.get("19", 0) + a.get("20", 0)
                    assault = a.get("18", 0)
                    unrest = a.get("14", 0)
                    tier = 0
                    if war >= _WW_RED_WAR:
                        tier = 2
                    elif (war >= _WW_ORANGE_WAR
                          or assault >= _WW_ORANGE_ASSAULT
                          or unrest >= _WW_ORANGE_UNREST):
                        tier = 1
                    if tier:
                        out.append({"iso3": iso, "tier": tier,
                                    "war": war,
                                    "armed": war + assault,
                                    "unrest": unrest})
                payload = _json.dumps({"countries": out,
                                       "status": dict(_warwatch_status)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    self.send_response(502); self._cors_headers(); self.end_headers()
                except Exception:
                    pass
            return
        # --- World country polygons, cached on disk (v4.97) -----------------
        if parsed.path == "/countries":
            try:
                cpath = Path(__file__).resolve().parent / "countries.geo.json"
                if not cpath.exists():
                    req = urllib.request.Request(
                        "https://cdn.jsdelivr.net/gh/johan/world.geo.json@master/countries.geo.json",
                        headers={"User-Agent": "JARVIS-WorldView/1.0"})
                    with urllib.request.urlopen(req, timeout=30) as r:
                        cpath.write_bytes(r.read())
                data = cpath.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except Exception as _e:
                try:
                    self.send_response(502); self._cors_headers(); self.end_headers()
                except Exception:
                    pass
            return
        # --- AI country brief, 24h cache (v4.97) ----------------------------
        if parsed.path == "/country_brief":
            try:
                import json as _json
                params = urllib.parse.parse_qs(parsed.query)
                iso = (params.get("iso", [""])[0] or "").strip().upper()[:3]
                cname = (params.get("name", [""])[0] or iso).strip()[:60]
                if not iso:
                    raise ValueError("no iso")
                now = time.time()
                cached = _ww_briefs.get(iso)
                if cached and now - cached["ts"] < _WW_BRIEF_TTL:
                    text, was_cached = cached["text"], True
                else:
                    with _ww_brief_lock:
                        cached = _ww_briefs.get(iso)
                        if cached and time.time() - cached["ts"] < _WW_BRIEF_TTL:
                            text, was_cached = cached["text"], True
                        else:
                            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY,
                                                          timeout=60.0)
                            resp = client.messages.create(
                                model="claude-opus-5",
                                max_tokens=600,
                                messages=[{"role": "user", "content":
                                    "אתה מודול המודיעין של JARVIS. כתוב תקציר מודיעיני קומפקטי בעברית על "
                                    + cname +
                                    " בשלושה חלקים עם כותרות: 1) מצב כלכלי נוכחי "
                                    "2) חברות/סקטורים צומחים בולטים 3) מצב צבאי-ביטחוני. "
                                    "עד 180 מילים סה\"כ. בלי הקדמות ובלי סיכום. "
                                    "אם המידע שלך עשוי להיות לא עדכני - ציין זאת בשורה האחרונה."}],
                            )
                            text = "".join(b.text for b in resp.content
                                           if getattr(b, "type", "") == "text").strip()
                            _ww_briefs[iso] = {"text": text, "ts": time.time()}
                            was_cached = False
                payload = _json.dumps({"brief": text,
                                       "cached": was_cached}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e)) + '}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- WorldView WARWATCH conflict events (v4.96) ---------------------
        if parsed.path == "/warwatch":
            try:
                import json as _json
                clusters = {}
                with _warwatch_lock:
                    evs = [v for v in _warwatch.values()
                           if v.get("cat", "armed") == "armed"]
                for ev in evs:
                    key = (round(ev["lat"], 1), round(ev["lon"], 1))
                    c = clusters.get(key)
                    if c is None:
                        c = {"lat": ev["lat"], "lon": ev["lon"],
                             "name": ev["name"], "count": 0, "urls": []}
                        clusters[key] = c
                    c["count"] += 1
                    if ev["url"] and len(c["urls"]) < 3 and ev["url"] not in c["urls"]:
                        c["urls"].append(ev["url"])
                feats = []
                for c in clusters.values():
                    links = ""
                    for u in c["urls"]:
                        try:
                            dom = urllib.parse.urlparse(u).netloc or u
                        except Exception:
                            dom = u
                        links += ('<a href="%s" target="_blank" '
                                  'rel="noopener">%s</a><br>' % (u, dom))
                    feats.append({
                        "type": "Feature",
                        "geometry": {"type": "Point",
                                     "coordinates": [c["lon"], c["lat"]]},
                        "properties": {"name": c["name"], "count": c["count"],
                                       "html": links,
                                       "urls": c["urls"]},
                    })
                payload = _json.dumps({
                    "type": "FeatureCollection", "features": feats,
                    "status": dict(_warwatch_status),
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e))
                            + ',"type":"FeatureCollection","features":[]}'
                            ).encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        # --- WorldView VESSELS snapshot (v4.66) ----------------------------
        if parsed.path == "/vessels":
            try:
                import json as _json
                now = time.time()
                with _vessels_lock:
                    items = [dict(v) for v in _vessels.values()
                             if v.get("lat") is not None and v.get("lon") is not None
                             and (now - v.get("ts", 0)) < 600]
                    stale = [m for m, v in _vessels.items()
                             if (now - v.get("ts", 0)) > 1800]
                    for m in stale:
                        _vessels.pop(m, None)
                payload = _json.dumps({"vessels": items,
                                       "count": len(items),
                                       "status": dict(_vessels_status)}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            except Exception as _e:
                try:
                    body = ('{"error":' + json.dumps(str(_e))
                            + ',"vessels":[]}').encode("utf-8")
                    self.send_response(502)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(body)
                except Exception:
                    pass
            return
        if parsed.path != "/flights":
            self.send_response(404)
            self._cors_headers()
            self.end_headers()
            return
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lat = params.get("lat", ["32.0"])[0]
            lon = params.get("lon", ["34.8"])[0]
            radius = params.get("radius", ["250"])[0]
            # validate as numbers - rejects junk before talking to adsb.lol
            float(lat); float(lon); int(float(radius))
            url = "https://api.adsb.lol/v2/lat/%s/lon/%s/dist/%s" % (lat, lon, radius)
            req = urllib.request.Request(url, headers={
                "User-Agent": "JARVIS-WorldView/1.0",
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            try:
                body = (
                    '{"error":' + json.dumps(str(e)) + ',"ac":[]}'
                ).encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass

    def _handle_property(self, parsed):
        # SCOUTING property card: GET /property?lat=&lon=[&radius=][&address=]
        # Mirrors /webcams: validate before any upstream URL is built, clamp
        # the range, answer with structured JSON on every path including
        # failure, and set CORS everywhere because the page is served from
        # :7777 while this is :7778.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lat = float(params.get("lat", ["32.0"])[0])
            lon = float(params.get("lon", ["34.8"])[0])
            radius = int(float(params.get("radius", ["150"])[0]))
            address = (params.get("address", [""])[0] or "").strip()
            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                raise ValueError("coordinates out of range")
        except (TypeError, ValueError, OverflowError, IndexError) as e:
            self._send_property_json(400,
                {"ok": False, "error": "bad lat/lon/radius: %s" % e,
                 "deals": [], "parcels": []})
            return
        radius = max(25, min(radius, _GOVMAP_MAX_RADIUS_M))
        if len(address) > 120:
            address = address[:120]
        try:
            payload = _govmap_property_at(lat, lon, radius, address or None)
        except Exception as e:
            # An upstream problem is a 502 with an explanation, never a bare
            # 500 and never an exception that reaches the socket.
            print("[property] lookup failed: %r" % (e,), flush=True)
            self._send_property_json(502,
                {"ok": False, "error": "property service unavailable",
                 "deals": [], "parcels": []})
            return
        self._send_property_json(200, payload)

    def _send_property_json(self, code, obj):
        try:
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type",
                             "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            pass

    def _handle_webcams(self, parsed):
        # WorldView CAMERAS layer: GET /webcams?lat=<f>&lon=<f>&radius=<int km>
        # Same shape of problem as /flights (a geographic query that needs a
        # server-side credential), so it mirrors that route: validate before
        # building any URL, forward with the secret, CORS on every path.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lat = params.get("lat", ["32.0"])[0]
            lon = params.get("lon", ["34.8"])[0]
            radius = params.get("radius", ["100"])[0]
            # validate as numbers BEFORE building any URL
            lat = float(lat); lon = float(lon); radius = int(float(radius))
        except (TypeError, ValueError, OverflowError) as e:
            # junk coordinates get a 400 here, not a trip upstream to Windy
            try:
                body = ('{"error":' + json.dumps("bad lat/lon/radius: %s" % e)
                        + ',"webcams":[]}').encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass
            return
        radius = max(1, min(radius, _WEBCAMS_MAX_RADIUS_KM))
        api_key = os.environ.get("WINDY_API_KEY", "") or ""
        if not api_key:
            # a structured, explainable empty result - NOT a 500. The page
            # shows this message; the fix is one line in .env.
            try:
                body = json.dumps({"webcams": [],
                                   "error": "no WINDY_API_KEY in .env"}
                                  ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass
            return
        try:
            url = ("%s?nearby=%s,%s,%s&limit=50"
                   "&include=images,location,urls&lang=en"
                   % (_WINDY_WEBCAMS_URL, lat, lon, radius))
            # v3 accepts the key ONLY as this header (renamed from v2's
            # x-windy-key) - never as a query parameter.
            req = urllib.request.Request(url, headers={
                "User-Agent": "JARVIS-WorldView/1.0",
                "Accept": "application/json",
                "x-windy-api-key": api_key,
            })
            with urllib.request.urlopen(req, timeout=10) as r:
                raw = json.loads(r.read().decode("utf-8", "replace"))
            # reshape to only what the page needs, so the frontend is not
            # coupled to Windy's full response shape
            cams = []
            for w in (raw.get("webcams") or []):
                loc = w.get("location") or {}
                imgs = (w.get("images") or {}).get("current") or {}
                urls = w.get("urls") or {}
                cam_lat = loc.get("latitude")
                cam_lon = loc.get("longitude")
                if cam_lat is None or cam_lon is None:
                    continue
                cams.append({
                    "id": w.get("webcamId"),
                    "title": w.get("title") or "Webcam",
                    "lat": cam_lat, "lon": cam_lon,
                    "preview": (imgs.get("preview")
                                or imgs.get("thumbnail") or ""),
                    "url": urls.get("detail") or "",
                })
            body = json.dumps({"webcams": cams,
                               "count": len(cams)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            try:
                body = ('{"error":' + json.dumps(str(e))
                        + ',"webcams":[]}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(body)
            except Exception:
                pass

    def _handle_route(self, parsed):
        # Origin/destination is NOT in raw ADS-B; adsb.lol exposes plausible
        # routes via POST /api/0/routeset keyed on callsign. We proxy it here
        # (browser is blocked by CORS, same as the flights feed).
        try:
            params = urllib.parse.parse_qs(parsed.query)
            cs = (params.get("callsign", [""])[0] or "").strip().upper()
            lat = params.get("lat", ["32.0"])[0]
            lon = params.get("lon", ["34.8"])[0]
            float(lat); float(lon)
            if not cs:
                raise ValueError("no callsign")
            body = json.dumps({"planes": [
                {"callsign": cs, "lat": float(lat), "lng": float(lon)}
            ]}).encode("utf-8")
            req = urllib.request.Request(
                "https://api.adsb.lol/api/0/routeset",
                data=body, method="POST",
                headers={
                    "User-Agent": "JARVIS-WorldView/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                out = r.read()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e)) + '}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_tle(self):
        # v4.51: TLE feed for the WorldView SATELLITES tab. Pulls the
        # "stations" (ISS, CSS, crewed) and "visual" (brightest ~150)
        # group files from Celestrak, dedupes by NORAD id, and caches the
        # JSON in-process for 6 hours - TLEs change slowly, be polite.
        global _tle_cache
        try:
            now = time.time()
            if _tle_cache["data"] and (now - _tle_cache["ts"] < 6 * 3600):
                payload = _tle_cache["data"]
            else:
                sats, seen = [], set()
                for grp_name, grp_tag in (("stations", "station"),
                                          ("visual", "visual")):
                    url = ("https://celestrak.org/NORAD/elements/gp.php"
                           "?GROUP=%s&FORMAT=tle" % grp_name)
                    req = urllib.request.Request(url, headers={
                        "User-Agent": "JARVIS-WorldView/1.0",
                        "Accept": "text/plain",
                    })
                    try:
                        with urllib.request.urlopen(req, timeout=15) as r:
                            text = r.read().decode("utf-8", "replace")
                    except Exception:
                        continue  # one group failing is survivable
                    lines = [ln.rstrip() for ln in text.splitlines()
                             if ln.strip()]
                    for i in range(0, len(lines) - 2, 3):
                        name = lines[i].strip()
                        l1, l2 = lines[i + 1], lines[i + 2]
                        if not l1.startswith("1 ") or not l2.startswith("2 "):
                            continue
                        norad = l1[2:7].strip()
                        if norad in seen:
                            continue
                        seen.add(norad)
                        sats.append({"name": name, "l1": l1, "l2": l2,
                                     "grp": grp_tag})
                if not sats:
                    raise RuntimeError("no TLE data from Celestrak")
                payload = json.dumps({"sats": sats[:150],
                                      "fetched": int(now)}).encode("utf-8")
                _tle_cache = {"ts": now, "data": payload}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            try:
                if _tle_cache["data"]:
                    # serve stale cache rather than nothing
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors_headers()
                    self.end_headers()
                    self.wfile.write(_tle_cache["data"])
                    return
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"sats":[]}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_state(self):
        # v4.52: live state for the Achilles screen. Cheap JSON, polled
        # ~every 600ms by the page; last_poll doubles as a "page is open"
        # heartbeat for open_achilles().
        try:
            _achilles_state["last_poll"] = time.time()
            _scene = _achilles_state.get("scene", "core")
            body = json.dumps({
                "state": _achilles_state.get("state", "idle"),
                "scene": _scene,
                "ts": _achilles_state.get("ts", 0.0),
                "srv": time.time(),
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            # v4.53: "dive" is one-shot - consumed by the first poll that
            # sees it, so reopening the screen later never re-triggers it.
            if _scene == "dive":
                _achilles_state["scene"] = "core"
        except Exception:
            pass

    def _handle_ask(self, parsed):
        # v4.53: typed question from the Achilles screen -> same brain as
        # voice. Replies with text; speaks aloud too when asked from the PC.
        try:
            # v4.67: the proxy binds 0.0.0.0 for phone WorldView access, but
            # /ask runs the full brain (state mutation, web search, API spend).
            # Restrict it to loopback so a LAN host / drive-by web page can't
            # drive it. (The phone uses Telegram for chat instead.)
            _peer = self.client_address[0] if self.client_address else ""
            if _peer not in ("127.0.0.1", "::1", "localhost"):
                self.send_response(403)
                self._cors_headers()
                self.end_headers()
                return
            params = urllib.parse.parse_qs(parsed.query)
            q = (params.get("q", [""])[0] or "").strip()
            if not q:
                raise ValueError("empty question")
            lang = "he" if is_hebrew(q) else "en"
            _achilles_state["state"] = "thinking"
            _achilles_state["ts"] = time.time()
            try:
                mem = APP.memory if (APP is not None and getattr(APP, "memory", "")) \
                      else load_long_term_memory()
            except Exception:
                mem = ""
            try:
                reply = think(q, mem, lang=lang)
            except Exception as e:
                reply = "Brain error: %r" % (e,)
            body = json.dumps({"reply": reply}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
            # speak only when the question came from this PC
            client = self.client_address[0] if self.client_address else ""
            if client in ("127.0.0.1", "::1", "localhost"):
                def _say(txt):
                    _achilles_state["state"] = "speaking"
                    _achilles_state["ts"] = time.time()
                    try:
                        speak(clean_text(txt))
                    except Exception:
                        pass
                    _achilles_state["state"] = "idle"
                    _achilles_state["ts"] = time.time()
                threading.Thread(target=_say, args=(reply,), daemon=True).start()
            else:
                _achilles_state["state"] = "idle"
                _achilles_state["ts"] = time.time()
        except Exception as e:
            try:
                _achilles_state["state"] = "idle"
                msg = ('{"error":' + json.dumps(str(e)) + "}").encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _json_out(self, obj, status=200):
        # v5.16 shared helper for the calendar/briefing endpoints.
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _peer_can_edit(self):
        # Same gate as /todo mutations: loopback or Tailscale CGNAT only.
        _peer = self.client_address[0] if self.client_address else ""
        if _peer in ("127.0.0.1", "::1", "localhost"):
            return True
        if "." in _peer:
            try:
                _oct = [int(x) for x in _peer.split(".")]
                if _oct[0] == 100 and 64 <= _oct[1] <= 127:
                    return True
            except Exception:
                pass
        return False

    def _handle_calendar(self, parsed):
        # v5.16: read + add Google Calendar events for the mobile Calendar tile.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            if parsed.path == "/calendar_add":
                if not self._peer_can_edit():
                    self._json_out({"ok": False, "error": "forbidden"}, 403)
                    return
                summary = (params.get("summary", [""])[0] or "").strip()
                start = (params.get("start", [""])[0] or "").strip()
                end = (params.get("end", [""])[0] or "").strip() or None
                if not summary or not start:
                    self._json_out({"ok": False,
                                    "error": "summary and start required"}, 400)
                    return
                msg = calendar_add(summary, start, end)
                ok = "added" in str(msg).lower()
                self._json_out({"ok": ok, "message": str(msg)},
                               200 if ok else 500)
                return
            svc = _calendar_service()
            if svc is None:
                self._json_out({"connected": False, "events": []})
                return
            try:
                days = min(max(int((params.get("days", ["7"])[0]) or 7), 1), 31)
            except Exception:
                days = 7
            now = datetime.datetime.now(datetime.timezone.utc)
            tmax = now + datetime.timedelta(days=days)
            res = svc.events().list(calendarId="primary",
                                    timeMin=now.isoformat(),
                                    timeMax=tmax.isoformat(),
                                    singleEvents=True, orderBy="startTime",
                                    maxResults=40).execute()
            events = []
            for e in res.get("items", []):
                st = e.get("start", {})
                en = e.get("end", {})
                events.append({
                    "id": e.get("id", ""),
                    "summary": e.get("summary", "(no title)"),
                    "start": st.get("dateTime", st.get("date", "")),
                    "end": en.get("dateTime", en.get("date", "")),
                    "allday": "date" in st and "dateTime" not in st,
                    "location": e.get("location", ""),
                })
            self._json_out({"connected": True, "days": days,
                            "events": events})
        except Exception as e:
            try:
                self._json_out({"connected": False, "events": [],
                                "error": str(e)}, 500)
            except Exception:
                pass

    def _handle_briefing(self, parsed):
        # v5.16: text briefing for the mobile Briefing tile. Reuses
        # daily_briefing() and caches per (part,lang) for 15 min.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lang = (params.get("lang", ["he"])[0] or "he").strip().lower()
            if lang not in ("he", "en"):
                lang = "he"
            part = (params.get("part", ["auto"])[0] or "auto").strip().lower()
            if part not in ("auto", "morning", "afternoon", "evening"):
                part = "auto"
            fresh = (params.get("fresh", ["0"])[0] or "0") == "1"
            rpart = _briefing_part_from_clock(datetime.datetime.now()) \
                if part == "auto" else part
            ck = rpart + ":" + lang
            now = time.time()
            hit = _briefing_http_cache.get(ck)
            if hit and not fresh and (now - hit["ts"] < 900) and hit["text"]:
                self._json_out({"ok": True, "part": rpart, "lang": lang,
                                "cached": True, "age_sec": int(now - hit["ts"]),
                                "text": hit["text"]})
                return
            text = daily_briefing(rpart, lang)
            if text and not text.startswith("[Error"):
                _briefing_http_cache[ck] = {"ts": now, "text": text}
            self._json_out({"ok": True, "part": rpart, "lang": lang,
                            "cached": False, "age_sec": 0, "text": text})
        except Exception as e:
            try:
                self._json_out({"ok": False, "text": "",
                                "error": str(e)}, 500)
            except Exception:
                pass

    def _handle_briefing_audio(self, parsed):
        # v5.16b: same briefing, rendered to mp3 with the REAL Achilles voice
        # (ElevenLabs Alfred for English, edge-tts he-IL-Avri for Hebrew --
        # the exact speak() pipeline). Cached per (part,lang) alongside the
        # text cache so the phone replays instantly.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            lang = (params.get("lang", ["he"])[0] or "he").strip().lower()
            if lang not in ("he", "en"):
                lang = "he"
            part = (params.get("part", ["auto"])[0] or "auto").strip().lower()
            if part not in ("auto", "morning", "afternoon", "evening"):
                part = "auto"
            rpart = _briefing_part_from_clock(datetime.datetime.now()) \
                if part == "auto" else part
            ck = rpart + ":" + lang
            now = time.time()

            thit = _briefing_http_cache.get(ck)
            if thit and (now - thit["ts"] < 900) and thit["text"]:
                text = thit["text"]
            else:
                text = daily_briefing(rpart, lang)
                if text and not text.startswith("[Error"):
                    _briefing_http_cache[ck] = {"ts": now, "text": text}

            if not text or text.startswith("[Error"):
                self._json_out({"ok": False, "error": "briefing failed"}, 500)
                return

            ahit = _briefing_audio_cache.get(ck)
            fn = None
            if (ahit and (now - ahit["ts"] < 900)
                    and os.path.exists(ahit["path"])):
                fn = ahit["path"]
            if fn is None:
                fn = os.path.join(str(_LOCATION_DIR),
                                  "briefing_%s_%s.mp3" % (rpart, lang))
                produced = False
                if not is_mostly_hebrew(text):
                    produced = speak_elevenlabs(text, fn)
                if not produced:
                    voice = VOICE_HEBREW if is_mostly_hebrew(text) \
                        else VOICE_ENGLISH
                    try:
                        asyncio.run(_speak(text, voice, fn))
                        produced = True
                    except Exception:
                        try:
                            asyncio.run(_speak(text, VOICE_ENGLISH_FALLBACK,
                                               fn))
                            produced = True
                        except Exception as e2:
                            print("[diag] briefing_audio TTS failed:",
                                  repr(e2))
                if not produced or not os.path.exists(fn):
                    self._json_out({"ok": False, "error": "tts failed"}, 500)
                    return
                _briefing_audio_cache[ck] = {"ts": now, "path": fn}

            with open(fn, "rb") as fh:
                data = fh.read()
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(data)))
            self._cors_headers()
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            try:
                self._json_out({"ok": False, "error": str(e)}, 500)
            except Exception:
                pass

    def _handle_training(self, parsed):
        # v5.16c: weight + workout logging for the mobile Training tile.
        # Reads/writes training_log.json in the files dir - the SAME file the
        # daily briefing already reads (flat keys preserved), plus history
        # arrays for the tile's chart. Mutations gated like /todo.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            p = Path(__file__).resolve().parent / "training_log.json"
            today = datetime.date.today().isoformat()

            def _load():
                try:
                    return json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    return {}

            def _weekly(workouts):
                cut = (datetime.date.today()
                       - datetime.timedelta(days=6)).isoformat()
                return sum(1 for w in workouts if (w.get("d") or "") >= cut)

            if parsed.path in ("/training_weight", "/training_workout",
                               "/training_import"):
                if not self._peer_can_edit():
                    self._json_out({"ok": False, "error": "forbidden"}, 403)
                    return
                with _training_lock:
                    data = _load()
                    data.setdefault("weight_target_min_kg", 68)
                    weights = data.setdefault("weights", [])
                    workouts = data.setdefault("workouts", [])
                    if parsed.path == "/training_weight":
                        try:
                            kg = float((params.get("kg", [""])[0] or ""))
                        except Exception:
                            self._json_out({"ok": False,
                                            "error": "bad kg"}, 400)
                            return
                        if not (30 <= kg <= 200):
                            self._json_out({"ok": False,
                                            "error": "kg out of range"}, 400)
                            return
                        weights[:] = [w for w in weights
                                      if w.get("d") != today]
                        weights.append({"d": today, "kg": round(kg, 1)})
                        weights.sort(key=lambda w: w.get("d", ""))
                        del weights[:-120]
                        data["last_weight_kg"] = round(kg, 1)
                        data["last_weight_date"] = today
                    else:
                        wtype = (params.get("type", [""])[0] or "").strip()
                        if not wtype:
                            self._json_out({"ok": False,
                                            "error": "type required"}, 400)
                            return
                        wdate = today
                        if parsed.path == "/training_import":
                            d0 = (params.get("date", [""])[0] or "").strip()
                            if re.match(r"^\d{4}-\d{2}-\d{2}$", d0):
                                wdate = d0
                        entry = {"d": wdate, "t": wtype[:80]}
                        def _numf(k):
                            try:
                                v = float((params.get(k, [""])[0] or ""))
                                return round(v, 1) if v > 0 else None
                            except Exception:
                                return None
                        for qk, jk in (("dist_km", "km"), ("dur_min", "min"),
                                       ("hr_avg", "hr"), ("hr_max", "hrmax"),
                                       ("kcal", "kcal")):
                            v = _numf(qk)
                            if v is not None:
                                entry[jk] = v
                        if parsed.path == "/training_import":
                            entry["src"] = "health"
                            def _same(w, e):
                                if w.get("d") != e["d"] or w.get("t") != e["t"]:
                                    return False
                                # Match on the first numeric field BOTH sides
                                # actually have. Two workouts that both lack a
                                # field (e.g. no duration) are not "the same"
                                # just because they're both blank - only a
                                # genuine matching value counts as a duplicate.
                                for k in ("km", "min", "kcal", "hr"):
                                    wv, ev = w.get(k), e.get(k)
                                    if wv is not None and ev is not None:
                                        return abs(wv - ev) < 0.05
                                return False
                            dup = any(_same(w, entry) for w in workouts)
                            if dup:
                                self._json_out({"ok": True, "deduped": True})
                                return
                        workouts.append(entry)
                        workouts.sort(key=lambda w: w.get("d", ""))
                        del workouts[:-120]
                        data["last_workout_type"] = wtype[:80]
                        data["last_workout_date"] = wdate
                    data["weekly_workouts"] = _weekly(workouts)
                    p.write_text(json.dumps(data, ensure_ascii=False,
                                            indent=2), encoding="utf-8")
            with _training_lock:
                data = _load()
            self._json_out({
                "ok": True,
                "target": data.get("weight_target_min_kg", 68),
                "last_weight_kg": data.get("last_weight_kg"),
                "last_weight_date": data.get("last_weight_date"),
                "last_workout_type": data.get("last_workout_type"),
                "last_workout_date": data.get("last_workout_date"),
                "weekly_workouts": data.get("weekly_workouts", 0),
                "weights": (data.get("weights") or [])[-60:],
                "workouts": (data.get("workouts") or [])[-14:],
            })
        except Exception as e:
            try:
                self._json_out({"ok": False, "error": str(e)}, 500)
            except Exception:
                pass

    def _handle_training_photo(self):
        # v5.16f: upload a workout photo directly from the mobile Training
        # tile. Same Claude-vision extraction pipeline as the Telegram
        # path (v5.16e) - shares _extract_workout_from_image() and
        # _training_log_add_workout_from_extract().
        if not self._peer_can_edit():
            self._json_out({"ok": False, "error": "forbidden"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > 15000000:
            self._json_out({"ok": False, "error": "bad content length"}, 400)
            return
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            b64 = payload.get("image_b64", "")
            mime = payload.get("mime") or "image/jpeg"
            caption = (payload.get("caption") or "").strip()
            if not b64:
                self._json_out({"ok": False, "error": "no image"}, 400)
                return
            image_bytes = base64.b64decode(b64)
        except Exception as e:
            self._json_out({"ok": False,
                            "error": "bad request: " + str(e)}, 400)
            return
        when = (payload.get("date") or "").strip() or None
        if when:
            # v5.16q: optional backdate for forgotten uploads. Strict
            # ISO YYYY-MM-DD, never in the future, at most a year back.
            try:
                _d = datetime.date.fromisoformat(when)
                _t = datetime.date.today()
                if _d > _t or (_t - _d).days > 365:
                    raise ValueError("date out of range")
                when = _d.isoformat()
            except Exception:
                self._json_out({"ok": False, "error":
                                "bad date - use YYYY-MM-DD, not in the "
                                "future, at most a year back"}, 400)
                return
        extracted = _extract_workout_from_image(image_bytes, mime, caption)
        if not extracted:
            self._json_out({"ok": False, "error": "unreadable"})
            return
        if extracted.get("screen") == "day_summary":
            # v5.16r: daily-summary screens carry totals, not
            # workouts - logging them created fake "Walking"
            # entries. The page shows guidance for this code.
            self._json_out({"ok": False, "error": "day_summary"})
            return
        wlist = extracted.get("workouts") or []
        if not wlist:
            self._json_out({"ok": False, "error": "unreadable"})
            return
        entries = []
        for w in wlist:
            e = _training_log_add_workout_from_extract(w, src="upload",
                                                       when=when)
            if e:
                entries.append(e)
        if not entries:
            self._json_out({"ok": False, "error": "write failed"}, 500)
            return
        self._json_out({"ok": True, "entry": entries[0],
                        "entries": entries})

    def _handle_warwatch_headlines(self, parsed):
        # v36: unfurl up to 3 already-known source URLs for one WARWATCH
        # cluster into real titles, shown inside the WorldView intel card -
        # never opens an external site itself, so the "reading" experience
        # stays inside the app; a plain link is still offered for the full
        # original article if the person wants it.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            raw = params.get("urls", [""])[0]
            urls = [u for u in raw.split(",") if u.strip()][:3]
            results = _warwatch_headlines_for(urls)
            self._json_out({"ok": True, "results": results})
        except Exception as e:
            self._json_out({"ok": False, "error": str(e)}, 500)

    def _handle_geoloc_photo(self):
        # v5.16k: photo geolocation guess for the WorldView SCOUTING
        # tab. Same request shape and gating as /training_photo (JSON:
        # image_b64 + mime + optional caption), but routes to
        # _geoguess_photo() - the Claude-vision location guesser also
        # used by the Telegram photo-caption path.
        if not self._peer_can_edit():
            self._json_out({"ok": False, "error": "forbidden"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > 15000000:
            self._json_out({"ok": False, "error": "bad content length"}, 400)
            return
        try:
            raw = self.rfile.read(length)
            payload = json.loads(raw.decode("utf-8"))
            b64 = payload.get("image_b64", "")
            mime = payload.get("mime") or "image/jpeg"
            caption = (payload.get("caption") or "").strip()
            if not b64:
                self._json_out({"ok": False, "error": "no image"}, 400)
                return
            image_bytes = base64.b64decode(b64)
        except Exception as e:
            self._json_out({"ok": False,
                            "error": "bad request: " + str(e)}, 400)
            return
        compare = bool(payload.get("compare"))
        if compare:
            # v5.16n: run BOTH paths - the local trained model and the
            # Claude-vision guess - and return them side by side. Local
            # service down/unreachable just means "osv5m": null here,
            # exactly like the normal path's silent fallback.
            local_g = _osv5m_local_guess(image_bytes)
            claude_g = _geoguess_photo(image_bytes, mime, caption,
                                       use_local=False)
            fused_g = None
            if local_g is not None:
                fused_g = _geoloc_fusion_guess(image_bytes, mime,
                                               caption, local_g,
                                               blind=claude_g)
            primary = fused_g or local_g or claude_g
            if not primary:
                self._json_out({"ok": False, "error": "unreadable"})
                return
            self._json_out({"ok": True, "guess": primary,
                            "compare": {"osv5m": local_g,
                                        "claude": claude_g,
                                        "fusion": fused_g}})
            return
        guess = _geoguess_photo(image_bytes, mime, caption)
        if not guess:
            self._json_out({"ok": False, "error": "unreadable"})
            return
        self._json_out({"ok": True, "guess": guess})

    def _handle_todo(self, parsed):
        # v4.53: minimal task store shared by voice and the Achilles screen.
        try:
            # v4.67: allow read-only GET /todo from the LAN (phone can view the
            # list) but block the mutating actions from non-loopback origins so
            # a cross-site GET can't add/toggle/delete the user's tasks.
            if parsed.path != "/todo":
                _peer = self.client_address[0] if self.client_address else ""
                _ok = _peer in ("127.0.0.1", "::1", "localhost")
                if not _ok and "." in _peer:
                    try:
                        _oct = [int(x) for x in _peer.split(".")]
                        # Tailscale CGNAT 100.64.0.0/10 -> only the user's own devices
                        if _oct[0] == 100 and 64 <= _oct[1] <= 127:
                            _ok = True
                    except Exception:
                        pass
                if not _ok:
                    self.send_response(403)
                    self._cors_headers()
                    self.end_headers()
                    return
            params = urllib.parse.parse_qs(parsed.query)
            with _tasks_lock:
                tasks = _tasks_load()
                if parsed.path == "/todo_add":
                    text = (params.get("text", [""])[0] or "").strip()
                    if text:
                        tasks.append({"id": int(time.time() * 1000),
                                      "text": text, "done": False,
                                      "ts": time.time()})
                        _tasks_save(tasks)
                elif parsed.path == "/todo_toggle":
                    tid = int(params.get("id", ["0"])[0] or "0")
                    for t in tasks:
                        if t.get("id") == tid:
                            t["done"] = not t.get("done", False)
                    _tasks_save(tasks)
                elif parsed.path == "/todo_del":
                    tid = int(params.get("id", ["0"])[0] or "0")
                    tasks = [t for t in tasks if t.get("id") != tid]
                    _tasks_save(tasks)
            body = json.dumps({"tasks": tasks}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"tasks":[]}').encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    def _handle_planet(self, parsed):
        # v4.52: live news for a clicked planet in the Solar System scene.
        # One Claude call with web_search, cached per planet for 1 hour so
        # repeated clicks cost nothing.
        try:
            params = urllib.parse.parse_qs(parsed.query)
            name = (params.get("name", [""])[0] or "").strip().lower()
            lang = (params.get("lang", ["he"])[0] or "he").strip().lower()
            allowed = ("sun", "mercury", "venus", "earth", "moon", "mars",
                       "jupiter", "saturn", "uranus", "neptune")
            if name not in allowed:
                raise ValueError("unknown body: %s" % name)
            now = time.time()
            ck = name + ":" + ("he" if lang == "he" else "en")
            hit = _planet_news_cache.get(ck)
            if hit and (now - hit["ts"] < 3600) and hit["text"]:
                text = hit["text"]
            else:
                if not ANTHROPIC_API_KEY:
                    raise RuntimeError("no API key")
                client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                sys_p = (
                    "You are a space news desk. Use web_search to find the 3 "
                    "most interesting RECENT news items (missions, discoveries, "
                    "research - prefer the last month) about: " + name + ". "
                    "Then output ONLY a compact plain-text list of those 3 "
                    "items, one per line, each one short factual sentence. "
                    "No URLs, no numbering, no markdown. Write in "
                    + ("Hebrew" if lang == "he" else "English") + ".")
                tools = [{"type": "web_search_20250305",
                          "name": "web_search", "max_uses": 2}]
                msgs = [{"role": "user",
                         "content": "Latest news about " + name + ", please."}]
                r = None
                for _ in range(4):
                    r = client.messages.create(
                        model="claude-sonnet-5", max_tokens=450,
                        system=sys_p, messages=msgs, tools=tools)
                    msgs.append({"role": "assistant", "content": r.content})
                    if getattr(r, "stop_reason", None) == "tool_use":
                        continue
                    break
                parts = [b.text for b in r.content
                         if getattr(b, "type", None) == "text"]
                text = "\n".join(p.strip() for p in parts if p.strip()).strip()
                text = re.sub(r"https?://\S+", "", text).strip()
                if not text:
                    raise RuntimeError("empty news")
                _planet_news_cache[ck] = {"ts": now, "text": text}
            body = json.dumps({"name": name, "news": text}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self._cors_headers()
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            try:
                msg = ('{"error":' + json.dumps(str(e))
                       + ',"news":""}').encode("utf-8")
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self._cors_headers()
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass

    # silence per-request access logs
    def log_message(self, *args, **kwargs):
        pass


def _start_flights_proxy(port=7778):
    """Start the FLIGHTS proxy on a daemon thread. Idempotent - safe to call
    every time WorldView is opened. Returns True if the proxy is (now)
    listening, False if the bind failed."""
    global _flights_proxy_started
    with _flights_proxy_lock:
        if _flights_proxy_started:
            return True
        try:
            server = http.server.ThreadingHTTPServer(
                ("0.0.0.0", port), _FlightsProxyHandler
            )
        except OSError as e:
            print("[diag] flights proxy could not bind to %d: %r" % (port, e))
            return False
        th = threading.Thread(
            target=server.serve_forever, daemon=True,
            name="jarvis-flights-proxy",
        )
        th.start()
        _flights_proxy_started = True
        print("[diag] flights proxy listening on 0.0.0.0:%d (LAN)" % port)
        return True


# ===========================================================================
# SECURE TEMPORARY LIVE LOCATION SHARING (v4.68)
# ---------------------------------------------------------------------------
# A completely SEPARATE, minimal HTTP server (default 127.0.0.1:7779) whose
# handler defines ONLY the sharing/upload routes. There is deliberately NO
# code path from a share token to /keys, /flights, /vessels, /state or any
# other internal API - isolation is enforced by architecture, not by
# filtering. This is the ONLY server that gets exposed publicly through
# Tailscale Funnel (which proxies to 127.0.0.1, so a loopback bind keeps
# even the LAN out); :7777 (WorldView) and :7778 (flights/vessels/keys)
# stay private on the Tailnet.
#
#   GET  /share/<token>              -> share_location.html   (410 if expired)
#   GET  /api/share/<token>/location -> {lat, lon, updated_at} (410 if expired)
#   GET  /u/<owner_key>              -> share_upload.html      (owner only)
#   POST /api/location/update        -> store live fix (owner key required)
#
# The recipient can ONLY read live coordinates while the token is valid.
# ===========================================================================
_LOCATION_DIR = Path(__file__).resolve().parent
_LOCATION_STATE_FILE = str(_LOCATION_DIR / "location_state.json")
_SHARE_TOKENS_FILE = str(_LOCATION_DIR / "share_tokens.json")
_OWNER_KEY_FILE = str(_LOCATION_DIR / "location_owner_key.txt")
try:
    _LOCATION_SHARE_PORT = int(os.environ.get("LOCATION_SHARE_PORT", "7779"))
except Exception:
    _LOCATION_SHARE_PORT = 7779
# Loopback by default: Tailscale Funnel/serve proxies to 127.0.0.1, so the
# public HTTPS path still works while plain-LAN clients can't even connect.
_LOCATION_SHARE_BIND = (os.environ.get("LOCATION_SHARE_BIND") or "127.0.0.1").strip()

# Most recent live fix. Persisted to location_state.json so a restart keeps
# the last position until the phone pushes a fresh one.
_live_location = {"lat": None, "lon": None, "accuracy": None, "updated_at": None}
# token -> {"created_at": float, "expires_at": float}. Persisted so an active
# share survives a JARVIS restart.
_share_tokens = {}
_location_lock = threading.Lock()

_location_share_started = False
_location_share_lock = threading.Lock()
_location_funnel_started = False
_location_funnel_https = None  # 443 or 8443 once the funnel is configured
_owner_key_cache = None

# --- basic per-client rate limiting for the ONE public server --------------
# Fixed window per client: plenty for legit use (the viewer polls every 5s,
# the phone posts every ~3-5s) yet stops hammering/brute-force scripts.
# Behind Tailscale Funnel every connection arrives from the local tailscaled,
# so the real client is taken from X-Forwarded-For (set by the funnel proxy).
# Trusting that header is safe here BECAUSE the server binds loopback: anyone
# able to forge it is already local, i.e. the owner.
_RATE_WINDOW = 10.0   # seconds
_RATE_MAX = 120       # requests per client per window
_rate_lock = threading.Lock()
_rate_buckets = {}    # client -> [window_start, count]


def _rate_limited(handler):
    """True if this request should be rejected with 429."""
    fwd = handler.headers.get("X-Forwarded-For", "") or ""
    client = (fwd.split(",")[0].strip() or
              (handler.client_address[0] if handler.client_address else "?"))
    now = time.time()
    with _rate_lock:
        # keep the table bounded even under address-spoofing floods
        if len(_rate_buckets) > 4096:
            for k in [k for k, v in _rate_buckets.items()
                      if now - v[0] > _RATE_WINDOW]:
                _rate_buckets.pop(k, None)
        b = _rate_buckets.get(client)
        if b is None or now - b[0] > _RATE_WINDOW:
            _rate_buckets[client] = [now, 1]
            return False
        b[1] += 1
        return b[1] > _RATE_MAX

# Simple "This link has expired" page, served with HTTP 410 Gone.
_EXPIRED_SHARE_HTML = (
    "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
    "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
    "<title>Link expired</title><style>"
    "html,body{height:100%;margin:0}"
    "body{display:flex;align-items:center;justify-content:center;"
    "font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "background:#0b0f14;color:#e6edf3}"
    ".card{max-width:340px;padding:32px;text-align:center}"
    ".card h1{font-size:22px;margin:0 0 10px}"
    ".card p{color:#8b98a5;line-height:1.5;margin:0}"
    ".dot{font-size:44px;margin-bottom:8px}"
    "</style></head><body><div class=\"card\">"
    "<div class=\"dot\">\U0001F512</div>"
    "<h1>This link has expired</h1>"
    "<p>The live location share you are trying to open is no longer active.</p>"
    "</div></body></html>"
).encode("utf-8")


def _write_private(path, text):
    """Write text to path with owner-only (0600) permissions, so the owner key
    / active tokens are not readable by other local users on a shared host."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        raise
    # Tighten even if the file pre-existed with looser bits.
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _location_owner_key():
    """The secret that gates the uploader page and POST /api/location/update.
    Order: LOCATION_OWNER_KEY from .env, else a generated key persisted to
    location_owner_key.txt (gitignored). Cached after first resolution.
    To ROTATE a leaked key: delete location_owner_key.txt (or change the env
    var) and restart JARVIS - a fresh key is minted and the old uploader
    links stop working."""
    global _owner_key_cache
    if _owner_key_cache:
        return _owner_key_cache
    k = (os.environ.get("LOCATION_OWNER_KEY") or "").strip()
    if not k:
        try:
            if os.path.exists(_OWNER_KEY_FILE):
                with open(_OWNER_KEY_FILE, "r", encoding="utf-8") as f:
                    k = (f.read() or "").strip()
        except Exception:
            k = ""
    if not k:
        k = secrets.token_urlsafe(24)
        try:
            _write_private(_OWNER_KEY_FILE, k)
        except Exception:
            pass
    _owner_key_cache = k
    return k


def _persist_location_state():
    try:
        _write_private(_LOCATION_STATE_FILE, json.dumps(_live_location))
    except Exception:
        pass


def _persist_share_tokens():
    try:
        _write_private(_SHARE_TOKENS_FILE, json.dumps(_share_tokens))
    except Exception:
        pass


def _load_location_persisted():
    """Load last fix + still-valid tokens from disk. Called once at startup."""
    global _share_tokens
    try:
        if os.path.exists(_LOCATION_STATE_FILE):
            with open(_LOCATION_STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                for key in ("lat", "lon", "accuracy", "updated_at"):
                    if key in d:
                        _live_location[key] = d[key]
    except Exception:
        pass
    try:
        if os.path.exists(_SHARE_TOKENS_FILE):
            with open(_SHARE_TOKENS_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                now = time.time()
                _share_tokens = {
                    t: r for t, r in d.items()
                    if isinstance(r, dict) and float(r.get("expires_at", 0)) > now
                }
    except Exception:
        pass


def _create_share_token(minutes, kind="owner", extra=None):
    """Mint a cryptographically-secure token valid for `minutes` minutes.
    kind: "owner" (classic share of MY location), "join" (someone else
    broadcasts THEIR location to me), "view" (my viewer for a join).
    extra: dict merged into the record (e.g. {"join": <join_token>})."""
    now = time.time()
    tok = secrets.token_urlsafe(24)
    rec = {"created_at": now, "expires_at": now + minutes * 60.0,
           "kind": kind}
    if extra:
        rec.update(extra)
    with _location_lock:
        _share_tokens[tok] = rec
        # opportunistic prune of anything already expired
        for t in [t for t, r in _share_tokens.items()
                  if float(r.get("expires_at", 0)) <= now]:
            _share_tokens.pop(t, None)
        _persist_share_tokens()
    return tok


def _ct_equal(a, b):
    """Constant-time string equality (hmac.compare_digest over utf-8 bytes).
    Never raises on odd input - unequal instead."""
    try:
        return hmac.compare_digest(str(a).encode("utf-8"),
                                    str(b).encode("utf-8"))
    except Exception:
        return False


def _check_share_token(tok):
    """Return the token record if present AND unexpired, else None.
    Constant-time: the presented value is compared against EVERY stored token
    with hmac.compare_digest - no dict lookup, no early exit - so response
    timing cannot narrow a guess. Every expired token seen during the scan is
    pruned (memory + disk) so it can never be revived."""
    if not tok or not isinstance(tok, str):
        return None
    now = time.time()
    with _location_lock:
        match = None
        expired = []
        for t, r in _share_tokens.items():
            if float(r.get("expires_at", 0)) <= now:
                expired.append(t)
            elif _ct_equal(tok, t):
                match = t
        if expired:
            for t in expired:
                _share_tokens.pop(t, None)
            _persist_share_tokens()
        if match is None:
            return None
        return dict(_share_tokens[match])


def _share_token_key(tok):
    """Like _check_share_token but returns the REAL stored key (or None),
    so the caller can update the record under _location_lock. Same
    constant-time full-table scan; same opportunistic pruning."""
    if not tok or not isinstance(tok, str):
        return None
    now = time.time()
    with _location_lock:
        match = None
        expired = []
        for t, r in _share_tokens.items():
            if float(r.get("expires_at", 0)) <= now:
                expired.append(t)
            elif _ct_equal(tok, t):
                match = t
        if expired:
            for t in expired:
                _share_tokens.pop(t, None)
            _persist_share_tokens()
        return match


class _LocationShareHandler(http.server.BaseHTTPRequestHandler):
    """The ONLY public surface. Defines exactly the sharing/upload routes and
    nothing else, so a share token can never reach an internal endpoint."""

    server_version = "share/1.0"
    sys_version = ""  # never advertise the Python version on the public port

    def version_string(self):
        # Base class returns "server_version sys_version"; pin it so the public
        # Server header discloses neither the Python version nor a stray space.
        return "share/1.0"

    # This is the one PUBLICLY reachable server, so slow/partial requests must
    # not pin worker threads forever (slowloris). BaseHTTPRequestHandler
    # applies this as the per-connection socket timeout.
    timeout = 20

    # Both HTML pages are served BY this server, so every fetch they make is
    # same-origin: no CORS headers are needed, and none are sent - a foreign
    # web page gets nothing readable out of these endpoints.
    # Per-page Content-Security-Policy (belt over the SRI suspenders): even a
    # compromised CDN script could not exfiltrate the token/coordinates to an
    # attacker host, because connect-src/img-src only allow the tile servers.
    _CSP_VIEWER = ("default-src 'none'; base-uri 'none'; form-action 'none'; "
                   "frame-ancestors 'none'; "
                   "script-src 'unsafe-inline' https://unpkg.com; "
                   "style-src 'unsafe-inline' https://unpkg.com; "
                   "img-src data: blob: https://*.tile.openstreetmap.org "
                   "https://server.arcgisonline.com; "
                   "connect-src 'self' https://*.tile.openstreetmap.org "
                   "https://server.arcgisonline.com; "
                   "worker-src blob:; child-src blob:")
    _CSP_UPLOADER = ("default-src 'none'; base-uri 'none'; form-action 'none'; "
                     "frame-ancestors 'none'; "
                     "script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                     "connect-src 'self'")
    _CSP_PLAIN = ("default-src 'none'; base-uri 'none'; form-action 'none'; "
                  "frame-ancestors 'none'; style-src 'unsafe-inline'")

    def _sec_headers(self, csp=None):
        self.send_header("Cache-Control", "no-store")
        # Lock the page down: no sniffing, no framing, no referrer leakage
        # of the token to tile servers / CDNs / navigation targets.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", csp or self._CSP_PLAIN)

    def _send(self, code, body=b"", ctype="text/plain; charset=utf-8",
              csp=None):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self._sec_headers(csp)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if body:
                self.wfile.write(body)
        except Exception:
            pass

    def _serve_static(self, filename, csp):
        # Fixed filenames only - never a path derived from the request, so
        # directory traversal is impossible.
        try:
            body = (_LOCATION_DIR / filename).read_bytes()
        except Exception:
            self._send(500, b"error")
            return
        self._send(200, body, "text/html; charset=utf-8", csp=csp)

    def do_OPTIONS(self):
        try:
            self.send_response(204)
            self.send_header("Allow", "GET, POST, OPTIONS")
            self._sec_headers()
            self.end_headers()
        except Exception:
            pass

    def do_GET(self):
        if _rate_limited(self):
            self._send(429, b"Too many requests")
            return
        try:
            path = urllib.parse.urlparse(self.path).path
        except Exception:
            self._send(400, b"bad request")
            return

        # --- public share page ---------------------------------------------
        if path.startswith("/share/"):
            tok = path[len("/share/"):].strip("/")
            if _check_share_token(tok):
                self._serve_static("share_location.html", self._CSP_VIEWER)
            else:
                self._send(410, _EXPIRED_SHARE_HTML, "text/html; charset=utf-8")
            return

        # --- public live-location API (lat/lon/updated_at ONLY) ------------
        if path.startswith("/api/share/") and path.endswith("/location"):
            tok = path[len("/api/share/"):-len("/location")].strip("/")
            rec = _check_share_token(tok)
            if rec:
                if rec.get("kind") == "view":
                    # v4.95 reverse request: the viewer follows the fix
                    # uploaded by whoever opened the matching join link.
                    with _location_lock:
                        jrec = _share_tokens.get(rec.get("join") or "")
                        fix = (jrec or {}).get("fix") or {}
                        lat = fix.get("lat")
                        lon = fix.get("lon")
                        ua = fix.get("updated_at")
                    if jrec is None or float(jrec.get("expires_at", 0)) <= time.time():
                        self._send(410, b'{"error":"expired"}', "application/json")
                        return
                else:
                    with _location_lock:
                        lat = _live_location.get("lat")
                        lon = _live_location.get("lon")
                        ua = _live_location.get("updated_at")
                # A share exposes ONLY fixes from its own lifetime (plus a
                # short backward slack for "already broadcasting, then
                # shared"). A position persisted before this share existed -
                # e.g. yesterday's, restored from disk at startup - is never
                # revealed to a new recipient; the viewer shows "waiting for
                # a location fix" until a live one arrives.
                try:
                    fresh_since = float(rec.get("created_at", 0)) - 120.0
                except (TypeError, ValueError):
                    fresh_since = time.time()
                if ua is None or float(ua) < fresh_since:
                    lat = lon = ua = None
                payload = json.dumps({
                    "lat": lat, "lon": lon, "updated_at": ua,
                }).encode("utf-8")
                self._send(200, payload, "application/json")
            else:
                self._send(410, b'{"error":"expired"}', "application/json")
            return

        # --- owner-only uploader page (my phone) ---------------------------
        if path.startswith("/u/"):
            key = path[len("/u/"):].strip("/")
            if key and _ct_equal(key, _location_owner_key()):
                self._serve_static("share_upload.html", self._CSP_UPLOADER)
            else:
                self._send(404, b"Not found")
            return

        # --- reverse request: join page (the OTHER person's phone) ---------
        if path.startswith("/r/"):
            tok = path[len("/r/"):].strip("/")
            rec = _check_share_token(tok)
            if rec and rec.get("kind") == "join":
                self._serve_static("request_join.html", self._CSP_UPLOADER)
            else:
                self._send(410, _EXPIRED_SHARE_HTML, "text/html; charset=utf-8")
            return

        # --- reverse request: page metadata (expiry + optional owner link) --
        if path.startswith("/api/req/") and path.endswith("/meta"):
            tok = path[len("/api/req/"):-len("/meta")].strip("/")
            rec = _check_share_token(tok)
            if rec and rec.get("kind") == "join":
                payload = json.dumps({
                    "ok": True,
                    "expires_in": max(0, int(float(rec.get("expires_at", 0)) - time.time())),
                    "owner_url": rec.get("owner_url") or None,
                }).encode("utf-8")
                self._send(200, payload, "application/json")
            else:
                self._send(410, b'{"error":"expired"}', "application/json")
            return

        # Everything else is invisible. No /keys, no /flights, no /vessels.
        self._send(404, b"Not found")

    def do_POST(self):
        if _rate_limited(self):
            self._send(429, b"Too many requests")
            return
        try:
            path = urllib.parse.urlparse(self.path).path
        except Exception:
            self._send(400, b"bad request")
            return
        # --- reverse request: fix upload from whoever holds the join link ---
        if path.startswith("/api/req/") and path.endswith("/update"):
            tok = path[len("/api/req/"):-len("/update")].strip("/")
            key = _share_token_key(tok)
            valid = False
            if key is not None:
                with _location_lock:
                    valid = (_share_tokens.get(key, {}).get("kind") == "join")
            if not valid:
                self._send(410, b'{"error":"expired"}', "application/json")
                return
            try:
                length = int(self.headers.get("Content-Length", "0") or "0")
            except (TypeError, ValueError):
                length = 0
            if length > 10000:
                self._send(413, b'{"error":"too large"}', "application/json")
                return
            length = max(0, length)
            try:
                raw = self.rfile.read(length) if length else b""
                data = json.loads(raw.decode("utf-8")) if raw else {}
                lat = float(data["lat"])
                lon = float(data["lon"])
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    raise ValueError("coordinates out of range")
                acc = data.get("accuracy")
                try:
                    acc = float(acc) if acc is not None else None
                except (TypeError, ValueError):
                    acc = None
                with _location_lock:
                    if key in _share_tokens:
                        _share_tokens[key]["fix"] = {
                            "lat": lat, "lon": lon, "accuracy": acc,
                            "updated_at": time.time(),
                        }
                # in-memory only, on purpose: a restart ends the session
                # rather than reviving someone's old position from disk.
                self._send(200, b'{"ok":true}', "application/json")
            except Exception:
                self._send(400, b'{"ok":false}', "application/json")
            return

        if path != "/api/location/update":
            self._send(404, b"Not found")
            return
        # Owner key required - a share-token holder can NOT push fake fixes.
        key = self.headers.get("X-Owner-Key", "") or ""
        if not (key and _ct_equal(key, _location_owner_key())):
            self._send(403, b'{"error":"forbidden"}', "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except (TypeError, ValueError):
            length = 0
        if length > 10000:
            self._send(413, b'{"error":"too large"}', "application/json")
            return
        length = max(0, length)
        try:
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
            lat = float(data["lat"])
            lon = float(data["lon"])
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                raise ValueError("coordinates out of range")
            acc = data.get("accuracy")
            try:
                acc = float(acc) if acc is not None else None
            except (TypeError, ValueError):
                acc = None
            with _location_lock:
                _live_location["lat"] = lat
                _live_location["lon"] = lon
                _live_location["accuracy"] = acc
                _live_location["updated_at"] = time.time()
                _persist_location_state()
            self._send(200, b'{"ok":true}', "application/json")
        except Exception:
            self._send(400, b'{"ok":false}', "application/json")

    # silence per-request access logs
    def log_message(self, *args, **kwargs):
        pass


class _LocationShareServer(http.server.ThreadingHTTPServer):
    """ThreadingHTTPServer, minus the slow part. http.server.HTTPServer.
    server_bind() calls socket.getfqdn(host) to set self.server_name - a
    reverse-DNS lookup that can take minutes on machines where a VPN/
    MagicDNS setup (e.g. Tailscale) interferes with DNS resolution. This
    server binds to loopback only and never needs a real FQDN, so we call
    the grandparent (plain socketserver.TCPServer) bind instead and set
    server_name/server_port directly from the socket address (instant).
    v4.90: root cause of the multi-minute hang on share_live_location -
    WorldView's server never hit this because it runs as a separate
    subprocess (python -m http.server), not in-process on the voice thread.
    """
    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


def _start_location_share_server(port=None):
    """Start the isolated location-share server on a daemon thread. Idempotent.
    Returns True if it is (now) listening, False if the bind failed."""
    global _location_share_started
    if port is None:
        port = _LOCATION_SHARE_PORT
    with _location_share_lock:
        if _location_share_started:
            return True
        _load_location_persisted()
        owner_key = _location_owner_key()
        _loc_log("_start_location_share_server: binding %s:%d" %
                 (_LOCATION_SHARE_BIND, port))
        try:
            server = _LocationShareServer(
                (_LOCATION_SHARE_BIND, port), _LocationShareHandler
            )
            _loc_log("_start_location_share_server: bind OK")
        except OSError as e:
            print("[diag] location share server could not bind to %s:%d: %r"
                  % (_LOCATION_SHARE_BIND, port, e))
            return False
        threading.Thread(
            target=server.serve_forever, daemon=True,
            name="jarvis-location-share",
        ).start()
        _location_share_started = True
        print("[diag] location share server listening on %s:%d"
              % (_LOCATION_SHARE_BIND, port))
        # Never print the full owner key: stdout can end up in captured logs.
        # The full uploader URL reaches the owner over the paired Telegram
        # chat (share_live_location) and lives in location_owner_key.txt.
        print("[diag] location uploader ready at /u/%s... (key redacted; "
              "full link arrives via Telegram)" % owner_key[:6])
        return True


def _funnel_base_url():
    """Best-effort public HTTPS base URL for the share links. Order:
    LOCATION_FUNNEL_DOMAIN / FUNNEL_DOMAIN in .env, else the MagicDNS name
    from `tailscale status --json`. Returns None if it cannot be determined."""
    d = (os.environ.get("LOCATION_FUNNEL_DOMAIN")
         or os.environ.get("FUNNEL_DOMAIN") or "").strip()
    if d:
        d = d.rstrip("/")
        if not d.startswith("http"):
            d = "https://" + d
        return d
    try:
        _loc_log("_funnel_base_url: calling tailscale status --json")
        out = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True, text=True, timeout=6,
            creationflags=0x08000000,  # v4.88: CREATE_NO_WINDOW - this
            # process has no console (pythonw); spawning a console-mode
            # child without this flag is a known Windows stall/flash risk.
        )
        _loc_log("_funnel_base_url: tailscale status returned rc=%s" % out.returncode)
        if out.returncode == 0 and out.stdout:
            j = json.loads(out.stdout)
            dns = ((j.get("Self") or {}).get("DNSName") or "").strip().rstrip(".")
            if dns:
                base = "https://" + dns
                if _location_funnel_https and _location_funnel_https != 443:
                    base += ":%d" % _location_funnel_https
                return base
    except Exception as _e:
        _loc_log("_funnel_base_url: tailscale status FAILED: %r" % (_e,))
    return None


def _funnel_serve_conflict(https_port, target_port):
    """Return a description string if HTTPS :https_port on this node already
    serves something OTHER than our target_port, else None.
    Guards the documented Windows bug where `tailscale funnel <port>` silently
    OVERWRITES an existing `tailscale serve` route on the same HTTPS port
    (breaking private routes and producing 502 circular proxies). We inspect
    `tailscale serve status --json` first and refuse to clobber."""
    try:
        _loc_log("_funnel_serve_conflict: calling tailscale serve status --json")
        out = subprocess.run(["tailscale", "serve", "status", "--json"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=0x08000000)  # v4.88: CREATE_NO_WINDOW
        _loc_log("_funnel_serve_conflict: returned rc=%s" % out.returncode)
        if out.returncode != 0 or not (out.stdout or "").strip():
            return None  # no config to clobber (fresh node) or can't inspect
        st = json.loads(out.stdout)
    except Exception as _e:
        _loc_log("_funnel_serve_conflict: FAILED: %r" % (_e,))
        return None
    suffix = ":%d" % https_port
    ours = ":%d" % target_port
    for hostport, site in (st.get("Web") or {}).items():
        if not str(hostport).endswith(suffix):
            continue
        for hpath, h in ((site or {}).get("Handlers") or {}).items():
            proxy = str((h or {}).get("Proxy") or "")
            if proxy and not proxy.rstrip("/").endswith(ours):
                return "%s already proxies %r -> %r" % (hostport, hpath, proxy)
    return None


def _ensure_location_funnel(port=None):
    """Best-effort: ask Tailscale to Funnel ONLY the share port publicly.
    Tries HTTPS :443 first, falls back to :8443 if :443 is already serving
    another route (never overwrites - see _funnel_serve_conflict). WorldView
    on :7777 and the proxy on :7778 are never funneled. Non-fatal if the
    tailscale CLI is missing - run `tailscale funnel <port>` manually, or set
    LOCATION_FUNNEL_DOMAIN in .env."""
    global _location_funnel_started, _location_funnel_https
    if port is None:
        port = _LOCATION_SHARE_PORT
    if _location_funnel_started:
        return
    _location_funnel_started = True
    try:
        for https_port in (443, 8443):
            conflict = _funnel_serve_conflict(https_port, port)
            if conflict:
                print("[diag] tailscale funnel: not touching :%d (%s)"
                      % (https_port, conflict))
                continue
            cmd = ["tailscale", "funnel", "--bg"]
            if https_port != 443:
                cmd.append("--https=%d" % https_port)
            cmd.append(str(port))
            _loc_log("_ensure_location_funnel: calling %r" % (cmd,))
            res = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=20,
                                 creationflags=0x08000000)  # v4.88: CREATE_NO_WINDOW
            _loc_log("_ensure_location_funnel: returned rc=%s" % res.returncode)
            if res.returncode == 0:
                _location_funnel_https = https_port
                print("[diag] tailscale funnel active: https :%d -> "
                      "127.0.0.1:%d (share routes only; :7777/:7778 stay "
                      "private)" % (https_port, port))
                return
            print("[diag] tailscale funnel on :%d failed: %s"
                  % (https_port,
                     ((res.stderr or res.stdout or "").strip())[:200]))
        print("[diag] tailscale funnel NOT configured (no free HTTPS port). "
              "Run `tailscale funnel --https=8443 %d` manually or set "
              "LOCATION_FUNNEL_DOMAIN in .env." % port)
    except Exception as e:
        print("[diag] tailscale funnel not started (%r); set "
              "LOCATION_FUNNEL_DOMAIN in .env or run `tailscale funnel %d`"
              % (e, port))


def _ensure_location_sharing():
    """Bring up the share server + public Funnel exposure. Idempotent."""
    ok = _start_location_share_server()
    _ensure_location_funnel()
    return ok


def _share_live_location_impl(minutes=15):
    """Voice tool: mint a secure temporary link to the user's LIVE location and
    send it to the user's brother over Telegram. Exposes ONLY live coordinates
    while the token is valid; everything else stays private."""
    _loc_log("share_live_location CALLED minutes=%r" % (minutes,))
    try:
        minutes = int(round(float(minutes)))
    except Exception:
        minutes = 15
    minutes = max(1, min(minutes, 24 * 60))  # clamp 1 min .. 24 h

    _ensure_location_sharing()
    tok = _create_share_token(minutes)
    base = _funnel_base_url()
    owner_key = _location_owner_key()
    if base:
        share_url = "%s/share/%s" % (base, tok)
        upload_url = "%s/u/%s" % (base, owner_key)
    else:
        share_url = "http://localhost:%d/share/%s" % (_LOCATION_SHARE_PORT, tok)
        upload_url = "http://localhost:%d/u/%s" % (_LOCATION_SHARE_PORT, owner_key)

    with _location_lock:
        last = _live_location.get("updated_at")
    has_fresh_fix = bool(last) and (time.time() - float(last)) < 120
    _loc_log("share_live_location token minted, share_url=%s has_fresh_fix=%s" %
             (share_url, has_fresh_fix))

    # 3) send the public share URL to the brother via Telegram.
    brother = (os.environ.get("BROTHER_TELEGRAM_CHAT_ID") or "").strip()
    sent_to_brother = False
    if brother:
        sent_to_brother = telegram_send(
            "\U0001F4CD Live location — expires in %d min:\n%s"
            % (minutes, share_url),
            chat_id=brother,
        )

    # Nudge the owner's paired chat: the uploader link (so the phone starts
    # broadcasting) and/or the share link to forward if no brother is set.
    owner_lines = []
    if not sent_to_brother:
        owner_lines.append("Forward to your brother (%d min): %s"
                           % (minutes, share_url))
    if not has_fresh_fix:
        owner_lines.append("Open this on your phone to start broadcasting your "
                           "location:\n" + upload_url)
    if owner_lines:
        telegram_send("\n\n".join(owner_lines))

    # Spoken confirmation for the brain to phrase naturally.
    if not base:
        return ("I generated a %d-minute share link, sir, but no public Funnel "
                "domain is configured. Set LOCATION_FUNNEL_DOMAIN in the .env, "
                "or enable Tailscale Funnel on port %d. The link is %s"
                % (minutes, _LOCATION_SHARE_PORT, share_url))
    if sent_to_brother:
        tail = ("" if has_fresh_fix else " I've also sent you the uploader link "
                "— open it on your phone to start broadcasting.")
        return ("Done, sir. Your brother now has a live location link that "
                "expires in %d minutes.%s" % (minutes, tail))
    return ("I created a %d-minute link and sent it to you to forward, sir. "
            "Set BROTHER_TELEGRAM_CHAT_ID in the .env and I'll send it to your "
            "brother automatically next time." % minutes)


def share_live_location(minutes=15):
    """Wrapper: run the real implementation, and on ANY failure write the
    full traceback to location_diag.log and return an explicit failure
    message - so the model reports the truth instead of assuming success.
    (v4.93: added after the model confirmed 'link sent' 2 seconds after a
    call that had actually died silently.)"""
    try:
        return _share_live_location_impl(minutes)
    except Exception:
        import traceback
        _loc_log("share_live_location EXCEPTION:\n" + traceback.format_exc())
        return ("The location-share tool FAILED with an internal error, sir. "
                "No link was created and nothing was sent. The exact error was "
                "recorded in location_diag.log. Report this failure honestly - "
                "do not claim the location was shared.")


def _request_location_impl(minutes=15, show_me=False):
    """Reverse share: mint a JOIN link (send to the person you want to
    locate; their browser asks for consent and broadcasts) plus a VIEW
    link (the existing map page) for the owner. If show_me is True, the
    join page also offers a live link to the owner's location."""
    _loc_log("request_location CALLED minutes=%r show_me=%r" % (minutes, show_me))
    try:
        minutes = int(round(float(minutes)))
    except Exception:
        minutes = 15
    minutes = max(1, min(minutes, 24 * 60))

    _ensure_location_sharing()
    base = _funnel_base_url()

    extra = {}
    owner_view_url = None
    if show_me:
        # A standard owner-share token, embedded in the join page, so the
        # other person can see the owner too. Only minted when asked.
        otok = _create_share_token(minutes, kind="owner")
        owner_view_url = ("%s/share/%s" % (base, otok)) if base else (
            "http://localhost:%d/share/%s" % (_LOCATION_SHARE_PORT, otok))
        extra["owner_url"] = owner_view_url

    jtok = _create_share_token(minutes, kind="join", extra=extra)
    vtok = _create_share_token(minutes, kind="view", extra={"join": jtok})

    if base:
        join_url = "%s/r/%s" % (base, jtok)
        view_url = "%s/share/%s" % (base, vtok)
    else:
        join_url = "http://localhost:%d/r/%s" % (_LOCATION_SHARE_PORT, jtok)
        view_url = "http://localhost:%d/share/%s" % (_LOCATION_SHARE_PORT, vtok)
    _loc_log("request_location minted join=%s view=%s show_me=%s" %
             (join_url, view_url, show_me))

    lines = ["Send this to the person you want to locate (%d min):\n%s"
             % (minutes, join_url),
             "Your live map of them:\n%s" % view_url]
    if show_me:
        lines.append("Note: the page they open also lets them see YOUR "
                     "location (you asked to share it back). Open your "
                     "uploader link if you aren't broadcasting yet.")
    telegram_send("\n\n".join(lines))

    if not base:
        return ("I created the request links, sir, but no public Funnel "
                "domain is active, so they only work on your own network. "
                "Enable Tailscale Funnel on port %d for public access."
                % _LOCATION_SHARE_PORT)
    back = (" They will also be able to see your location, as requested."
            if show_me else
            " Your own location stays hidden from them.")
    return ("Done, sir. I sent you two links on Telegram: forward the "
            "first to whoever you want to locate - when they open it and "
            "approve, their live position appears on your map link for "
            "%d minutes.%s" % (minutes, back))


def request_location(minutes=15, show_me=False):
    """Honest-failure wrapper - same contract as share_live_location."""
    try:
        return _request_location_impl(minutes, show_me)
    except Exception:
        import traceback
        _loc_log("request_location EXCEPTION:\n" + traceback.format_exc())
        return ("The location-request tool FAILED with an internal error, "
                "sir. No links were created. The exact error was recorded "
                "in location_diag.log. Report this failure honestly - do "
                "not claim any link was sent.")


_geoloc_baseline_proc = None


def _ensure_geoloc_baseline():
    """v5.16o: start the local trained geolocation model service
    (geoloc_baseline/geoloc_baseline_server.py, port 8850, localhost
    only) in the background if it is installed and not already
    running - same windowless pattern as the WorldView server below.
    Silent no-op when not installed; port check prevents a double
    spawn when the manual START window is already open; any failure
    here never affects ACHILLES (the caller of the model,
    _osv5m_local_guess, falls back to Claude vision on its own).
    Output goes to geoloc_baseline/geoloc_baseline.log."""
    global _geoloc_baseline_proc
    try:
        if _wv_port_in_use(8850):
            return True
        base = Path(__file__).resolve().parent / "geoloc_baseline"
        venv_py = base / "venv" / "Scripts" / "python.exe"
        server = base / "geoloc_baseline_server.py"
        if not venv_py.exists() or not server.exists():
            return False
        creationflags = 0x08000000 if os.name == "nt" else 0
        log = open(base / "geoloc_baseline.log", "ab")
        _geoloc_baseline_proc = subprocess.Popen(
            [str(venv_py), str(server)],
            cwd=str(base),
            stdout=log,
            stderr=log,
            creationflags=creationflags,
            close_fds=True,
        )
        return True
    except Exception as e:
        print("[diag] failed to spawn geoloc baseline service:", repr(e))
        return False


# --- v5.23 guarded static server -------------------------------------------
# The page server used to be a bare "python -m http.server" over the whole
# project folder. Directory listing was on, so anything on the tailnet could
# browse to / and download .env, credentials.json, every backup and the
# source itself. The pages are public by design; the folder they live in is
# not, and those two were never separated.
#
# This serves the same folder through an allowlist instead: only the file
# types a page actually needs, no directory listings, no dotfiles, and no
# path traversal. An allowlist is used rather than a blocklist so that a new
# secret dropped into the folder tomorrow is refused by default.
_STATIC_SERVER_SRC = '''
import os, sys, posixpath, urllib.parse, http.server, socketserver

ROOT = os.path.abspath(sys.argv[2])
PORT = int(sys.argv[1])
ALLOWED_EXT = {".html", ".htm", ".css", ".js", ".mjs", ".map",
               ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
               ".woff", ".woff2", ".ttf", ".mp3", ".webmanifest"}
# .json is NOT allowed wholesale - credentials.json and anthropic_usage.json
# both end in .json. Only files a page genuinely fetches are named here.
ALLOWED_NAMES = {"countries.geo.json", "manifest.json", "site.webmanifest"}

class Guarded(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _permitted(self, path):
        rel = urllib.parse.urlparse(path).path
        rel = urllib.parse.unquote(rel)
        if rel.endswith("/"):
            return False          # no directory listings, ever
        name = posixpath.basename(rel)
        if not name or name.startswith("."):
            return False          # .env and friends
        if ".." in rel.split("/"):
            return False          # traversal
        if name in ALLOWED_NAMES:
            return True
        return os.path.splitext(name)[1].lower() in ALLOWED_EXT

    def send_head(self):
        if not self._permitted(self.path):
            self.send_error(404, "Not found")
            return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404, "Not found")
        return None

    def log_message(self, *a):
        pass

class Threaded(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

Threaded(("0.0.0.0", PORT), Guarded).serve_forever()
'''

def _write_static_server(files_dir):
    """Drop the guarded server next to the pages and return its path."""
    p = Path(files_dir) / "_static_server.py"
    try:
        p.write_text(_STATIC_SERVER_SRC, encoding="utf-8")
        return str(p)
    except Exception as e:
        print("[diag] could not write the guarded static server:", repr(e))
        return None


def _ensure_worldview_server(files_dir, port=7777):
    """Ensure a local HTTP server is serving WorldView at 127.0.0.1:port.
    Starts python -m http.server in the background if nothing is listening yet.
    Returns True on success, False on failure."""
    global _worldview_server_proc
    _start_flights_proxy()
    _start_vessels_relay()
    _start_warwatch_relay()
    _ensure_geoloc_baseline()
    if _wv_port_in_use(port):
        return True
    try:
        creationflags = 0
        if os.name == "nt":
            # CREATE_NO_WINDOW - no console flash on Windows
            creationflags = 0x08000000
        guard = _write_static_server(files_dir)
        cmd = ([sys.executable, guard, str(port), str(files_dir)] if guard
               else [sys.executable, "-m", "http.server", str(port),
                     "--bind", "0.0.0.0"])
        _worldview_server_proc = subprocess.Popen(
            cmd,
            cwd=str(files_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
    except Exception as e:
        print("[diag] failed to spawn WorldView server:", repr(e))
        return False
    # Poll up to 3 seconds for the server to come up
    for _ in range(30):
        if _wv_port_in_use(port):
            return True
        time.sleep(0.1)
    print("[diag] WorldView server did not become reachable within 3s")
    return False

def open_worldview():
    """Open the WorldView 3D globe in Edge --app mode, served over a local
    HTTP server on 127.0.0.1:7777. Google Maps JavaScript and Photorealistic
    3D Tiles refuse to load from file:// origins (Chromium treats them as
    unique opaque security origins), so JARVIS spawns a background
    python -m http.server in the files directory the first time the user
    asks to open WorldView, reuses it across subsequent opens in the same
    session, and points Edge at http://localhost:7777/worldview.html.
    Falls back to the default browser if Edge is not at the standard paths.
    Returns a short status string for the brain to phrase naturally."""
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "worldview.html"
    if not path.exists():
        return "WorldView file not found, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local WorldView server, sir. Try restarting JARVIS."
    # v4.53: if the Achilles screen is open, dive cinematically through
    # the solar system into Earth instead of spawning a separate window.
    if time.time() - _achilles_state.get("last_poll", 0.0) < 3.0:
        _achilles_state["scene"] = "dive"
        _achilles_state["ts"] = time.time()
        return "Diving to Earth, sir."
    # Cache-buster so Edge always reads the latest build, never a stale page
    url = "http://localhost:7777/worldview.html?t=" + str(int(time.time()))
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen(
                    [exe, "--app=" + url],
                    close_fds=True,
                )
                return "Opening WorldView, sir."
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back to default browser:", repr(e))
                break
    try:
        webbrowser.open(url)
        return "Opening WorldView, sir."
    except Exception as e:
        return "Failed to open WorldView: %s" % e

def open_hermes():
    """Open HERMES, the financial/investment terminal (hermes.html, formerly
    aleph.html), in Edge --app mode over the same local :7777 server that
    serves WorldView. Mirrors open_worldview: ensures the server is up, then
    points Edge at the terminal URL. Falls back to the default browser, and
    to the legacy aleph.html filename if hermes.html isn't deployed yet.
    Returns a short status string for the brain to phrase naturally."""
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "hermes.html"
    served_name = "hermes.html"
    if not path.exists():
        legacy = files_dir / "aleph.html"
        if legacy.exists():
            path, served_name = legacy, "aleph.html"
        else:
            return "HERMES terminal file not found, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local server, sir. Try restarting JARVIS."
    url = "http://localhost:7777/" + served_name + "?t=" + str(int(time.time()))
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url], close_fds=True)
                return "Opening HERMES, sir."
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back to default browser:", repr(e))
                break
    try:
        webbrowser.open(url)
        return "Opening HERMES, sir."
    except Exception as e:
        return "Failed to open HERMES: %s" % e

def open_roadmap():
    """Open Mission Control - the project roadmap/status dashboard - in Edge
    --app mode, served by the same local HTTP server as WorldView (port 7777).
    Returns a short status string for the brain to phrase naturally."""
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "roadmap.html"
    if not path.exists():
        return "Roadmap file not found, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local server, sir. Try restarting JARVIS."
    url = "http://localhost:7777/roadmap.html?t=" + str(int(time.time()))
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url], close_fds=True)
                return "Opening Mission Control, sir."
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back:", repr(e))
                break
    try:
        webbrowser.open(url)
        return "Opening Mission Control, sir."
    except Exception as e:
        return "Failed to open the roadmap: %s" % e

# --- v4.53: tasks store (tasks.json, shared by voice + Achilles screen) -----
def _tasks_path():
    return Path(__file__).resolve().parent / "tasks.json"

def _tasks_load():
    try:
        with open(_tasks_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _tasks_save(tasks):
    try:
        with open(_tasks_path(), "w", encoding="utf-8") as f:
            json.dump(tasks, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("[diag] tasks.json save failed:", repr(e))

def todo_add_voice(text, lang="he"):
    """Add a task from a voice/typed command and confirm briefly."""
    text = (text or "").strip().strip('.')
    if not text:
        return "מה להוסיף לרשימה, אדוני?" if lang == "he" else "Add what, sir?"
    with _tasks_lock:
        tasks = _tasks_load()
        tasks.append({"id": int(time.time() * 1000), "text": text,
                      "done": False, "ts": time.time()})
        _tasks_save(tasks)
    n = len([t for t in tasks if not t.get("done")])
    if lang == "he":
        return "נוסף: %s. %d משימות פתוחות, אדוני." % (text, n)
    return "Added: %s. %d open tasks, sir." % (text, n)

def _open_screen_reply(result, he):
    """v5.19: the open_* helpers answer in English. When the command was
    spoken in Hebrew, hand back a Hebrew confirmation - but ONLY for the
    exact known success strings. Anything else is passed through word for
    word, so a real failure is never masked by a cheerful translation."""
    if not he:
        return result
    return {
        "Opening HERMES, sir.":
            "\u05e4\u05d5\u05ea\u05d7 \u05d0\u05ea \u05d4\u05e8\u05de\u05e1, \u05d0\u05d3\u05d5\u05e0\u05d9.",
        "Opening WorldView, sir.":
            "\u05e4\u05d5\u05ea\u05d7 \u05d0\u05ea \u05d5\u05d5\u05e8\u05dc\u05d3\u05d5\u05d5\u05d9\u05d5, \u05d0\u05d3\u05d5\u05e0\u05d9.",
        "Opening Mission Control, sir.":
            "\u05e4\u05d5\u05ea\u05d7 \u05d0\u05ea \u05de\u05e4\u05ea \u05d4\u05d3\u05e8\u05db\u05d9\u05dd, \u05d0\u05d3\u05d5\u05e0\u05d9.",
    }.get((result or "").strip(), result)


def open_portal():
    """v4.61: double-click on the floating hole -> FULLSCREEN portal.
    Opens achilles.html with the full UI (ui=full) in a dedicated Edge
    profile so --start-fullscreen is always honored. In the portal:
    Earth button dives into WorldView, Solar System opens the planets.
    Exit fullscreen with F11; close with Alt+F4."""
    files_dir = Path(__file__).resolve().parent
    try:
        _ensure_worldview_server(files_dir, port=7777)
    except Exception:
        pass
    url = ("http://localhost:7777/achilles.html?scene=core&ui=full&t="
           + str(int(time.time())))
    prof = str(files_dir / ".portal_profile")
    args = ["--user-data-dir=" + prof, "--no-first-run",
            "--no-default-browser-check", "--start-fullscreen",
            "--app=" + url]
    for exe in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.isfile(exe):
            try:
                subprocess.Popen([exe] + args)
                return
            except Exception:
                pass
    try:
        os.startfile(url)
    except Exception:
        pass


def open_achilles(scene="core", face=False):
    """v4.52: Open the Achilles Core screen (achilles.html) - the WebGL
    black hole + solar system - in Edge --app mode on the same local server
    as WorldView (:7777). If the page is ALREADY open (it heartbeats /state
    every ~600ms), just flip the scene instead of spawning a second window.
    Returns a short status string for the brain to phrase naturally."""
    scene = scene if scene in ("core", "solar", "todo") else "core"
    files_dir = Path(__file__).resolve().parent
    path = files_dir / "achilles.html"
    if not path.exists():
        return "The Achilles screen file is missing, sir. Expected at: %s" % path
    if not _ensure_worldview_server(files_dir, port=7777):
        return "Failed to start the local server, sir. Try restarting me."
    # already-open page? (heartbeat within the last 3 seconds)
    _achilles_state["scene"] = scene
    _achilles_state["ts"] = time.time()
    if time.time() - _achilles_state.get("last_poll", 0.0) < 3.0:
        return {"solar": "Switching to the solar system, sir.",
                "todo": "Bringing up your task list, sir.",
                "core": "Bringing up the core, sir."}[scene]
    url = ("http://localhost:7777/achilles.html?scene=" + scene
           + "&t=" + str(int(time.time())))
    # v4.56: face mode = a SMALL widget window (like the old orb).
    # Edge ignores --window-size when the main browser is already running,
    # so the face gets its OWN profile (= its own process) which always
    # respects size and position. 420x500 at the orb's old spot.
    args_extra = []
    if face:
        try:
            import ctypes
            _sw = ctypes.windll.user32.GetSystemMetrics(0)
        except Exception:
            _sw = 1920
        _prof = str(files_dir / ".face_profile")
        args_extra = ["--user-data-dir=" + _prof,
                      "--no-first-run", "--no-default-browser-check",
                      "--window-size=420,500",
                      "--window-position=%d,60" % max(0, _sw - 450)]
    edge_candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for exe in edge_candidates:
        if os.path.exists(exe):
            try:
                subprocess.Popen([exe, "--app=" + url] + args_extra,
                                 close_fds=True)
                return {"solar": "Opening the solar system, sir.",
                        "todo": "Opening your task list, sir.",
                        "core": "Opening the core, sir."}[scene]
            except Exception as e:
                print("[diag] Edge --app launch failed, falling back:", repr(e))
                break
    try:
        webbrowser.open(url)
        return {"solar": "Opening the solar system, sir.",
                "todo": "Opening your task list, sir.",
                "core": "Opening the core, sir."}[scene]
    except Exception as e:
        return "Failed to open the Achilles screen: %s" % e

# --- Google Places + Directions ---------------------------------------------
def _gmaps_get(url, params, timeout=12):
    """GET against a Google Maps endpoint and parse the JSON. Returns
    (data_dict, error_string). Never throws."""
    if not GOOGLE_MAPS_API_KEY:
        return None, "Google Maps API key missing from .env (GOOGLE_MAPS_API_KEY)."
    params = dict(params)
    params["key"] = GOOGLE_MAPS_API_KEY
    full = url + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(full, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        return None, f"Network error contacting Google Maps: {e}"
    except Exception as e:
        return None, f"Unexpected error: {e}"
    status = data.get("status", "")
    if status not in ("OK", "ZERO_RESULTS"):
        return None, f"Google Maps returned status {status}: {data.get('error_message','')}"
    return data, None

def find_places(query, max_results=5):
    """Search Google Places (Text Search) for restaurants/cafes/shops/etc.
    Biased to Israel (Alfei Menashe area). Returns a short summary string the
    brain can read aloud, listing name, rating, status and address."""
    if not query or not query.strip():
        return "Please tell me what kind of place you're looking for, sir."
    # Bias the search to Alfei Menashe (~50 km covers most of central Israel
    # including Tel Aviv, Petah Tikva, Kfar Saba, etc.). Hebrew queries work too.
    params = {
        "query": query.strip(),
        "location": "32.1772,34.9947",   # Alfei Menashe approx
        "radius": "50000",
        "region": "il",
        "language": "iw",                # results in Hebrew where available
    }
    data, err = _gmaps_get(
        "https://maps.googleapis.com/maps/api/place/textsearch/json", params)
    if err:
        return f"Place search failed: {err}"
    results = data.get("results") or []
    if not results:
        return f"No places found in Israel matching '{query}'."
    out = []
    for p in results[:max_results]:
        name = p.get("name", "?")
        addr = p.get("formatted_address", "")
        rating = p.get("rating")
        ratings_n = p.get("user_ratings_total")
        oh = p.get("opening_hours", {})
        open_now = oh.get("open_now")
        bits = [name]
        if rating is not None:
            bits.append(f"{rating}/5"
                        + (f" ({ratings_n} reviews)" if ratings_n else ""))
        if open_now is True:
            bits.append("open now")
        elif open_now is False:
            bits.append("closed now")
        if addr:
            bits.append(addr)
        out.append(" — ".join(bits))
    return "Top results:\n- " + "\n- ".join(out)

def get_directions(destination, origin=None):
    """Get driving directions + live travel time from origin to destination
    using Google Directions. Defaults the origin to home (Alfei Menashe).
    Returns a short readable summary string."""
    if not destination or not destination.strip():
        return "Where would you like to go, sir?"
    origin = (origin or HOME_ADDRESS).strip()
    params = {
        "origin": origin,
        "destination": destination.strip(),
        "mode": "driving",
        "departure_time": "now",      # gives duration_in_traffic
        "traffic_model": "best_guess",
        "region": "il",
        "language": "iw",
    }
    data, err = _gmaps_get(
        "https://maps.googleapis.com/maps/api/directions/json", params)
    if err:
        return f"Directions failed: {err}"
    routes = data.get("routes") or []
    if not routes:
        return f"No driving route found from {origin} to {destination}."
    leg = routes[0]["legs"][0]
    dist = leg.get("distance", {}).get("text", "?")
    dur = leg.get("duration", {}).get("text", "?")
    dur_traffic = leg.get("duration_in_traffic", {}).get("text")
    start_addr = leg.get("start_address", origin)
    end_addr = leg.get("end_address", destination)
    summary = (routes[0].get("summary") or "").strip()
    line = f"From {start_addr} to {end_addr}: {dist}, normally {dur}"
    if dur_traffic:
        line += f", with current traffic about {dur_traffic}"
    if summary:
        line += f". Route via {summary}."
    else:
        line += "."
    return line

# --- Google Calendar ---------------------------------------------------------
def _calendar_service():
    """Return an authorized Calendar service, or None if not connected.
    Handles the OAuth dance: uses token.json if present, refreshes it if expired,
    or runs the one-time browser sign-in using credentials.json."""
    if not HAVE_GCAL:
        print("Calendar: Google libraries not installed.")
        return None
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        print("Calendar: credentials.json not found in folder.")
        return None
    creds = None
    try:
        if os.path.exists(CAL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CAL_TOKEN_FILE, CAL_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CAL_CREDENTIALS_FILE, CAL_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(CAL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception as e:
        print("Calendar auth error:", e)
        return None

def calendar_read(time_min=None, time_max=None, max_results=10):
    """List upcoming events. Defaults to the next 7 days if no range given."""
    svc = _calendar_service()
    if svc is None:
        return ("Calendar not connected. Add credentials.json and install the "
                "Google libraries to enable it, sir.")
    try:
        # Google's API needs RFC3339 times WITH a timezone. The brain sometimes
        # sends a naive time like "2026-05-26T00:00:00" (no Z, no offset), which
        # Google rejects as a 400 Bad Request. So we attach the machine's local
        # (Israel) offset to any naive time before sending it.
        now = datetime.datetime.now(datetime.timezone.utc)
        local_tz = datetime.datetime.now().astimezone().tzinfo  # DST-aware local offset

        def _tz(s):
            if not s:
                return None
            s = s.strip()
            if s.endswith("Z") or re.search(r'[+\-]\d{2}:?\d{2}$', s):
                return s  # already has a timezone -> leave it as-is
            try:
                d = datetime.datetime.fromisoformat(s)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=local_tz)
                return d.isoformat()
            except Exception:
                return s

        tmin = _tz(time_min) or now.isoformat()
        tmax = _tz(time_max) or (now + datetime.timedelta(days=7)).isoformat()
        res = svc.events().list(calendarId="primary", timeMin=tmin, timeMax=tmax,
                                singleEvents=True, orderBy="startTime",
                                maxResults=max_results).execute()
        items = res.get("items", [])
        if not items:
            return "No events found in that period."
        lines = []
        for e in items:
            s = e["start"].get("dateTime", e["start"].get("date", ""))
            eid = e.get("id", "")
            lines.append(f"[id={eid}] {s}: {e.get('summary', '(no title)')}")
        return "Events:\n" + "\n".join(lines)
    except Exception as e:
        # Print the REAL reason to the console so we can actually see it.
        print("Calendar read error:", repr(e))
        return f"Failed to read calendar: {e}"

def calendar_add(summary, start_iso, end_iso=None, location=None, description=None):
    """Create an event. start_iso/end_iso are ISO datetimes like
    2026-05-26T16:00:00. If end is omitted, the event lasts one hour."""
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not summary or not start_iso:
        return "I need at least a title and a start time."
    try:
        if not end_iso:
            st = datetime.datetime.fromisoformat(start_iso)
            end_iso = (st + datetime.timedelta(hours=1)).isoformat()
        body = {
            "summary": summary,
            "start": {"dateTime": start_iso, "timeZone": CAL_TIMEZONE},
            "end": {"dateTime": end_iso, "timeZone": CAL_TIMEZONE},
        }
        if location:
            body["location"] = location
        if description:
            body["description"] = description
        ev = svc.events().insert(calendarId="primary", body=body).execute()
        _record_action("calendar_add",
                       {"event_id": ev.get("id", ""), "summary": summary})
        return f"Event '{summary}' added for {start_iso}."
    except Exception as e:
        print("Calendar add error:", repr(e))
        return f"Failed to add event: {e}"

def calendar_delete(event_id):
    """Delete an event by its Google Calendar event id. Returns a status string."""
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not event_id:
        return "I need the event id to delete, sir."
    try:
        # v4.29: cache the event body before deletion so undo can re-insert it
        cached_body = None
        try:
            ev = svc.events().get(calendarId="primary",
                                  eventId=event_id).execute()
            cached_body = {k: v for k, v in ev.items()
                           if k in ("summary", "description", "location",
                                    "start", "end", "attendees",
                                    "reminders", "colorId")}
        except Exception:
            cached_body = None
        svc.events().delete(calendarId="primary", eventId=event_id).execute()
        if cached_body:
            _record_action("calendar_delete", {"body": cached_body})
        return "Event deleted, sir."
    except Exception as e:
        print("Calendar delete error:", repr(e))
        return f"Failed to delete event: {e}"

def calendar_update(event_id, summary=None, start_iso=None, end_iso=None,
                    location=None, description=None):
    """Patch an existing event. Only the fields explicitly provided are changed;
    everything else stays as it is. Times are ISO datetimes."""
    svc = _calendar_service()
    if svc is None:
        return "Calendar not connected, sir."
    if not event_id:
        return "I need the event id to update, sir."
    body = {}
    if summary:
        body["summary"] = summary
    if start_iso:
        body["start"] = {"dateTime": start_iso, "timeZone": CAL_TIMEZONE}
    if end_iso:
        body["end"] = {"dateTime": end_iso, "timeZone": CAL_TIMEZONE}
    if location is not None:
        body["location"] = location
    if description is not None:
        body["description"] = description
    if not body:
        return "Nothing to change, sir."
    try:
        svc.events().patch(calendarId="primary", eventId=event_id,
                           body=body).execute()
        return "Event updated, sir."
    except Exception as e:
        print("Calendar update error:", repr(e))
        return f"Failed to update event: {e}"

# --- Gmail -------------------------------------------------------------------
def _gmail_service():
    """Return an authorized Gmail service, or None if not connected. Uses the
    SAME token.json/credentials.json as the calendar (shared Google login)."""
    if not HAVE_GCAL:
        print("Gmail: Google libraries not installed.")
        return None
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        print("Gmail: credentials.json not found in folder.")
        return None
    creds = None
    try:
        if os.path.exists(CAL_TOKEN_FILE):
            creds = Credentials.from_authorized_user_file(CAL_TOKEN_FILE, GOOGLE_SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    CAL_CREDENTIALS_FILE, GOOGLE_SCOPES)
                creds = flow.run_local_server(port=0)
            with open(CAL_TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as e:
        print("Gmail auth error:", repr(e))
        return None

def _gmail_header(msg, name):
    """Pull a header value (e.g. 'From', 'Subject') from a Gmail message."""
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""

def _looks_like_spam(subject, sender, snippet):
    """Aggressive (v3.8): flags promotions/newsletters too. Anything carrying an
    unsubscribe marker counts, plus the older strong-junk signals. JARVIS still
    ASKS the user before moving/blocking anything, so this only decides what to
    PROPOSE."""
    blob = (subject + " " + sender + " " + snippet).lower()
    # Newsletters/promotions almost always include an unsubscribe line.
    if "unsubscribe" in blob:
        return True
    hits = sum(1 for w in GMAIL_SPAM_HINTS if w in blob)
    if hits >= 2:
        return True
    if any(w in blob for w in ("sale", "% off", "discount", "deal", "promo",
                               "newsletter", "offer")):
        return True
    return False

def _email_address_only(sender):
    """Extract just the address from a From header like 'Name <a@b.com>'."""
    m = re.search(r'<([^>]+)>', sender or "")
    if m:
        return m.group(1).strip().lower()
    return (sender or "").strip().lower()

def gmail_read(max_results=12):
    """Read recent inbox emails and return a compact list the model can
    summarise out loud: sender, subject, and a short snippet for each."""
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    try:
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
        ids = [m["id"] for m in res.get("messages", [])]
        if not ids:
            return "Your inbox is empty, sir."
        lines = []
        for mid in ids:
            msg = svc.users().messages().get(
                userId="me", id=mid, format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            sender = _gmail_header(msg, "From")
            subject = _gmail_header(msg, "Subject") or "(no subject)"
            snippet = (msg.get("snippet", "") or "")[:120]
            lines.append(f"From {sender} | {subject} | {snippet}")
        return ("Here are the latest %d emails. Summarise them briefly for the "
                "user by voice (who, about what, anything urgent):\n" % len(lines)
                + "\n".join(lines))
    except Exception as e:
        print("Gmail read error:", repr(e))
        return f"Failed to read email: {e}"

def gmail_spam_review(max_results=25):
    """Scan recent inbox mail, flag likely spam, and STAGE it (does NOT move
    anything). Returns a list for JARVIS to read out and ask for confirmation.
    The actual move happens only in gmail_move_spam after the user says yes."""
    global _gmail_pending_spam
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    try:
        res = svc.users().messages().list(
            userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
        ids = [m["id"] for m in res.get("messages", [])]
        flagged = []
        for mid in ids:
            msg = svc.users().messages().get(
                userId="me", id=mid, format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            sender = _gmail_header(msg, "From")
            subject = _gmail_header(msg, "Subject") or "(no subject)"
            snippet = msg.get("snippet", "") or ""
            if _looks_like_spam(subject, sender, snippet):
                flagged.append({"id": mid, "from": sender,
                                "addr": _email_address_only(sender),
                                "subject": subject})
        _gmail_pending_spam = flagged
        if not flagged:
            return "I found no obvious spam in your recent inbox, sir."
        listing = "\n".join(f"- {f['subject']} (from {f['from']})" for f in flagged)
        return ("I found %d likely spam/promotional emails. Read the list to the "
                "user and ASK whether to move them to JARVIS_Spam AND block those "
                "senders for the future. Do NOT do anything yet; wait for a clear "
                "yes. List:\n%s" % (len(flagged), listing))
    except Exception as e:
        print("Gmail spam review error:", repr(e))
        return f"Failed to review spam: {e}"

def _gmail_get_or_make_label(svc, name):
    """Find the label id by name, creating the label if it doesn't exist."""
    res = svc.users().labels().list(userId="me").execute()
    for lab in res.get("labels", []):
        if lab.get("name") == name:
            return lab["id"]
    created = svc.users().labels().create(
        userId="me", body={"name": name,
                            "labelListVisibility": "labelShow",
                            "messageListVisibility": "show"}).execute()
    return created["id"]

def gmail_move_spam():
    """Move the emails staged by gmail_spam_review into the JARVIS_Spam label
    and out of the inbox. Call this ONLY after the user confirmed out loud.
    Never deletes — the mail stays under the label and is fully recoverable."""
    global _gmail_pending_spam
    svc = _gmail_service()
    if svc is None:
        return "Gmail not connected, sir."
    if not _gmail_pending_spam:
        return "There's nothing staged to move, sir. Ask me to review spam first."
    try:
        label_id = _gmail_get_or_make_label(svc, GMAIL_SPAM_LABEL)
        moved = 0
        blocked_addrs = set()
        for f in _gmail_pending_spam:
            svc.users().messages().modify(
                userId="me", id=f["id"],
                body={"addLabelIds": [label_id], "removeLabelIds": ["INBOX"]}).execute()
            moved += 1
            # Block the sender for the future: a filter that sends mail from this
            # address straight to Trash. Skipped if we couldn't parse an address,
            # or if we already made a filter for it in this batch.
            addr = f.get("addr") or ""
            if addr and "@" in addr and addr not in blocked_addrs:
                try:
                    svc.users().settings().filters().create(
                        userId="me",
                        body={"criteria": {"from": addr},
                              "action": {"addLabelIds": ["TRASH"],
                                         "removeLabelIds": ["INBOX"]}}).execute()
                    blocked_addrs.add(addr)
                except Exception as fe:
                    print("Gmail block-sender warning for", addr, ":", repr(fe))
        _gmail_pending_spam = []
        return (f"Done, sir. Moved {moved} emails to {GMAIL_SPAM_LABEL} and blocked "
                f"{len(blocked_addrs)} senders for the future. Nothing was deleted; "
                "everything is recoverable.")
    except Exception as e:
        print("Gmail move spam error:", repr(e))
        return f"Failed to move spam: {e}"

# Tool schemas described to Claude. The 'description' fields are what Claude
# reads to decide WHEN to use each tool, so they're written for the model.
LOCAL_TOOLS = [
    {
        "name": "open_app",
        "description": ("Open an application or website on the user's Windows PC. "
                        "Use when the user asks to open, launch, or go to something. "
                        "Allowed names: " + ", ".join(ALLOWED_APPS.keys()) + "."),
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Which allowed app/site to open."}
            },
            "required": ["name"],
        },
    },
    {
        "name": "save_note",
        "description": ("Save a short note to the user's Obsidian vault. Use when "
                        "the user asks to write down, note, remember, or jot something. "
                        "Pass the note content as plain text."),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string",
                         "description": "The note content to save."}
            },
            "required": ["text"],
        },
    },
    {
        "name": "learn_topic",
        "description": ("Research a subject in depth and save a structured "
                        "study note to the user's Obsidian Knowledge folder. "
                        "Use ONLY when the user explicitly asks JARVIS to "
                        "learn, study, research, or build knowledge about "
                        "a topic - e.g. \"JARVIS, learn aerodynamics\", "
                        "\"tilmad fizika shel rachfanim\", \"research X "
                        "for me\", \"build me knowledge on Y\". The note "
                        "persists across sessions; running this again on the "
                        "same topic appends a deepening section. Optionally "
                        "include a context string (e.g. the project the "
                        "topic relates to) so the note is tailored."),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string",
                          "description": "The subject to study (e.g. 'aerodynamics of quadcopters', 'Bernoulli principle')."},
                "context": {"type": "string",
                            "description": "Optional project or use-case context to tailor the note. Pass empty string if none."},
            },
            "required": ["topic"],
        },
    },
    {
        "name": "deep_learn_domain",
        "description": ("Study an ENTIRE field/domain in depth over time. "
                        "Use when the user asks to deeply learn or master a "
                        "whole subject - e.g. \"deep-learn chemistry\", "
                        "\"learn all of physics in depth\", \"tilmad kol "
                        "ha-chimya la'omek\", \"study biology thoroughly\". "
                        "JARVIS builds a sub-topic curriculum and learns it in "
                        "the background, one deep note at a time, capped per "
                        "run for cost. Pass the field name as domain. "
                        "Optionally pass max_notes to set how many sub-topics "
                        "to learn this run (default 15)."),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string",
                           "description": "The field to study deeply (e.g. 'chemistry', 'physics', 'materials science')."},
                "max_notes": {"type": "integer",
                              "description": "Optional cap on sub-topics to learn this run (default 15, max 60)."},
            },
            "required": ["domain"],
        },
    },
    {
        "name": "resume_learning",
        "description": ("Continue learning the remaining sub-topics of a "
                        "domain that was already planned with deep_learn_domain. "
                        "Use when the user says \"continue learning X\", "
                        "\"keep studying X\", \"tamshich lilmod X\"."),
        "input_schema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "The field to continue."},
                "max_notes": {"type": "integer",
                              "description": "Optional cap for this batch (default 15, max 60)."},
            },
            "required": ["domain"],
        },
    },
    {
        "name": "learning_status",
        "description": ("Report how the background deep-learning is going. "
                        "Use when the user asks \"how's the learning going\", "
                        "\"learning status\", \"what have you learned\", "
                        "\"ma im ha-lemida\"."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "calendar_read",
        "description": ("Read the user's Google Calendar. Use when asked what's on "
                        "their schedule, what they have today/this week, or about "
                        "upcoming events. Optionally pass an ISO time range; "
                        "defaults to the next 7 days."),
        "input_schema": {
            "type": "object",
            "properties": {
                "time_min": {"type": "string", "description": "ISO start, e.g. 2026-05-25T00:00:00Z (optional)."},
                "time_max": {"type": "string", "description": "ISO end (optional)."},
            },
        },
    },
    {
        "name": "calendar_add",
        "description": ("Add an event to the user's Google Calendar. Use when they "
                        "ask to schedule, book, or add something. Compute ISO "
                        "datetimes from the current local time given in the system "
                        "prompt. Local timezone is Israel."),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start_iso": {"type": "string", "description": "Start, ISO e.g. 2026-05-26T16:00:00."},
                "end_iso": {"type": "string", "description": "End, ISO (optional; defaults to +1 hour)."},
                "location": {"type": "string", "description": "Location (optional)."},
            },
            "required": ["summary", "start_iso"],
        },
    },
    {
        "name": "calendar_delete",
        "description": ("Delete an event from the user's Google Calendar. "
                        "First call calendar_read to find the event and read "
                        "its id from the [id=...] prefix. If several events "
                        "match the user's description, list them and ASK which "
                        "one before deleting. If exactly one matches, proceed "
                        "since the user already asked. Never delete the wrong "
                        "event silently."),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string",
                             "description": "The Google Calendar event id from calendar_read."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "calendar_update",
        "description": ("Modify an existing Google Calendar event (change "
                        "title, start/end time, or location). First call "
                        "calendar_read to find the event id. Pass ONLY the "
                        "fields you want to change; leave the rest out. Times "
                        "are ISO datetimes computed from the current local "
                        "time in the system prompt."),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event id from calendar_read."},
                "summary": {"type": "string", "description": "New title (optional)."},
                "start_iso": {"type": "string", "description": "New start ISO time (optional)."},
                "end_iso": {"type": "string", "description": "New end ISO time (optional)."},
                "location": {"type": "string", "description": "New location (optional)."},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "gmail_read",
        "description": ("Read the user's most recent emails and summarise them. "
                        "Use when asked to check email, read mail, or what's in "
                        "the inbox. Returns sender/subject/snippet for each; you "
                        "then give a short spoken summary."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_spam_review",
        "description": ("Scan recent inbox mail for likely spam and return the "
                        "flagged list. Use when asked to find/clean spam or junk. "
                        "This does NOT move anything — read the list to the user "
                        "and ask whether to move them. Only call gmail_move_spam "
                        "after the user clearly confirms."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "gmail_move_spam",
        "description": ("Move the previously reviewed spam emails to the "
                        "JARVIS_Spam label (out of the inbox) AND block each "
                        "sender for the future. Call this ONLY after the user "
                        "has explicitly confirmed. Never call it without a clear "
                        "yes. Nothing is deleted; blocking is reversible."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "find_places",
        "description": ("Search Google Places for restaurants, cafes, shops, "
                        "businesses, attractions etc. in Israel. Use whenever "
                        "the user asks WHERE to eat/drink/buy/visit something "
                        "(e.g. 'find me a good sushi place in Tel Aviv', "
                        "'מסעדות איטלקיות בכפר סבא', 'cafes near Rothschild'). "
                        "Returns up to 5 results with name, rating, open/closed "
                        "status, and address. Then summarise them out loud and "
                        "ask if the user wants directions to one."),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "What to search for, e.g. 'pizza Petah Tikva' or 'cafes Tel Aviv'. Hebrew is fine."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_directions",
        "description": ("Get the driving travel time from the user's home "
                        "(Alfei Menashe) to a destination, with current live "
                        "traffic. Use when the user asks 'how long to drive "
                        "to X', 'כמה זמן ייקח להגיע ל-X', 'איך מגיעים ל-X', "
                        "or wants ETA to a place — including a place returned "
                        "by find_places. Returns a single-line summary with "
                        "distance, normal duration, and duration with traffic."),
        "input_schema": {
            "type": "object",
            "properties": {
                "destination": {"type": "string",
                                "description": "Address or place name, e.g. 'Azrieli Tower Tel Aviv' or 'דיזנגוף סנטר'."},
                "origin": {"type": "string",
                           "description": "Optional starting address. Defaults to the user's home in Alfei Menashe."},
            },
            "required": ["destination"],
        },
    },
    {
        "name": "set_timer",
        "description": ("Start a countdown timer or reminder. Use when the user "
                        "asks to set a timer, remind them in N minutes, or alert "
                        "them after some time (e.g. 'set a timer for 5 minutes', "
                        "'\u05ea\u05d6\u05db\u05d9\u05e8 \u05dc\u05d9 \u05d1\u05e2\u05d5\u05d3 10 \u05d3\u05e7\u05d5\u05ea', "
                        "'timer for the pasta 8 minutes'). When it elapses JARVIS "
                        "announces it by voice. For an absolute time like '4 PM', "
                        "compute minutes from the current local time in the system "
                        "prompt."),
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "number",
                            "description": "Minutes from now until the timer fires. May be fractional."},
                "label": {"type": "string",
                          "description": "Optional short label, e.g. 'pasta' or 'workout'."},
            },
            "required": ["minutes"],
        },
    },
    {
        "name": "spotify_play",
        "description": ("Play music on Spotify. Use when the user asks to "
                        "play / listen to / put on a song, artist, album, "
                        "or playlist, or to resume music. Pass `query` for "
                        "a specific request (e.g. 'Bohemian Rhapsody', "
                        "'Imagine Dragons', '\u05d4\u05d1\u05d9\u05d8\u05dc\u05e1'). Omit `query` "
                        "to resume current playback. Requires Spotify "
                        "Premium and Spotify open on some device."),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "Song / artist / album / playlist. Omit to resume."},
            },
        },
    },
    {
        "name": "spotify_pause",
        "description": "Pause Spotify playback.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_next",
        "description": "Skip to the next track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_previous",
        "description": "Go back to the previous track on Spotify.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "spotify_volume",
        "description": "Set Spotify playback volume. Pass `level` 0-100.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "number", "description": "Volume percent 0-100."},
            },
            "required": ["level"],
        },
    },
    {
        "name": "spotify_now_playing",
        "description": "Ask Spotify what is currently playing.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_roadmap",
        "description": ("Open Mission Control - the JARVIS project roadmap / "
                        "status dashboard page in the browser. Use when the "
                        "user asks for the roadmap, the project status board, "
                        "mission control, what's left to build, or the "
                        "checklist page. Hebrew triggers include "
                        "'\u05e4\u05ea\u05d7 \u05d0\u05ea \u05d4-roadmap', "
                        "'\u05de\u05e4\u05ea \u05d3\u05e8\u05db\u05d9\u05dd', "
                        "'\u05ea\u05e4\u05ea\u05d7 \u05d0\u05ea \u05dc\u05d5\u05d7 "
                        "\u05d4\u05de\u05e9\u05d9\u05de\u05d5\u05ea'."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_search_panel",
        "description": ("Open the big search window. Use when the user wants to "
                        "find/look up a product or asks to open the search "
                        "window, or wants to show JARVIS an image (e.g. 'find me "
                        "this chair', 'open the search window', 'I want to upload "
                        "a picture'). The window lets them type, speak, or pick "
                        "an image, and shows clickable result links."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_worldview",
        "description": ("Open WorldView, the 3D globe in the user's browser. "
                        "Use when the user asks to open WorldView, open the "
                        "globe, show the world or the Earth, or asks about "
                        "live earthquakes / seismic activity worldwide. The "
                        "globe shows live USGS earthquake data on a rotating "
                        "Earth in a separate browser tab. Hebrew triggers "
                        "include 'פתח את WorldView', 'תפתח את הגלובוס', "
                        "'תראה לי רעידות אדמה'."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "open_hermes",
        "description": ("Open HERMES, the financial/investment terminal in the "
                        "user's browser. Use when the user asks to open HERMES, "
                        "open the investment/trading terminal, the markets "
                        "terminal, or the finance dashboard. Hebrew triggers "
                        "include '\u05e4\u05ea\u05d7 \u05d0\u05ea \u05d4\u05e8\u05de\u05e1', "
                        "'\u05ea\u05e4\u05ea\u05d7 \u05d0\u05ea \u05d4\u05e8\u05de\u05e1', "
                        "'\u05e4\u05ea\u05d7 \u05d0\u05ea \u05d4\u05d8\u05e8\u05de\u05d9\u05e0\u05dc', "
                        "'\u05de\u05de\u05e9\u05e7 \u05d4\u05d4\u05e9\u05e7\u05e2\u05d4'."),
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "share_live_location",
        "description": ("Create a SECURE, TEMPORARY public link to the user's "
                        "LIVE location and send it to the user's brother over "
                        "Telegram. Use when the user asks to share/send their "
                        "live location or 'where I am' for some minutes, e.g. "
                        "'share my location for 15 minutes', 'send my brother my "
                        "live location for half an hour'. Hebrew triggers include "
                        "'שתף את המיקום "
                        "שלי', 'תשלח לאח "
                        "שלי את המיקום', "
                        "'שתף מיקום ל-15 "
                        "דקות'. The link expires automatically "
                        "and reveals ONLY the live coordinates - no other app "
                        "data. Pass minutes as the requested duration; default 15."),
        "input_schema": {"type": "object", "properties": {
            "minutes": {"type": "number",
                        "description": "How many minutes the link stays valid. Default 15."}
        }},
    },
    {
        "name": "request_location",
        "description": ("Create a SECURE, TEMPORARY link that asks SOMEONE "
                        "ELSE for their live location. The user forwards the "
                        "join link; when that person opens it and approves, "
                        "their position appears on the user's live map link. "
                        "Consent-based: the browser asks them explicitly. Use "
                        "when the user asks WHERE SOMEONE ELSE is / to request "
                        "someone's location. Optionally also reveals the "
                        "user's own location back to that person."),
        "input_schema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "number",
                            "description": "Link lifetime in minutes (default 15)"},
                "show_my_location": {"type": "boolean",
                                     "description": "If true, the person can also "
                                                    "see the user's live location "
                                                    "(default false)"}
            },
            "required": []
        }
    },
    {
        "name": "open_achilles",
        "description": ("Open the Achilles Core screen - an ultra-realistic "
                        "WebGL black hole that serves as the assistant's "
                        "visual face, with a Solar System mode (clickable "
                        "planets with facts and live news). Use when the user "
                        "asks for the black hole, the Achilles screen or "
                        "window, or the solar system / the planets. Hebrew "
                        "triggers include 'פתח את החור השחור', 'תפתח את "
                        "אכילס', 'מערכת השמש', 'תראה לי את הכוכבים'. Pass "
                        "scene='solar' when they ask for the solar system or "
                        "planets, scene='todo' when they ask for the to-do "
                        "list / task list / 'המשימות שלי', otherwise "
                        "scene='core'."),
        "input_schema": {"type": "object", "properties": {
            "scene": {"type": "string", "enum": ["core", "solar", "todo"],
                      "description": "core = black hole, solar = solar system, todo = task list"}
        }},
    },
    {
        "name": "set_weight_target",
        "description": ("Change the user's minimum-weight red line (the training "
                        "goal used by the daily briefing and the Training tile). "
                        "Use ONLY when the user explicitly asks to change, update, "
                        "or set their weight target/goal - e.g. \"change my weight "
                        "target to 72\", \"tishane et matrat ha'mishkal sheli le 72\". "
                        "Do not use this for logging today's actual measured weight - "
                        "that is a separate action the user does from the Training tile."),
        "input_schema": {
            "type": "object",
            "properties": {
                "kg": {"type": "number",
                       "description": "The new minimum-weight target in kg."}
            },
            "required": ["kg"],
        },
    },
]

def set_weight_target(kg):
    """LLM tool handler: change weight_target_min_kg in training_log.json.
    Mirrors the file path and locking used by the /training_weight HTTP
    handler in _handle_training so both stay consistent. v5.16j: this tool
    did not exist before, so asking JARVIS to change the weight target was
    silently a no-op - it could only reply conversationally with no way to
    actually write the change."""
    try:
        kg = float(kg)
    except Exception:
        return "That doesn't look like a valid weight."
    if not (30 <= kg <= 200):
        return "That weight is out of a sane range (30-200 kg) - please confirm the number."
    p = Path(__file__).resolve().parent / "training_log.json"
    with _training_lock:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        old = data.get("weight_target_min_kg", 68)
        data["weight_target_min_kg"] = round(kg, 1)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _record_action("set_weight_target", {"old": old, "new": round(kg, 1)})
    return "Weight target updated from %g kg to %g kg." % (float(old), kg)

def run_local_tool(name, tool_input):
    """Dispatch a tool call from Claude to the matching Python function."""
    if name == "set_weight_target":
        return set_weight_target(tool_input.get("kg"))
    if name == "open_app":
        return open_app(tool_input.get("name", ""))
    if name == "save_note":
        return save_note(tool_input.get("text", ""))
    if name == "calendar_read":
        return calendar_read(tool_input.get("time_min"), tool_input.get("time_max"))
    if name == "calendar_add":
        return calendar_add(tool_input.get("summary", ""),
                            tool_input.get("start_iso", ""),
                            tool_input.get("end_iso"),
                            tool_input.get("location"))
    if name == "calendar_delete":
        return calendar_delete(tool_input.get("event_id", ""))
    if name == "calendar_update":
        return calendar_update(tool_input.get("event_id", ""),
                               tool_input.get("summary"),
                               tool_input.get("start_iso"),
                               tool_input.get("end_iso"),
                               tool_input.get("location"))
    if name == "gmail_read":
        return gmail_read()
    if name == "gmail_spam_review":
        return gmail_spam_review()
    if name == "gmail_move_spam":
        return gmail_move_spam()
    if name == "find_places":
        return find_places(tool_input.get("query", ""))
    if name == "get_directions":
        return get_directions(tool_input.get("destination", ""),
                              tool_input.get("origin"))
    if name == "set_timer":
        return set_timer(tool_input.get("minutes"), tool_input.get("label"))
    if name == "spotify_play":
        return spotify_play(tool_input.get("query"))
    if name == "spotify_pause":
        return spotify_pause()
    if name == "spotify_next":
        return spotify_next()
    if name == "spotify_previous":
        return spotify_previous()
    if name == "spotify_volume":
        return spotify_volume(tool_input.get("level"))
    if name == "spotify_now_playing":
        return spotify_now_playing()
    if name == "deep_learn_domain":
        return deep_learn_domain(
            tool_input.get("domain", ""),
            tool_input.get("max_notes"),
        )
    if name == "resume_learning":
        return resume_learning(
            tool_input.get("domain", ""),
            tool_input.get("max_notes"),
        )
    if name == "learning_status":
        return learning_status()
    if name == "learn_topic":
        return learn_topic(
            tool_input.get("topic", ""),
            tool_input.get("context", ""),
        )
    if name == "open_worldview":
        return open_worldview()
    if name == "open_hermes":
        return open_hermes()
    if name == "share_live_location":
        return share_live_location(tool_input.get("minutes", 15))
    if name == "request_location":
        return request_location(tool_input.get("minutes", 15),
                                bool(tool_input.get("show_my_location", False)))
    if name == "open_achilles":
        return open_achilles(tool_input.get("scene", "core"))
    if name == "open_roadmap":
        return open_roadmap()
    if name == "open_search_panel":
        if APP is not None:
            APP.ui(APP.open_panel)
            return "Opening the search window, sir."
        return "The search window isn't available right now."
    return f"Unknown tool: {name}"

def _learning_intercept(user_message: str):
    """Detect clear learning commands and return a (topic, depth) tuple, or
    None if the message is not a learning command. depth in {'deep', 'narrow'}."""
    if not user_message or not isinstance(user_message, str):
        return None
    import re
    text = user_message.strip()
    # Strip leading "JARVIS," / "Hey JARVIS," variants
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג'?א?ר?ו+יס|gארוויס)[\s,:]*", "", text)
    if not text:
        return None
    low = text.lower()

    # --- LEARNING_STATUS shortcuts ---
    if any(p in low for p in ["learning status", "how's the learning",
                              "how is the learning", "what have you learned"]):
        return ("__STATUS__", None)
    if any(p in text for p in ["מה עם הלמידה", "סטטוס למידה", "איך הלמידה",
                               "מה למדת"]):
        return ("__STATUS__", None)

    # --- RESUME ---
    m = re.match(r"(?:continue|resume|keep)\s+(?:studying|learning)\s+(.+)$", low)
    if m:
        return ("__RESUME__:" + m.group(1).strip(), None)
    m = re.match(r"^\s*תמשיך\s+(?:ללמוד|לחקור)\s+(?:את\s+)?(.+)$", text)
    if m:
        return ("__RESUME__:" + m.group(1).strip(), None)

    # --- LEARN commands ---
    # English: "deep-learn X" / "deep learn X" / "learn X" / "study X" / "research X" / "master X"
    # Capture both the verb (to detect depth) and the topic.
    en = re.match(
        r"^\s*(deep[\s-]?learn|learn(?:\s+all\s+of)?|study(?:\s+all\s+of)?|research|master|build\s+knowledge\s+(?:of|about|on))\s+(.+?)\s*[.!?]?\s*$",
        low)
    if en:
        verb = en.group(1)
        # Topic from the original casing for the file/folder name
        topic = text[text.lower().find(en.group(2)):].strip(" .!?,")
        is_deep = ("deep" in verb) or ("all of" in verb)
        return (topic, "deep" if is_deep else "narrow")

    # Hebrew: "תלמד לעומק X" / "תלמד את X לעומק" / "תלמד את כל X" / "תלמד X" /
    #        "ללמוד X" / "תחקור X" / "תבנה ידע על X"
    # Detect the "lao'omek" / "kol ha-" depth markers.
    he_verb = r"(?:תלמד|למד|ללמוד|תחקור|לחקור|תבנה\s+(?:לי\s+)?ידע(?:\s+על)?)"
    he = re.match(r"^\s*" + he_verb + r"\s+(.+)$", text)
    if he:
        rest = he.group(1).strip()
        is_deep = ("לעומק" in rest) or ("כל ה" in rest) or ("את כל" in rest)
        # Clean topic: strip leading "את ", trailing "לעומק", leading "את כל ה"
        topic = rest
        topic = re.sub(r"\bלעומק\b", "", topic).strip()
        topic = re.sub(r"^את\s+כל\s+ה", "", topic).strip()
        topic = re.sub(r"^את\s+ה", "", topic).strip()
        topic = re.sub(r"^את\s+", "", topic).strip()
        topic = re.sub(r"^כל\s+ה", "", topic).strip()
        topic = topic.strip(" .!?,:")
        if topic:
            return (topic, "deep" if is_deep else "narrow")

    return None

def _whats_new_intercept(msg):
    """True if the user is asking what changed recently in JARVIS."""
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "what's new", "whats new", "what is new", "anything new",
        "what changed", "what's changed", "whats changed",
        "what did you add", "what did we add",
        "what's been added", "what's different",
        "recent changes", "any updates",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "מה השתנה", "מה חדש", "מה הוספנו", "מה הוספת",
        "מה שינית", "מה שינינו", "מה התווסף", "מה התעדכן",
        "מה עדכנו", "מה עדכנת",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False


def whats_new(lang="en"):
    """Read the most recent Changelog entries from this file and return a
    short reply for the user. Falls back gracefully on any error."""
    try:
        src = Path(__file__).read_text(encoding="utf-8")
    except Exception:
        return ("לא הצלחתי לקרוא את עצמי, אדוני." if lang == "he"
                else "I can't read my own source right now, sir.")
    m = re.search(r'Changelog:\s*\n(.+?)"""', src, re.DOTALL)
    if not m:
        return ("אין לי changelog זמין, אדוני." if lang == "he"
                else "I don't have a changelog to show, sir.")
    body = m.group(1)
    entries = re.findall(
        r'^  (v\d+\.\d+\s+-\s+.+?)(?=^  v\d+\.\d+\s+-\s+|\Z)',
        body, re.MULTILINE | re.DOTALL)
    if not entries:
        return ("ה-changelog ריק, אדוני." if lang == "he"
                else "The changelog is empty, sir.")
    cleaned = []
    for e in entries[:3]:
        flat = " ".join(line.strip() for line in e.splitlines()
                        if line.strip())
        cleaned.append(flat)
    facts = "\n".join("- " + c for c in cleaned)
    if not ANTHROPIC_API_KEY:
        return (("השינויים האחרונים, אדוני:\n" + facts) if lang == "he"
                else ("Recent changes, sir:\n" + facts))
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI assistant. The user "
            "asked what changed recently in your code. Below are the last "
            "few Changelog entries (newest first). Summarise them naturally "
            "in 2-4 short sentences in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address the user as 'sir' (or 'אדוני' in Hebrew). Focus on "
            "what is new for the USER (capabilities, fixes they would "
            "notice), not internal version numbers or implementation "
            "details. Plain text only - no markdown, no bullet points."
        )
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=300,
            system=sys_p,
            messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content
                 if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or facts
    except Exception:
        return facts


def _system_health_intercept(msg):
    """True if the user is asking for a system health check."""
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "system health", "health check", "status check",
        "self check", "self-check", "selfcheck",
        "are you ok", "are you okay", "are you alright",
        "is everything ok", "is everything okay",
        "everything working", "everything alright",
        "system status", "diagnostics",
        "run a check", "run diagnostics", "check yourself",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "בדיקה עצמית", "בדוק את עצמך", "בדיקת מערכת",
        "בריאות מערכת", "בריאות המערכת", "מצב המערכת",
        "מצב מערכת", "סטטוס מערכת", "האם הכל תקין",
        "הכל עובד", "הכל תקין", "תבדוק שהכל",
        "הרץ בדיקה", "אבחון מערכת",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False


def system_health(lang="en"):
    """Quick health snapshot of JARVIS. Shallow checks only - no expensive
    API calls. Returns a short, natural reply phrased by Sonnet; falls back
    to raw facts on any error."""
    import socket as _socket_mod
    facts = []

    # API keys
    if ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-ant-"):
        facts.append("Anthropic key: OK (loaded, %d chars)"
                     % len(ANTHROPIC_API_KEY))
    elif ANTHROPIC_API_KEY:
        facts.append("Anthropic key: WARN (loaded but format looks off)")
    else:
        facts.append("Anthropic key: FAIL (missing from .env - brain offline)")

    if ELEVENLABS_API_KEY:
        facts.append("ElevenLabs key: OK (loaded, %d chars)"
                     % len(ELEVENLABS_API_KEY))
    else:
        facts.append("ElevenLabs key: WARN (missing - English voice will "
                     "fall back to edge-tts)")

    if GOOGLE_MAPS_API_KEY:
        facts.append("Google Maps key: OK (loaded)")
    else:
        facts.append("Google Maps key: WARN (missing - places, directions, "
                     "WorldView will not work)")

    # Google Calendar + Gmail (shared token) - v4.41: real live probe
    # not just file existence. Catches dead refresh tokens etc.
    if not os.path.exists(CAL_CREDENTIALS_FILE):
        facts.append("Google Calendar + Gmail: WARN "
                     "(not configured - no credentials.json)")
    elif not os.path.exists(CAL_TOKEN_FILE):
        facts.append("Google Calendar + Gmail: WARN "
                     "(no token yet - first sign-in needed)")
    else:
        try:
            _gc_svc = _calendar_service()
            if _gc_svc is None:
                facts.append("Google Calendar + Gmail: FAIL "
                             "(auth dead - run reauth_google.py)")
            else:
                _gc_svc.calendarList().list(maxResults=1).execute()
                facts.append("Google Calendar + Gmail: OK (live probe passed)")
        except Exception as _gc_e:
            facts.append("Google Calendar + Gmail: FAIL "
                         "(live probe error: %s)" % type(_gc_e).__name__)

    # Spotify
    if SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET:
        if _SPOTIFY_TOKEN_FILE.exists():
            facts.append("Spotify: OK (credentials and token present)")
        else:
            facts.append("Spotify: WARN (credentials present, no token - "
                         "first sign-in needed)")
    else:
        facts.append("Spotify: WARN (client id/secret missing from .env)")

    # WorldView HTML file
    try:
        wv = Path(__file__).resolve().parent / "worldview.html"
        if wv.exists():
            facts.append("WorldView file: OK (worldview.html present)")
        else:
            facts.append("WorldView file: WARN (worldview.html missing)")
    except Exception as e:
        facts.append("WorldView file: WARN (%s)" % e)

    # Knowledge folder
    try:
        kn = Path(KNOWLEDGE_DIR)
        if kn.exists():
            doms = [p for p in kn.iterdir() if p.is_dir()]
            facts.append("Knowledge folder: OK (%d domain(s) on disk)"
                         % len(doms))
        else:
            facts.append("Knowledge folder: WARN (not created yet)")
    except Exception as e:
        facts.append("Knowledge folder: WARN (%s)" % e)

    # Background deep-learning thread state
    try:
        with _deep_learn_lock:
            running = _deep_learn_state["running"]
            domain = _deep_learn_state["domain"]
            done = _deep_learn_state["done"]
            total = _deep_learn_state["total"]
        if running and domain:
            facts.append("Background learning: OK (running - %s, %d/%d "
                         "this run)" % (domain, done, total))
        else:
            facts.append("Background learning: OK (idle)")
    except Exception as e:
        facts.append("Background learning: WARN (%s)" % e)

    # Internet reachability (DNS port to Cloudflare - fast, free)
    try:
        s = _socket_mod.create_connection(("1.1.1.1", 53), timeout=2)
        s.close()
        facts.append("Internet: OK (reachable)")
    except Exception:
        facts.append("Internet: FAIL (unreachable - most tools will not work)")

    raw = "\n".join(facts)

    if not ANTHROPIC_API_KEY:
        return raw

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI assistant. The user "
            "asked for a quick system health check. Below is a list of "
            "components and their statuses (OK / WARN / FAIL). Reply in 2-4 "
            "short sentences in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address the user as 'sir' (or 'אדוני' in Hebrew). Lead "
            "with the overall headline (all good / some warnings / a real "
            "problem). Then name only the items the user would care about - "
            "warnings and failures specifically; do not list every OK item "
            "unless absolutely everything is fine. Plain text, no markdown, "
            "no bullet points."
        )
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=300,
            system=sys_p,
            messages=[{"role": "user", "content": raw}])
        parts = [b.text for b in r.content
                 if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or raw
    except Exception:
        return raw


def _learned_this_week_intercept(msg):
    """True if the user is asking what they learned this week."""
    if not msg or not isinstance(msg, str):
        return False
    low = msg.lower().strip()
    en_triggers = [
        "what did i learn this week", "what have i learned this week",
        "what did i study this week", "weekly learning summary",
        "what did we learn this week", "this week's notes",
        "what did i learn lately", "what have i learned lately",
        "learning summary", "what did i learn recently",
        "what have we learned",
    ]
    if any(t in low for t in en_triggers):
        return True
    he_triggers = [
        "מה למדתי השבוע", "מה למדנו השבוע",
        "מה למדתי לאחרונה", "מה למדנו לאחרונה",
        "סיכום למידה", "סיכום השבוע",
        "מה נלמד השבוע", "מה למדנו לאחרונה",
        "מה למדת לאחרונה", "מה למדת השבוע",
    ]
    if any(t in msg for t in he_triggers):
        return True
    return False


def learned_this_week(lang="en"):
    """Summarise knowledge notes created or modified in the past 7 days.
    Walks Obsidian_Vault/Knowledge/, groups by domain, then asks Sonnet to
    phrase a short reply. Falls back to raw facts on error."""
    try:
        base = Path(KNOWLEDGE_DIR)
        if not base.exists():
            return ("אין עדיין תיקיית ידע, אדוני." if lang == "he"
                    else "There's no knowledge folder yet, sir.")
        cutoff = datetime.datetime.now() - datetime.timedelta(days=7)
        by_domain = {}      # domain_slug -> [titles]
        standalone = []     # notes directly under KNOWLEDGE_DIR
        for f in base.rglob("*.md"):
            if f.name.startswith("_"):
                continue
            try:
                mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    continue
            except Exception:
                continue
            try:
                head = "\n".join(
                    f.read_text(encoding="utf-8").splitlines()[:30])
            except Exception:
                continue
            title = None
            m = re.search(r"^title:\s*[\"']?(.+?)[\"']?\s*$",
                          head, re.MULTILINE)
            if m:
                title = m.group(1).strip()
            else:
                m = re.search(r"^#\s+(.+?)\s*$", head, re.MULTILINE)
                if m:
                    title = m.group(1).strip()
            if not title:
                title = f.stem.replace("_", " ")
            try:
                rel = f.relative_to(base)
                if len(rel.parts) > 1:
                    by_domain.setdefault(rel.parts[0], []).append(title)
                else:
                    standalone.append(title)
            except Exception:
                standalone.append(title)
        total = sum(len(v) for v in by_domain.values()) + len(standalone)
        if total == 0:
            return ("השבוע לא נוצרו פתקי ידע, אדוני." if lang == "he"
                    else "No knowledge notes were created in the past week, sir.")
        lines = []
        for domain, titles in sorted(by_domain.items()):
            d_name = domain.replace("_", " ")
            lines.append("%s (%d notes): %s"
                         % (d_name, len(titles), ", ".join(titles)))
        if standalone:
            lines.append("standalone (%d): %s"
                         % (len(standalone), ", ".join(standalone)))
        facts = ("Total notes in the past 7 days: %d.\n" % total
                 + "\n".join(lines))
        if not ANTHROPIC_API_KEY:
            return facts
        try:
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            sys_p = (
                "You are Achilles, a calm British-butler AI assistant. The "
                "user asked for a summary of what was learned this week (in "
                "the knowledge notes). Below is the list of notes generated "
                "in the past 7 days, grouped by domain. Reply in 2-4 short "
                "sentences in "
                + ("Hebrew" if lang == "he" else "English")
                + ". Address the user as 'sir' (or 'אדוני' in Hebrew). Lead "
                "with the total count and the main domain(s). Name a few "
                "notable sub-topics by name (but not all). Plain text, no "
                "markdown, no bullet points."
            )
            r = client.messages.create(
                model="claude-sonnet-5", max_tokens=350,
                system=sys_p,
                messages=[{"role": "user", "content": facts}])
            parts = [b.text for b in r.content
                     if getattr(b, "type", None) == "text"]
            reply = " ".join(p.strip() for p in parts if p.strip()).strip()
            return clean_text(reply) or facts
        except Exception:
            return facts
    except Exception as e:
        return ("נכשלתי לסכם את הלמידה השבוע, אדוני: %s" % e
                if lang == "he"
                else "Failed to summarise weekly learning, sir: %s" % e)


# =====================================================================
# Undo (v4.29) - reverse the most recent mutating action
# =====================================================================
_last_action_lock = threading.Lock()
_last_action = {"type": None, "data": None}


def _record_action(action_type, data):
    """Remember the most recent undoable action. Called by mutating
    functions (save_note, calendar_add, calendar_delete, set_timer)
    after they succeed. Only the SINGLE most recent action is kept -
    'undo' covers one step."""
    with _last_action_lock:
        _last_action["type"] = action_type
        _last_action["data"] = data


def undo_last():
    """Reverse the most recent mutating action. Supported types:
       calendar_add    - removes the just-added event
       calendar_delete - re-inserts the just-deleted event (body
                         was cached before deletion)
       save_note       - removes the appended line from disk
       set_timer       - cancels the pending threading.Timer
    Returns a short status string for the spoken reply. Consumes
    the recorded action immediately so a second 'undo' is a no-op
    rather than a double-reverse."""
    with _last_action_lock:
        atype = _last_action.get("type")
        data = _last_action.get("data") or {}
        _last_action["type"] = None
        _last_action["data"] = None
    if not atype:
        return "Nothing to undo, sir."
    try:
        if atype == "calendar_add":
            event_id = data.get("event_id", "")
            summary = data.get("summary", "")
            if not event_id:
                return "Can't undo - I don't have the event id, sir."
            svc = _calendar_service()
            if svc is None:
                return "Can't undo - calendar isn't connected, sir."
            svc.events().delete(calendarId="primary",
                                eventId=event_id).execute()
            return "Undone, sir. Removed '%s'." % (summary or "the event")
        if atype == "calendar_delete":
            body = data.get("body") or {}
            summary = body.get("summary", "the event")
            svc = _calendar_service()
            if svc is None:
                return "Can't undo - calendar isn't connected, sir."
            if not body.get("start") or not body.get("end"):
                return "Can't undo - the cached event is incomplete, sir."
            svc.events().insert(calendarId="primary", body=body).execute()
            return "Undone, sir. Restored '%s'." % summary
        if atype == "save_note":
            path = data.get("path", "")
            written = data.get("written", "")
            if not path or not os.path.exists(path):
                return "Can't undo - the note file is gone, sir."
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return "Can't read the note file, sir: %s" % e
            if written and content.endswith(written):
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content[:-len(written)])
                return "Undone, sir. Removed the last note."
            return ("Can't undo - the note file changed since I "
                    "wrote it, sir.")
        if atype == "set_timer":
            timer = data.get("timer")
            label = data.get("label") or ""
            if timer is not None:
                try:
                    timer.cancel()
                except Exception:
                    pass
                try:
                    if timer in _active_timers:
                        _active_timers.remove(timer)
                except Exception:
                    pass
            return ("Timer cancelled%s, sir."
                    % ((" (%s)" % label) if label else ""))
        return "I don't know how to undo that, sir."
    except Exception as e:
        return "Undo failed: %s" % e


def _undo_intercept(msg):
    """True if the user is asking to undo the last action."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "undo", "undo it", "undo that", "undo last",
        "undo the last", "undo the last action", "undo last action",
        "revert", "revert that", "revert it", "revert the last",
        "cancel that", "cancel the last", "cancel last action",
        "scratch that", "take that back", "take it back",
        "nevermind that", "never mind that",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05ea\u05d1\u05d8\u05dc", "\u05ea\u05d1\u05d8\u05dc \u05d0\u05ea \u05d6\u05d4",
        "\u05ea\u05d1\u05d8\u05dc \u05d0\u05ea \u05d4\u05e4\u05e2\u05d5\u05dc\u05d4",
        "\u05ea\u05d1\u05d8\u05dc \u05d0\u05ea \u05d4\u05d0\u05d7\u05e8\u05d5\u05df",
        "\u05d1\u05d8\u05dc", "\u05d1\u05d8\u05dc \u05d0\u05ea \u05d6\u05d4",
        "\u05d1\u05d8\u05dc \u05d0\u05ea \u05d4\u05e4\u05e2\u05d5\u05dc\u05d4",
        "\u05d1\u05d8\u05dc \u05d0\u05ea \u05d4\u05d0\u05d7\u05e8\u05d5\u05df",
        "\u05d1\u05d9\u05d8\u05d5\u05dc", "\u05d1\u05d9\u05d8\u05d5\u05dc \u05d0\u05d7\u05e8\u05d5\u05df",
        "\u05d1\u05d9\u05d8\u05d5\u05dc \u05e4\u05e2\u05d5\u05dc\u05d4",
        "\u05d0\u05e0\u05d3\u05d5", "\u05ea\u05d7\u05d6\u05d9\u05e8 \u05d0\u05ea \u05d6\u05d4",
        "\u05ea\u05d7\u05d6\u05d9\u05e8", "\u05ea\u05d7\u05d6\u05d5\u05e8 \u05d0\u05d7\u05d5\u05e8\u05d4",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Cost tracking (v4.30) - monthly Anthropic API budget
# =====================================================================
_usage_lock = threading.Lock()
_USAGE_FILE = Path("anthropic_usage.json")
try:
    _BUDGET_USD = float(os.getenv("JARVIS_MONTHLY_BUDGET_USD", "50"))
except Exception:
    _BUDGET_USD = 50.0

# Pricing per million tokens. User can override if Anthropic changes
# rates. Matched by substring on the model name (sonnet/opus/haiku).
_DEFAULT_ANTHROPIC_PRICING = {
    "sonnet": {"input": 3.00,  "output": 15.00},
    "opus":   {"input": 15.00, "output": 75.00},
    "haiku":  {"input": 0.80,  "output": 4.00},
}


def _model_pricing(model_name):
    """Look up per-million-token rates for a model. Falls back to
    Sonnet pricing for unrecognized names (safest middle-of-road)."""
    low = (model_name or "").lower()
    if "opus" in low:
        return _DEFAULT_ANTHROPIC_PRICING["opus"]
    if "haiku" in low:
        return _DEFAULT_ANTHROPIC_PRICING["haiku"]
    return _DEFAULT_ANTHROPIC_PRICING["sonnet"]


def _load_usage():
    if not _USAGE_FILE.exists():
        return {}
    try:
        return json.loads(_USAGE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_usage(data):
    try:
        _USAGE_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8")
    except Exception as e:
        print("[diag] usage save failed:", repr(e))


def _track_anthropic_usage(response):
    """Update the persistent usage counter from an Anthropic response.
    Best-effort - any error returns silently so it never breaks the
    main API flow."""
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        # Cache tokens (if present) bill at the same input rate here
        # for simplicity - a slight overestimate vs. Anthropic's
        # 90%-off cache hits, but never an underestimate.
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        in_tok += cache_read + cache_create
        model = getattr(response, "model", "")
        pricing = _model_pricing(model)
        cost = (in_tok * pricing["input"]
                + out_tok * pricing["output"]) / 1_000_000.0
        crossed_80 = False
        crossed_100 = False
        with _usage_lock:
            data = _load_usage()
            month_key = datetime.date.today().strftime("%Y-%m")
            months = data.setdefault("months", {})
            m = months.setdefault(month_key, {
                "input_tokens": 0, "output_tokens": 0,
                "cost_usd": 0.0, "calls": 0,
                "warned_80": False, "warned_100": False,
            })
            m["input_tokens"] += in_tok
            m["output_tokens"] += out_tok
            m["cost_usd"] = round(m["cost_usd"] + cost, 6)
            m["calls"] += 1
            data["last_update"] = datetime.datetime.now().isoformat(
                timespec="seconds")
            pct = (m["cost_usd"] / _BUDGET_USD * 100.0
                   if _BUDGET_USD > 0 else 0)
            if pct >= 100 and not m["warned_100"]:
                m["warned_100"] = True
                crossed_100 = True
            elif pct >= 80 and not m["warned_80"]:
                m["warned_80"] = True
                crossed_80 = True
            _save_usage(data)
        # Fire the alert OUTSIDE the lock and in a background thread
        # so the main API flow never blocks on TTS.
        if crossed_100:
            threading.Thread(target=_budget_alert, args=("over",),
                             daemon=True).start()
        elif crossed_80:
            threading.Thread(target=_budget_alert, args=("warning",),
                             daemon=True).start()
    except Exception as e:
        print("[diag] usage tracking failed:", repr(e))


def _budget_alert(level):
    """Announce a budget alert by voice and on the orb. Runs in a
    background thread; safe to fail silently."""
    if level == "over":
        msg = ("Sir, you've exceeded the monthly API budget of $%.0f. "
               "Consider pausing background learning."
               % _BUDGET_USD)
    else:
        msg = ("Sir, you've used 80%% of the monthly $%.0f API budget. "
               "Heads up." % _BUDGET_USD)
    try:
        if APP is not None:
            APP.ui(lambda m=msg: APP._push("JARVIS", m))
    except Exception:
        pass
    try:
        speak(msg)
    except Exception:
        pass


def budget_status(lang="en"):
    """Voice-friendly summary of current month's spending. Called by
    _budget_intercept; returns plain text for clean_text / speak."""
    try:
        data = _load_usage()
        month_key = datetime.date.today().strftime("%Y-%m")
        m = data.get("months", {}).get(month_key, {})
        spent = float(m.get("cost_usd", 0.0))
        calls = int(m.get("calls", 0))
        in_tok = int(m.get("input_tokens", 0))
        out_tok = int(m.get("output_tokens", 0))
        pct = (spent / _BUDGET_USD * 100.0) if _BUDGET_USD > 0 else 0
        if lang == "he":
            return ("החודש הוצאת %.2f דולר מתוך %.0f דולר, %.0f אחוזים, "
                    "אדוני. %d קריאות API, %s טוקנים בקלט ו-%s טוקנים בפלט."
                    % (spent, _BUDGET_USD, pct, calls,
                       "{:,}".format(in_tok), "{:,}".format(out_tok)))
        return ("Sir, you've spent $%.2f of your $%.0f monthly cap "
                "(%.0f%%) - %d API calls, %s input tokens and %s "
                "output tokens." % (spent, _BUDGET_USD, pct, calls,
                                     "{:,}".format(in_tok),
                                     "{:,}".format(out_tok)))
    except Exception as e:
        if lang == "he":
            return "לא הצלחתי לקרוא את התקציב, אדוני: %s" % e
        return "Couldn't read the budget, sir: %s" % e


def _budget_intercept(msg):
    """True if the user is asking about API cost / budget."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    low = text.lower().strip().rstrip(".!?,")
    en_triggers = {
        "budget", "my budget", "the budget",
        "what's my budget", "whats my budget", "what is my budget",
        "show me the budget", "show my budget",
        "api budget", "api cost", "api spending", "api spend",
        "cost status", "monthly cost", "monthly spend",
        "how much have i spent", "how much did i spend",
        "how much is the api costing",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05d4\u05ea\u05e7\u05e6\u05d9\u05d1",
        "\u05de\u05d4 \u05d4\u05ea\u05e7\u05e6\u05d9\u05d1",
        "\u05de\u05d4 \u05d4\u05ea\u05e7\u05e6\u05d9\u05d1 \u05e9\u05dc\u05d9",
        "\u05ea\u05e7\u05e6\u05d9\u05d1 \u05d4-API",
        "\u05ea\u05e7\u05e6\u05d9\u05d1 \u05d4\u05d7\u05d5\u05d3\u05e9",
        "\u05de\u05e6\u05d1 \u05d4\u05ea\u05e7\u05e6\u05d9\u05d1",
        "\u05db\u05de\u05d4 \u05d4\u05d5\u05e6\u05d0\u05ea\u05d9",
        "\u05db\u05de\u05d4 \u05d6\u05d4 \u05e2\u05d5\u05dc\u05d4",
        "\u05db\u05de\u05d4 \u05d1\u05d9\u05d6\u05d1\u05d6\u05ea\u05d9",
        "\u05e2\u05dc\u05d5\u05ea \u05d4-API",
    }
    if text in he_triggers:
        return True
    if any(t in text for t in ("\u05de\u05d4 \u05d4\u05ea\u05e7\u05e6\u05d9\u05d1",
                                "\u05db\u05de\u05d4 \u05d4\u05d5\u05e6\u05d0\u05ea\u05d9",
                                "\u05de\u05e6\u05d1 \u05d4\u05ea\u05e7\u05e6\u05d9\u05d1")):
        return True
    return False


# Monkey-patch anthropic.Anthropic so every messages.create() call
# updates the usage counter automatically. Single insertion point
# instead of wrapping ~10 call sites in jarvis.py.
try:
    from anthropic.resources.messages import Messages as _AnthMessages
    if not hasattr(_AnthMessages, "_jarvis_patched"):
        _orig_anth_create = _AnthMessages.create

        def _wrapped_anth_create(self, *args, **kwargs):
            response = _orig_anth_create(self, *args, **kwargs)
            try:
                _track_anthropic_usage(response)
            except Exception:
                pass
            return response

        _AnthMessages.create = _wrapped_anth_create
        _AnthMessages._jarvis_patched = True
        print("[diag] Anthropic usage tracking active (budget cap $%.0f/month)"
              % _BUDGET_USD, flush=True)
except Exception as _patch_err:
    print("[diag] anthropic usage tracking patch failed:",
          repr(_patch_err), flush=True)


# =====================================================================
# Vault backup (v4.31) - daily zip of Obsidian_Vault
# =====================================================================
BACKUP_DIR = Path("./backups")
BACKUP_KEEP = 14
VAULT_DIR = _VAULT_ROOT  # v5.20: absolute, see the note at SSD_OBSIDIAN_VAULT


def backup_vault():
    """Create a timestamped zip of VAULT_DIR under BACKUP_DIR and prune
    to BACKUP_KEEP newest. Returns a short status string for the spoken
    reply. Safe to call from a daemon thread - any error is logged and
    a friendly message returned. Never raises."""
    import zipfile
    try:
        if not VAULT_DIR.exists():
            return "No vault to back up, sir."
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        fname = BACKUP_DIR / ("obsidian_vault_" + ts + ".zip")
        n_files = 0
        total_bytes = 0
        skipped = 0
        with zipfile.ZipFile(fname, "w", zipfile.ZIP_DEFLATED,
                             compresslevel=6) as z:
            for f in VAULT_DIR.rglob("*"):
                if not f.is_file():
                    continue
                try:
                    arcname = f.relative_to(VAULT_DIR.parent)
                    z.write(f, arcname)
                    n_files += 1
                    total_bytes += f.stat().st_size
                except Exception as fe:
                    skipped += 1
                    print("[diag] backup skip:", f, repr(fe))
        # Prune older zips beyond BACKUP_KEEP
        existing = sorted(
            BACKUP_DIR.glob("obsidian_vault_*.zip"),
            key=lambda p: p.stat().st_mtime, reverse=True)
        pruned = 0
        for old in existing[BACKUP_KEEP:]:
            try:
                old.unlink()
                pruned += 1
            except Exception:
                pass
        size_mb = total_bytes / 1024.0 / 1024.0
        zip_size_mb = fname.stat().st_size / 1024.0 / 1024.0
        tail = ""
        if skipped:
            tail += " %d files skipped." % skipped
        if pruned:
            tail += " %d old backups pruned." % pruned
        return ("Backed up %d files - %.1f MB raw, %.1f MB zipped - "
                "to %s, sir. Keeping the last %d backups.%s"
                % (n_files, size_mb, zip_size_mb, fname.name,
                   BACKUP_KEEP, tail))
    except Exception as e:
        print("[diag] backup_vault failed:", repr(e))
        return "Backup failed, sir: %s" % e


def _backup_intercept(msg):
    """True if the user is asking to back up the vault."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "backup", "back up", "backup now", "back up now",
        "backup my notes", "back up my notes",
        "backup the vault", "backup my vault", "back up the vault",
        "backup the notes", "back up the notes",
        "create a backup", "create backup",
        "make a backup", "make backup",
        "run a backup", "run backup",
        "save a backup", "save backup",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05d2\u05d9\u05d1\u05d5\u05d9",
        "\u05d2\u05d1\u05d4",
        "\u05d2\u05d1\u05d4 \u05dc\u05d9",
        "\u05d2\u05d1\u05d4 \u05d0\u05ea \u05d4\u05e4\u05ea\u05e7\u05d9\u05dd",
        "\u05d2\u05d1\u05d4 \u05d0\u05ea \u05d4\u05db\u05e1\u05e4\u05ea",
        "\u05ea\u05d2\u05d1\u05d4",
        "\u05ea\u05d2\u05d1\u05d4 \u05dc\u05d9",
        "\u05ea\u05d2\u05d1\u05d4 \u05d0\u05ea \u05d4\u05e4\u05ea\u05e7\u05d9\u05dd",
        "\u05ea\u05d2\u05d1\u05d4 \u05d0\u05ea \u05d4\u05db\u05e1\u05e4\u05ea",
        "\u05ea\u05d9\u05e6\u05d5\u05e8 \u05d2\u05d9\u05d1\u05d5\u05d9",
        "\u05e2\u05e9\u05d4 \u05d2\u05d9\u05d1\u05d5\u05d9",
        "\u05e8\u05d5\u05e5 \u05d2\u05d9\u05d1\u05d5\u05d9",
        "\u05d4\u05e8\u05e5 \u05d2\u05d9\u05d1\u05d5\u05d9",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Decisions log (v4.32)
# =====================================================================
DECISIONS_FILE = _VAULT_ROOT / "Decisions.md"  # v5.20: absolute


def log_decision(text):
    """Append a timestamped decision to Obsidian_Vault/Decisions.md.
    Returns a short status string."""
    if not text or not text.strip():
        return "What decision should I log, sir?"
    try:
        DECISIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.datetime.now()
        new_file = not DECISIONS_FILE.exists()
        with open(DECISIONS_FILE, "a", encoding="utf-8") as f:
            if new_file:
                f.write("# Decisions Log\n\n")
            f.write("## %s\n%s\n\n"
                    % (now.strftime("%Y-%m-%d %H:%M"), text.strip()))
        return "Decision logged, sir."
    except Exception as e:
        return "Failed to log the decision, sir: %s" % e


def recent_decisions(n=5, lang="en"):
    """Read back the most recent n decisions with relative dates."""
    try:
        if not DECISIONS_FILE.exists():
            return ("עדיין לא רשמת החלטות, אדוני." if lang == "he"
                    else "No decisions logged yet, sir.")
        text = DECISIONS_FILE.read_text(encoding="utf-8")
        entries = re.findall(r"^## (.+?)\n(.+?)(?=\n## |\Z)", text,
                             re.MULTILINE | re.DOTALL)
        if not entries:
            return ("עדיין לא רשמת החלטות, אדוני." if lang == "he"
                    else "No decisions logged yet, sir.")
        recent = entries[-n:]
        recent.reverse()
        lines = []
        for when, body in recent:
            try:
                d = datetime.datetime.strptime(
                    when.strip(), "%Y-%m-%d %H:%M").date()
                days = (datetime.date.today() - d).days
                if lang == "he":
                    rel = ("היום" if days == 0 else
                           "אתמול" if days == 1 else
                           "לפני %d ימים" % days)
                else:
                    rel = ("today" if days == 0 else
                           "yesterday" if days == 1 else
                           "%d days ago" % days)
            except Exception:
                rel = when.strip()
            body_clean = " ".join(body.split())
            lines.append("%s: %s" % (rel, body_clean))
        facts = "\n".join(lines)
        if lang == "he":
            return "ההחלטות האחרונות שלך, אדוני:\n" + facts
        return "Your recent decisions, sir:\n" + facts
    except Exception as e:
        return "Couldn't read the decisions log, sir: %s" % e


def _decision_log_parse(msg):
    """If the message is 'log decision: X' / 'תרשום החלטה X', return X.
    Else None."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|note|save)\s+(?:a\s+|the\s+)?"
                 r"decision[:\-\s]+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05ea\u05e2\u05d3|\u05ea\u05ea\u05e2\u05d3)\s+"
                 r"(?:\u05dc\u05d9\s+)?(?:\u05d0\u05ea\s+)?(?:\u05d4)?"
                 r"\u05d4\u05d7\u05dc\u05d8\u05d4[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    return None


def _decision_review_intercept(msg):
    """True if the user is asking to review their decisions."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "my decisions", "show my decisions", "show decisions",
        "recent decisions", "list my decisions", "decision log",
        "what did i decide", "what have i decided",
        "read my decisions",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05d4\u05d4\u05d7\u05dc\u05d8\u05d5\u05ea \u05e9\u05dc\u05d9",
        "\u05d4\u05d7\u05dc\u05d8\u05d5\u05ea \u05d0\u05d7\u05e8\u05d5\u05e0\u05d5\u05ea",
        "\u05d4\u05d4\u05d7\u05dc\u05d8\u05d5\u05ea \u05d4\u05d0\u05d7\u05e8\u05d5\u05e0\u05d5\u05ea",
        "\u05de\u05d4 \u05d4\u05d7\u05dc\u05d8\u05ea\u05d9",
        "\u05d9\u05d5\u05de\u05df \u05d4\u05d7\u05dc\u05d8\u05d5\u05ea",
        "\u05ea\u05e8\u05d0\u05d4 \u05dc\u05d9 \u05d0\u05ea \u05d4\u05d4\u05d7\u05dc\u05d8\u05d5\u05ea",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Nutrition / macro tracker (v4.33) - reuses training_log.json
# =====================================================================
# v5.20: absolute for the same reason as the vault - a training log written
# to the wrong folder would read as an empty history, not as an error.
TRAINING_LOG_FILE = _FILES_DIR / "training_log.json"


def _load_training_log():
    if not TRAINING_LOG_FILE.exists():
        return {}
    try:
        return json.loads(TRAINING_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_training_log(data):
    """v5.20: write to a temp file, then rename over the real one.

    write_text truncates the target FIRST and then writes. A crash, a kill,
    or a power cut in that gap left training_log.json half-written - and
    that one file holds every weight, workout, injury and nutrition entry.
    os.replace is atomic on NTFS, so the file on disk is only ever the old
    complete version or the new complete version, never a torn one."""
    tmp = TRAINING_LOG_FILE.parent / (TRAINING_LOG_FILE.name + ".tmp")
    try:
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8")
        os.replace(tmp, TRAINING_LOG_FILE)
    except Exception as e:
        print("[diag] training log save failed:", repr(e))
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass


def _nutrition_reset_if_new_day(data):
    """Zero today's counters when the stored date isn't today. Mutates
    data in place; caller decides whether to save."""
    today = datetime.date.today().isoformat()
    if data.get("nutrition_date") != today:
        data["nutrition_date"] = today
        data["today_calories"] = 0
        data["today_protein_g"] = 0


def log_calories(n):
    try:
        n = int(round(float(n)))
    except Exception:
        return "How many calories, sir?"
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)
    data["today_calories"] = int(data.get("today_calories", 0)) + n
    _save_training_log(data)
    tgt = data.get("target_calories", 3000)
    total = data["today_calories"]
    return ("Logged %d calories, sir. Today's total: %d of %d."
            % (n, total, tgt))


def log_protein(g):
    try:
        g = int(round(float(g)))
    except Exception:
        return "How many grams of protein, sir?"
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)
    data["today_protein_g"] = int(data.get("today_protein_g", 0)) + g
    _save_training_log(data)
    tgt = data.get("target_protein_g", 130)
    total = data["today_protein_g"]
    return ("Logged %d grams of protein, sir. Today's total: %d of %d."
            % (g, total, tgt))


def nutrition_status(lang="en"):
    data = _load_training_log()
    _nutrition_reset_if_new_day(data)  # display-only; not saved
    cal = int(data.get("today_calories", 0))
    pro = int(data.get("today_protein_g", 0))
    tcal = data.get("target_calories", 3000)
    tpro = data.get("target_protein_g", 130)
    cal_left = tcal - cal
    pro_left = tpro - pro
    if lang == "he":
        return ("היום, אדוני: %d מתוך %d קלוריות (%d נותרו), "
                "%d מתוך %d גרם חלבון (%d נותרו)."
                % (cal, tcal, max(0, cal_left), pro, tpro,
                   max(0, pro_left)))
    return ("Today, sir: %d of %d calories (%d to go), %d of %d grams "
            "of protein (%d to go)."
            % (cal, tcal, max(0, cal_left), pro, tpro, max(0, pro_left)))


def _nutrition_log_parse(msg):
    """Parse a nutrition log command. Returns ('calories', N) or
    ('protein', N) or None. Requires a number, a unit word, and a
    logging verb so questions don't false-trigger."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    low = text.lower()
    en_verb = re.search(r"\b(log|ate|eaten|add|added|track|had|"
                        r"consumed|just had)\b", low)
    if en_verb:
        mp = re.search(r"(\d+(?:\.\d+)?)\s*(?:grams?|g)\s*(?:of\s+)?"
                       r"protein", low)
        if mp:
            return ("protein", float(mp.group(1)))
        mp2 = re.search(r"protein[:\s]+(\d+(?:\.\d+)?)", low)
        if mp2:
            return ("protein", float(mp2.group(1)))
        mc = re.search(r"(\d+(?:\.\d+)?)\s*(?:k?cals?|calories|calorie|"
                       r"kcal)\b", low)
        if mc:
            return ("calories", float(mc.group(1)))
    he_verb = re.search(r"(\u05d0\u05db\u05dc\u05ea\u05d9|\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05d4\u05d5\u05e1\u05e3|\u05ea\u05d5\u05e1\u05d9\u05e3|\u05e6\u05e8\u05db\u05ea\u05d9)", text)
    if he_verb:
        mp = re.search(r"(\d+(?:\.\d+)?)\s*(?:\u05d2\u05e8\u05dd\s+)?\u05d7\u05dc\u05d1\u05d5\u05df", text)
        if mp:
            return ("protein", float(mp.group(1)))
        mp2 = re.search(r"\u05d7\u05dc\u05d1\u05d5\u05df[:\s]+(\d+(?:\.\d+)?)", text)
        if mp2:
            return ("protein", float(mp2.group(1)))
        mc = re.search(r"(\d+(?:\.\d+)?)\s*(?:\u05e7\u05dc\u05d5\u05e8\u05d9\u05d5\u05ea|\u05e7\u05dc\u05d5\u05e8\u05d9\u05d4|\u05e7\u05e7\"\u05dc)", text)
        if mc:
            return ("calories", float(mc.group(1)))
    return None


def _nutrition_status_intercept(msg):
    """True if the user is asking about today's nutrition/macros."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "nutrition", "nutrition status", "my nutrition",
        "macros", "my macros", "macro status",
        "calories today", "how many calories today",
        "protein today", "how much protein today",
        "what have i eaten", "what have i eaten today",
        "food log", "diet status", "how am i eating",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05ea\u05d6\u05d5\u05e0\u05d4", "\u05de\u05e6\u05d1 \u05ea\u05d6\u05d5\u05e0\u05d4",
        "\u05de\u05d0\u05e7\u05e8\u05d5", "\u05d4\u05de\u05d0\u05e7\u05e8\u05d5 \u05e9\u05dc\u05d9",
        "\u05db\u05de\u05d4 \u05d0\u05db\u05dc\u05ea\u05d9",
        "\u05db\u05de\u05d4 \u05d0\u05db\u05dc\u05ea\u05d9 \u05d4\u05d9\u05d5\u05dd",
        "\u05e7\u05dc\u05d5\u05e8\u05d9\u05d5\u05ea \u05d4\u05d9\u05d5\u05dd",
        "\u05d7\u05dc\u05d1\u05d5\u05df \u05d4\u05d9\u05d5\u05dd",
        "\u05de\u05d4 \u05d0\u05db\u05dc\u05ea\u05d9 \u05d4\u05d9\u05d5\u05dd",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Self-test / quiz mode (v4.34)
# =====================================================================
_quiz_lock = threading.Lock()
_quiz_state = {"active": False, "question": "", "answer": "", "topic": ""}


def _pick_quiz_note(topic):
    """Find a knowledge note matching `topic` (or any note if topic is
    empty/unmatched). Returns (path, content) or (None, None)."""
    import random
    base = Path(KNOWLEDGE_DIR)
    if not base.exists():
        return None, None
    candidates = [f for f in base.rglob("*.md")
                  if not f.name.startswith("_")]
    if not candidates:
        return None, None
    if topic:
        slug = _slugify_topic(topic)
        matched = []
        for f in candidates:
            dom = _slugify_topic(f.parent.name)
            if (slug and (slug in dom or dom in slug
                          or slug in f.stem.lower())):
                matched.append(f)
        if matched:
            candidates = matched
    note = random.choice(candidates)
    try:
        content = note.read_text(encoding="utf-8")[:6000]
    except Exception:
        return None, None
    return note, content


def start_quiz(topic, lang="en"):
    """Pick a note, generate one question + model answer, store as
    pending, and return the question text to speak."""
    if not ANTHROPIC_API_KEY:
        return ("לא ניתן להריץ חידון - מפתח Anthropic לא מוגדר, אדוני."
                if lang == "he"
                else "Can't run a quiz - the Anthropic key isn't set, sir.")
    note, content = _pick_quiz_note(topic)
    if not content:
        if topic:
            return (("אין לי פתקי ידע על %s עדיין, אדוני. בקש ממני "
                     "ללמוד את זה קודם." % topic) if lang == "he"
                    else ("I don't have knowledge notes on %s yet, sir. "
                          "Ask me to learn it first." % topic))
        return ("אין לי פתקי ידע לבחון אותך עליהם עדיין, אדוני."
                if lang == "he"
                else "I have no knowledge notes to quiz you on yet, sir.")
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are a quizmaster. From the study note below, write ONE "
            "clear exam-style question that tests real understanding "
            "(not trivia), plus a concise model answer. Output EXACTLY "
            "two lines and nothing else:\nQ: <question>\nA: <model "
            "answer>\nWrite in "
            + ("Hebrew" if lang == "he" else "English") + ".")
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=400,
            system=sys_p,
            messages=[{"role": "user", "content": content}])
        txt = " ".join(b.text for b in r.content
                       if getattr(b, "type", None) == "text").strip()
        mq = re.search(r"Q:\s*(.+?)(?:\nA:|A:)", txt, re.DOTALL)
        ma = re.search(r"A:\s*(.+)$", txt, re.DOTALL)
        if not mq or not ma:
            return ("לא הצלחתי לנסח שאלה, אדוני. נסה שוב."
                    if lang == "he"
                    else "I couldn't form a question, sir. Try again.")
        q = mq.group(1).strip()
        a = ma.group(1).strip()
    except Exception as e:
        return "Quiz generation failed, sir: %s" % e
    with _quiz_lock:
        _quiz_state.update(active=True, question=q, answer=a,
                           topic=(topic or note.stem))
    if lang == "he":
        return "שאלה, אדוני: " + q + " אמור את התשובה כשתהיה מוכן."
    return "Question, sir: " + q + " Tell me your answer when ready."


def evaluate_quiz_answer(user_answer, lang="en"):
    """Grade the user's answer against the pending question and clear
    the pending state. Returns feedback text, or None if no quiz is
    pending (so think() falls through to normal handling)."""
    with _quiz_lock:
        if not _quiz_state["active"]:
            return None
        q = _quiz_state["question"]
        expected = _quiz_state["answer"]
        _quiz_state.update(active=False, question="", answer="", topic="")
    ans = (user_answer or "").strip()
    cancel = {"stop", "cancel", "never mind", "nevermind", "forget it",
              "\u05e2\u05d6\u05d5\u05d1", "\u05d1\u05d8\u05dc", "\u05e2\u05e6\u05d5\u05e8",
              "\u05d3\u05d9", "\u05dc\u05d0 \u05e2\u05db\u05e9\u05d9\u05d5"}
    # v4.67: always let the user bail - match cancel words anywhere, not just an
    # exact whole-string equality (so "stop the quiz" / cancel-anywhere works).
    _al = ans.lower()
    _words = set(re.split(r"[\s,.!?]+", _al))
    if (_al in cancel or ans in cancel
            or _words & {"stop", "cancel", "forget", "nevermind"}
            or any(w in ans for w in ("\u05e2\u05d6\u05d5\u05d1", "\u05d1\u05d8\u05dc", "\u05e2\u05e6\u05d5\u05e8"))):
        return ("ביטלתי את החידון, אדוני." if lang == "he"
                else "Quiz cancelled, sir.")
    if not ANTHROPIC_API_KEY:
        return (("התשובה שחיפשתי, אדוני: " + expected) if lang == "he"
                else ("The expected answer, sir: " + expected))
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are a supportive but honest tutor grading a spoken "
            "answer. Given the question, the model answer, and the "
            "student's answer, say in 2-3 sentences whether the student "
            "was correct, partially correct, or wrong, and give the key "
            "point they missed if any. Address them as 'sir' (or "
            "'אדוני'). Write in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Plain text, no markdown.")
        prompt = ("Question: %s\nModel answer: %s\nStudent's answer: %s"
                  % (q, expected, ans))
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=300,
            system=sys_p,
            messages=[{"role": "user", "content": prompt}])
        fb = " ".join(b.text for b in r.content
                      if getattr(b, "type", None) == "text").strip()
        return clean_text(fb) or ("The expected answer was: " + expected)
    except Exception as e:
        return ("Couldn't grade that, sir: %s. Expected answer: %s"
                % (e, expected))


def _quiz_start_parse(msg):
    """Return the quiz topic (possibly an empty string for 'no specific
    topic') if the message is a quiz request, else None."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    m = re.match(r"(?:quiz|test)\s+me(?:\s+on\s+(.+))?$", low)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"(?:give me a quiz|quiz time|test my knowledge|"
                 r"self test|self-test)(?:\s+on\s+(.+))?$", low)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"(?:\u05ea\u05d1\u05d7\u05df|\u05ea\u05e9\u05d0\u05dc|\u05e9\u05d0\u05dc)\s+\u05d0\u05d5\u05ea\u05d9(?:\s+\u05e2\u05dc\s+(.+))?$", text)
    if m:
        return (m.group(1) or "").strip()
    m = re.match(r"\u05d7\u05d9\u05d3\u05d5\u05df(?:\s+\u05e2\u05dc\s+(.+))?$", text)
    if m:
        return (m.group(1) or "").strip()
    return None


# =====================================================================
# Injury / recovery tracker (v4.35) - reuses training_log.json
# =====================================================================
def log_injury(text, lang="en"):
    """Append an injury entry to training_log.json (injuries list)."""
    if not text or not text.strip():
        return ("איזו פציעה לרשום, אדוני?" if lang == "he"
                else "What injury should I log, sir?")
    data = _load_training_log()
    injuries = data.setdefault("injuries", [])
    injuries.append({
        "desc": text.strip(),
        "logged": datetime.date.today().isoformat(),
        "status": "active",
        "recovered": None,
    })
    _save_training_log(data)
    if lang == "he":
        return "רשמתי את הפציעה, אדוני: %s. תנוח." % text.strip()
    return "Injury logged, sir: %s. Rest up." % text.strip()


def injury_status(lang="en"):
    """Report active injuries with relative dates."""
    data = _load_training_log()
    injuries = data.get("injuries", [])
    active = [i for i in injuries if i.get("status") == "active"]
    if not active:
        return ("אין פציעות פעילות, אדוני. הכל תקין." if lang == "he"
                else "No active injuries, sir. All clear.")
    lines = []
    for inj in active:
        try:
            d = datetime.date.fromisoformat(inj.get("logged", ""))
            days = (datetime.date.today() - d).days
            if lang == "he":
                rel = ("היום" if days == 0 else "אתמול" if days == 1
                       else "לפני %d ימים" % days)
            else:
                rel = ("today" if days == 0 else "yesterday" if days == 1
                       else "%d days ago" % days)
        except Exception:
            rel = ""
        desc = inj.get("desc", "?")
        lines.append(("%s (%s)" % (desc, rel)) if rel else desc)
    facts = "; ".join(lines)
    if lang == "he":
        return "פציעות פעילות, אדוני: " + facts
    return "Active injuries, sir: " + facts


def mark_recovered(keyword, lang="en"):
    """Mark a matching active injury as recovered. If exactly one is
    active, a keyword isn't required."""
    data = _load_training_log()
    injuries = data.get("injuries", [])
    kw = (keyword or "").strip().lower()
    matched = None
    if kw:
        for inj in injuries:
            if (inj.get("status") == "active"
                    and kw in inj.get("desc", "").lower()):
                matched = inj
                break
    if matched is None:
        active = [i for i in injuries if i.get("status") == "active"]
        if len(active) == 1:
            matched = active[0]
    if matched is None:
        return ("לא מצאתי פציעה פעילה שמתאימה, אדוני." if lang == "he"
                else "I couldn't find a matching active injury, sir.")
    matched["status"] = "recovered"
    matched["recovered"] = datetime.date.today().isoformat()
    _save_training_log(data)
    desc = matched.get("desc", "")
    if lang == "he":
        return "מצוין, אדוני. סימנתי כהחלים: " + desc
    return "Great, sir. Marked as recovered: " + desc


def _injury_log_parse(msg):
    """'log injury: X' / 'I hurt my X' / 'תרשום פציעה X' -> X, else None."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip()
    m = re.match(r"(?:log|record|note)\s+(?:an?\s+)?injury[:\-\s]+(.+)$",
                 text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"i\s+(?:hurt|injured|strained|pulled|tweaked)\s+"
                 r"(?:my\s+)?(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05ea\u05e2\u05d3)\s+"
                 r"(?:\u05dc\u05d9\s+)?(?:\u05d0\u05ea\s+)?\u05e4\u05e6\u05d9\u05e2\u05d4[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"\u05e0\u05e4\u05e6\u05e2\u05ea\u05d9\s+(?:\u05d1|\u05d1\u05d0\u05d6\u05d5\u05e8\s+)?(.+)$", text)
    if m:
        return m.group(1).strip()
    return None


def _injury_recovered_parse(msg):
    """'injury recovered: X' / 'my X has healed' / 'החלמתי מX' -> X."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    m = re.match(r"(?:injury\s+recovered|recovered\s+from|healed\s+from)"
                 r"[:\-\s]+(.+)$", text, re.I)
    if m:
        return m.group(1).strip()
    # v4.67: require a "my <body-part>" shape so generic sentences like
    # "everything is better" / "the weather is better" don't falsely clear an
    # injury (mark_recovered would otherwise fall back to the single active one).
    m = re.match(r"my\s+([\w' ]{1,20}?)\s+(?:has\s+|is\s+)?(?:healed|recovered|"
                 r"better)$", text, re.I)
    if m and len(m.group(1).split()) <= 3:
        return m.group(1).strip()
    m = re.match(r"(?:\u05d4\u05d7\u05dc\u05de\u05ea\u05d9|\u05e0\u05e8\u05e4\u05d0\u05ea\u05d9)\s+"
                 r"(?:\u05de\u05d4|\u05de)?(.+)$", text)
    if m:
        return m.group(1).strip()
    return None


def _injury_status_intercept(msg):
    """True if the user is asking about injury status."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "injury status", "injuries", "my injuries",
        "am i injured", "injury report", "any injuries",
        "what injuries", "current injuries", "injury check",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05de\u05e6\u05d1 \u05e4\u05e6\u05d9\u05e2\u05d5\u05ea",
        "\u05e4\u05e6\u05d9\u05e2\u05d5\u05ea",
        "\u05d4\u05e4\u05e6\u05d9\u05e2\u05d5\u05ea \u05e9\u05dc\u05d9",
        "\u05de\u05d4 \u05d4\u05e4\u05e6\u05d9\u05e2\u05d5\u05ea",
        "\u05d9\u05e9 \u05dc\u05d9 \u05e4\u05e6\u05d9\u05e2\u05d5\u05ea",
        "\u05d3\u05d5\u05d7 \u05e4\u05e6\u05d9\u05e2\u05d5\u05ea",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Workout logging (v4.36) - combat fitness coach, brick 1
# reuses training_log.json + updates v4.28 briefing fields
# =====================================================================
def _classify_workout(text):
    """Return a coarse workout type from keywords. Hebrew keywords use
    plain substring; English uses word boundaries so 'ran' does not match
    inside 'random' / 'brand' / 'France'."""
    low = (text or "").lower()
    he_swim = ["\u05e9\u05d7\u05d9\u05ea\u05d9", "\u05e9\u05d7\u05d9\u05d9\u05d4", "\u05e9\u05d7\u05d9\u05d4"]
    he_cardio = ["\u05e8\u05e6\u05ea\u05d9", "\u05e8\u05d9\u05e6\u05d4", "\u05e8\u05e5", "\u05d0\u05d5\u05e4\u05e0\u05d9\u05d9\u05dd",
                 "\u05e7\u05e8\u05d3\u05d9\u05d5", "\u05e1\u05e4\u05e8\u05d9\u05e0\u05d8"]
    he_strength = ["\u05e1\u05e7\u05d5\u05d5\u05d0\u05d8", "\u05dc\u05d7\u05d9\u05e6\u05d4", "\u05d3\u05d3\u05dc\u05d9\u05e4\u05d8",
                   "\u05de\u05e9\u05e7\u05d5\u05dc\u05d5\u05ea", "\u05db\u05d5\u05d7", "\u05e1\u05d8\u05d9\u05dd", "\u05d7\u05d6\u05e8\u05d5\u05ea",
                   "\u05de\u05ea\u05d7", "\u05e9\u05db\u05d9\u05d1\u05d5\u05ea", "\u05e7\u05d9\u05dc\u05d5", "\u05e8\u05d2\u05dc\u05d9\u05d9\u05dd",
                   "\u05d7\u05d6\u05d4", "\u05d2\u05d1", "\u05db\u05ea\u05e4\u05d9\u05d9\u05dd", "\u05d9\u05d3\u05d9\u05d9\u05dd", "\u05d1\u05d8\u05df",
                   "\u05d1\u05d9\u05e6\u05e4\u05e1", "\u05d8\u05e8\u05d9\u05e6\u05e4\u05e1"]
    en_swim = ["swim", "swam", "swimming"]
    en_cardio = ["run", "running", "ran", "jog", "jogging", "jogged",
                 "cardio", "cycle", "cycling", "bike", "biked", "row",
                 "rowing", "sprint", "sprinted", "treadmill", "5k", "10k"]
    en_strength = ["squat", "squats", "bench", "deadlift", "press", "lift",
                   "lifted", "lifting", "sets", "set", "reps", "rep", "kg",
                   "pullup", "pull-up", "pull up", "pullups", "pushup",
                   "push-up", "push up", "pushups", "curl", "curls", "ohp",
                   "chest", "back", "legs", "leg", "shoulders", "arms",
                   "biceps", "triceps", "glutes", "abs", "quads",
                   "hamstrings", "calves", "upper body", "lower body"]
    for kw in he_swim:
        if kw in low:
            return "swim"
    for kw in he_cardio:
        if kw in low:
            return "cardio"
    for kw in he_strength:
        if kw in low:
            return "strength"

    def _has(kw):
        return re.search(r"\b" + re.escape(kw) + r"\b", low) is not None

    for kw in en_swim:
        if _has(kw):
            return "swim"
    for kw in en_cardio:
        if _has(kw):
            return "cardio"
    for kw in en_strength:
        if _has(kw):
            return "strength"
    return "general"


def _iso_week_tag(d=None):
    d = d or datetime.date.today()
    iso = d.isocalendar()
    return "%d-W%02d" % (iso[0], iso[1])


def log_workout(text, lang="en"):
    """Append a workout and refresh v4.28 briefing fields."""
    if not text or not text.strip():
        return ("איזה אימון לרשום, אדוני?" if lang == "he"
                else "What workout should I log, sir?")
    data = _load_training_log()
    workouts = data.setdefault("workouts", [])
    today = datetime.date.today().isoformat()
    wtype = _classify_workout(text)
    workouts.append({"desc": text.strip(), "type": wtype, "date": today})
    # fields the v4.28 briefing reads
    data["last_workout_type"] = wtype
    data["last_workout_date"] = today
    wk = _iso_week_tag()
    if data.get("workout_week") != wk:
        data["workout_week"] = wk
        data["weekly_workouts"] = 0
    try:
        data["weekly_workouts"] = int(data.get("weekly_workouts", 0)) + 1
    except Exception:
        data["weekly_workouts"] = 1
    _save_training_log(data)
    n = data["weekly_workouts"]
    if lang == "he":
        return "נרשם, אדוני: %s. זה אימון מספר %d השבוע." % (text.strip(), n)
    return "Logged, sir: %s. That's workout #%d this week." % (text.strip(), n)


def recent_workouts(lang="en"):
    """Report this week's count and the last 5 workouts."""
    data = _load_training_log()
    workouts = data.get("workouts", [])
    if not workouts:
        return ("עדיין לא תיעדת אימונים, אדוני." if lang == "he"
                else "No workouts logged yet, sir.")
    wk = _iso_week_tag()
    week_count = 0
    if data.get("workout_week") == wk:
        try:
            week_count = int(data.get("weekly_workouts", 0))
        except Exception:
            week_count = 0
    type_he = {"cardio": "\u05e7\u05e8\u05d3\u05d9\u05d5", "swim": "\u05e9\u05d7\u05d9\u05d9\u05d4",
               "strength": "\u05db\u05d5\u05d7", "general": "\u05db\u05dc\u05dc\u05d9"}
    last5 = workouts[-5:][::-1]
    lines = []
    for w in last5:
        try:
            d = datetime.date.fromisoformat(w.get("date", ""))
            days = (datetime.date.today() - d).days
            if lang == "he":
                rel = ("היום" if days == 0 else "אתמול" if days == 1
                       else "לפני %d ימים" % days)
            else:
                rel = ("today" if days == 0 else "yesterday" if days == 1
                       else "%d days ago" % days)
        except Exception:
            rel = ""
        desc = w.get("desc", "?")
        t = w.get("type", "")
        if lang == "he":
            tlabel = type_he.get(t, t)
            lines.append("%s [%s] (%s)" % (desc, tlabel, rel) if rel
                         else "%s [%s]" % (desc, tlabel))
        else:
            lines.append("%s [%s] (%s)" % (desc, t, rel) if rel
                         else "%s [%s]" % (desc, t))
    body = "; ".join(lines)
    if lang == "he":
        return "השבוע: %d אימונים, אדוני. אחרונים: %s" % (week_count, body)
    return "This week: %d workouts, sir. Recent: %s" % (week_count, body)


# v4.67: a bare cardio verb ("ran"/"swam"/"רצתי"...) only counts as a workout
# when it carries workout context (a number, distance/time unit, or gym noun) -
# so "I ran the tests" / "רצתי לחנות" are NOT logged as workouts.
_WORKOUT_CTX = re.compile(
    r"\d|\bkm\b|\bk\b|\bmiles?\b|\bmin(?:ute)?s?\b|\bhours?\b|\breps?\b|"
    r"\bsets?\b|\blaps?\b|\bkg\b|\bmarathon\b|\btreadmill\b|\bpool\b|\bgym\b|"
    r"ק\"?מ|מטר|דקות|חזרות|סטים|קילומטר|בריכה|מרתון|הקפות",
    re.IGNORECASE)

def _workout_log_parse(msg):
    """'log workout: X' / 'I trained X' / 'I ran X' / 'תרשום אימון X' /
    'רצתי X' -> the workout description, else None."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip()
    # explicit "log workout: X"
    m = re.match(r"(?:log|record|add)\s+(?:a\s+)?workout[:\-\s]+(.+)$",
                 text, re.I)
    if m:
        return m.group(1).strip()
    # "I did a workout: ..." / "I did my workout ..."
    m = re.match(r"i\s+(?:did|completed|finished)\s+(?:a\s+|my\s+)?"
                 r"workout\b[:\-\s]*(.*)$", text, re.I)
    if m:
        rest = m.group(1).strip()
        return rest if rest else "workout"
    # "I trained X" / "I worked out (X)"
    m = re.match(r"i\s+trained\s+(.+)$", text, re.I)
    if m:
        return "trained " + m.group(1).strip()
    m = re.match(r"i\s+worked\s+out\b[:\-\s]*(.*)$", text, re.I)
    if m:
        rest = m.group(1).strip()
        return ("worked out " + rest) if rest else "worked out"
    # cardio/strength verbs: "I ran 5k", "ran 5k", "I swam 1000m", "I lifted"
    m = re.match(r"i\s+(ran|swam|lifted|rowed|cycled|biked|sprinted|jogged)"
                 r"\b\s*(.*)$", text, re.I)
    if m and _WORKOUT_CTX.search(m.group(2)):
        return (m.group(1) + " " + m.group(2)).strip()
    m = re.match(r"(ran|swam|jogged|sprinted)\b\s+(.+)$", text, re.I)
    if m and _WORKOUT_CTX.search(m.group(2)):
        return (m.group(1) + " " + m.group(2)).strip()
    # Hebrew explicit
    m = re.match(r"(?:\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05ea\u05e2\u05d3)\s+"
                 r"(?:\u05dc\u05d9\s+)?(?:\u05d0\u05ea\s+)?\u05d0\u05d9\u05de\u05d5\u05df[:\-\s]+(.+)$", text)
    if m:
        return m.group(1).strip()
    # Hebrew verbs: 'אימנתי X', 'התאמנתי X', 'רצתי X', 'שחיתי X', 'עשיתי אימון X'
    m = re.match(r"(?:\u05d0\u05d9\u05de\u05e0\u05ea\u05d9|\u05d4\u05ea\u05d0\u05de\u05e0\u05ea\u05d9)\s+(.+)$", text)
    if m:
        return m.group(1).strip()
    m = re.match(r"(?:\u05e8\u05e6\u05ea\u05d9|\u05e9\u05d7\u05d9\u05ea\u05d9)\s+(.+)$", text)
    if m and _WORKOUT_CTX.search(m.group(1)):
        return (text).strip()
    m = re.match(r"\u05e2\u05e9\u05d9\u05ea\u05d9\s+\u05d0\u05d9\u05de\u05d5\u05df\b[:\-\s]*(.*)$", text)
    if m:
        rest = m.group(1).strip()
        return ("\u05d0\u05d9\u05de\u05d5\u05df " + rest) if rest else "\u05d0\u05d9\u05de\u05d5\u05df"
    return None


def _workout_status_intercept(msg):
    """True if the user is asking about workout history/status."""
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en_triggers = {
        "workout status", "my workouts", "recent workouts",
        "what did i train this week", "what have i trained this week",
        "workouts this week", "training this week", "workout report",
        "how many workouts this week", "my training",
    }
    if low in en_triggers:
        return True
    he_triggers = {
        "\u05de\u05e6\u05d1 \u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd",
        "\u05d4\u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd \u05e9\u05dc\u05d9",
        "\u05de\u05d4 \u05d0\u05d9\u05de\u05e0\u05ea\u05d9 \u05d4\u05e9\u05d1\u05d5\u05e2",
        "\u05db\u05de\u05d4 \u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd \u05d4\u05e9\u05d1\u05d5\u05e2",
        "\u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd \u05d4\u05e9\u05d1\u05d5\u05e2",
        "\u05d3\u05d5\u05d7 \u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd",
    }
    if text in he_triggers:
        return True
    return False


# =====================================================================
# Fitness benchmarks & progress (v4.37) - combat coach brick 2
# structured test results + progress vs EDITABLE targets in
# training_log.json["standards"]. Reuses v4.33 _load/_save_training_log.
# =====================================================================
_FITNESS_METRICS = {
    "run_2km":   {"unit": "sec",   "default": 480, "lower_better": True,
                  "label_en": "2km run",   "label_he": "\u05e8\u05d9\u05e6\u05ea 2 \u05e7\"\u05de"},
    "run_3km":   {"unit": "sec",   "default": 750, "lower_better": True,
                  "label_en": "3km run",   "label_he": "\u05e8\u05d9\u05e6\u05ea 3 \u05e7\"\u05de"},
    "pullups":   {"unit": "count", "default": 15,  "lower_better": False,
                  "label_en": "pull-ups",  "label_he": "\u05de\u05ea\u05d7"},
    "pushups":   {"unit": "count", "default": 60,  "lower_better": False,
                  "label_en": "push-ups",  "label_he": "\u05e9\u05db\u05d9\u05d1\u05d5\u05ea \u05e1\u05de\u05d9\u05db\u05d4"},
    "situps":    {"unit": "count", "default": 70,  "lower_better": False,
                  "label_en": "sit-ups",   "label_he": "\u05db\u05e4\u05d9\u05e4\u05d5\u05ea \u05d1\u05d8\u05df"},
    "swim_400m": {"unit": "sec",   "default": 480, "lower_better": True,
                  "label_en": "400m swim", "label_he": "\u05e9\u05d7\u05d9\u05d9\u05ea 400 \u05de'"},
}
# Order for reporting
_FITNESS_ORDER = ["run_2km", "run_3km", "pullups", "pushups", "situps",
                  "swim_400m"]


def _fmt_metric_value(key, val):
    """sec -> mm:ss, count -> integer string."""
    meta = _FITNESS_METRICS.get(key, {})
    if meta.get("unit") == "sec":
        try:
            v = int(round(float(val)))
            return "%d:%02d" % (v // 60, v % 60)
        except Exception:
            return str(val)
    try:
        return str(int(round(float(val))))
    except Exception:
        return str(val)


def _parse_mmss_to_sec(text):
    """'8:45' -> 525. Returns int seconds or None."""
    m = re.search(r"(\d{1,2}):(\d{2})", text or "")
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    return None


def _fitness_label(key, lang):
    meta = _FITNESS_METRICS.get(key, {})
    return meta.get("label_he" if lang == "he" else "label_en", key)


def _get_target(data, key):
    std = data.get("standards", {}) or {}
    if key in std:
        return std[key]
    return _FITNESS_METRICS[key]["default"]


def _detect_fitness_metric(text):
    """Return a metric key from keywords in text, else None."""
    low = (text or "").lower()
    # runs need a distance marker
    if re.search(r"\b3\s*k(?:m)?\b", low) or "\u05e8\u05d9\u05e6\u05ea 3" in low or "3 \u05e7\u05de" in low or "3 \u05e7\"\u05de" in low:
        return "run_3km"
    if re.search(r"\b2\s*k(?:m)?\b", low) or "\u05e8\u05d9\u05e6\u05ea 2" in low or "2 \u05e7\u05de" in low or "2 \u05e7\"\u05de" in low:
        return "run_2km"
    if "pull" in low or "\u05de\u05ea\u05d7" in low:
        return "pullups"
    if "push" in low or "\u05e9\u05db\u05d9\u05d1\u05d5\u05ea" in low:
        return "pushups"
    if "situp" in low or "sit-up" in low or "sit up" in low or "\u05d1\u05d8\u05df" in low or "\u05db\u05e4\u05d9\u05e4\u05d5\u05ea" in low:
        return "situps"
    if "swim" in low or "\u05e9\u05d7\u05d9\u05d9\u05d4" in low or "\u05e9\u05d7\u05d9\u05d4" in low or "\u05e9\u05d7\u05d9\u05d9\u05ea" in low:
        return "swim_400m"
    # bare 'run' with a time -> assume 2km
    if ("run" in low or "\u05e8\u05d9\u05e6\u05d4" in low or "\u05e8\u05e6\u05ea\u05d9" in low) and _parse_mmss_to_sec(low) is not None:
        return "run_2km"
    return None


def _fitness_test_parse(msg):
    """Parse a test-log command. Returns (metric_key, value) or None.
    value is seconds for time metrics, an int count otherwise."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip()
    # require an explicit log/record verb so questions don't fire
    m = re.match(r"(?:log|record|add)\s+(?:a\s+|my\s+)?(?:fitness\s+)?"
                 r"(?:test|result)?[:\-\s]*(.+)$", text, re.I)
    if m:
        body = m.group(1).strip()
    else:
        mh = re.match(r"(?:\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05ea\u05e2\u05d3)\s+"
                      r"(?:\u05dc\u05d9\s+)?(?:\u05d0\u05ea\s+)?(?:\u05de\u05d1\u05d3\u05e7|\u05ea\u05d5\u05e6\u05d0\u05d4)?[:\-\s]*(.+)$",
                      text)
        if mh:
            body = mh.group(1).strip()
        else:
            return None
    key = _detect_fitness_metric(body)
    if key is None:
        return None
    unit = _FITNESS_METRICS[key]["unit"]
    if unit == "sec":
        sec = _parse_mmss_to_sec(body)
        if sec is None:
            return None
        return (key, sec)
    nums = re.findall(r"\d{1,3}", body)
    # drop distance markers like the '2'/'3' in 2k/3k and '400' for swim
    nums = [n for n in nums if n not in ("2", "3", "400") or len(nums) == 1]
    if not nums:
        return None
    return (key, int(nums[-1]))


def log_fitness_test(parsed, lang="en"):
    key, value = parsed
    data = _load_training_log()
    tests = data.setdefault("fitness_tests", [])
    tests.append({"metric": key, "value": value,
                  "date": datetime.date.today().isoformat()})
    _save_training_log(data)
    target = _get_target(data, key)
    disp = _fmt_metric_value(key, value)
    tdisp = _fmt_metric_value(key, target)
    label = _fitness_label(key, lang)
    lower = _FITNESS_METRICS[key]["lower_better"]
    met = (value <= target) if lower else (value >= target)
    if lang == "he":
        verdict = "\u05e2\u05d1\u05e8\u05ea \u05d0\u05ea \u05d4\u05d9\u05e2\u05d3! \ud83d\udd25" if met else ("\u05d4\u05d9\u05e2\u05d3: " + tdisp)
        return "\u05e0\u05e8\u05e9\u05dd, \u05d0\u05d3\u05d5\u05e0\u05d9: %s %s. %s" % (label, disp, verdict)
    verdict = "Target beaten! \ud83d\udd25" if met else ("Target: " + tdisp)
    return "Logged, sir: %s %s. %s" % (label, disp, verdict)


def _set_target_parse(msg):
    """'set target pullups 20' / 'יעד מתח 20' -> (key, value) or None."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = text.strip()
    m = re.match(r"(?:set\s+)?(?:target|goal|standard)[:\-\s]+(.+)$",
                 text, re.I)
    if not m:
        mh = re.match(r"(?:\u05d9\u05e2\u05d3|\u05ea\u05e7\u05df)[:\-\s]+(.+)$", text)
        if not mh:
            return None
        body = mh.group(1).strip()
    else:
        body = m.group(1).strip()
    key = _detect_fitness_metric(body)
    if key is None:
        return None
    unit = _FITNESS_METRICS[key]["unit"]
    if unit == "sec":
        sec = _parse_mmss_to_sec(body)
        if sec is None:
            return None
        return (key, sec)
    nums = [n for n in re.findall(r"\d{1,3}", body)
            if n not in ("2", "3", "400")]
    if not nums:
        return None
    return (key, int(nums[-1]))


def set_fitness_target(parsed, lang="en"):
    key, value = parsed
    data = _load_training_log()
    std = data.setdefault("standards", {})
    std[key] = value
    _save_training_log(data)
    label = _fitness_label(key, lang)
    disp = _fmt_metric_value(key, value)
    if lang == "he":
        return "\u05d4\u05d9\u05e2\u05d3 \u05dc%s \u05e2\u05d5\u05d3\u05db\u05df \u05dc-%s, \u05d0\u05d3\u05d5\u05e0\u05d9." % (label, disp)
    return "Target for %s set to %s, sir." % (label, disp)


def fitness_progress(lang="en"):
    data = _load_training_log()
    tests = data.get("fitness_tests", [])
    lines = []
    for key in _FITNESS_ORDER:
        meta = _FITNESS_METRICS[key]
        label = _fitness_label(key, lang)
        target = _get_target(data, key)
        tdisp = _fmt_metric_value(key, target)
        mine = [t for t in tests if t.get("metric") == key]
        if not mine:
            if lang == "he":
                lines.append("%s: \u05d8\u05e8\u05dd \u05e0\u05d1\u05d3\u05e7 (\u05d9\u05e2\u05d3 %s)" % (label, tdisp))
            else:
                lines.append("%s: not tested yet (target %s)" % (label, tdisp))
            continue
        latest = mine[-1]
        lval = latest.get("value")
        ldisp = _fmt_metric_value(key, lval)
        lower = meta["lower_better"]
        met = (lval <= target) if lower else (lval >= target)
        # delta vs previous test
        deltastr = ""
        if len(mine) > 1:
            pval = mine[-2].get("value")
            if meta["unit"] == "sec":
                diff = pval - lval  # positive = faster now
                if diff != 0:
                    sgn = "-" if diff > 0 else "+"
                    deltastr = (" (%s%ss \u05de\u05d4\u05e4\u05e2\u05dd \u05d4\u05e7\u05d5\u05d3\u05de\u05ea)" if lang == "he"
                                else " (%s%ss vs last)") % (sgn, abs(int(diff)))
            else:
                diff = lval - pval  # positive = more reps now
                if diff != 0:
                    sgn = "+" if diff > 0 else "-"
                    deltastr = (" (%s%d \u05de\u05d4\u05e4\u05e2\u05dd \u05d4\u05e7\u05d5\u05d3\u05de\u05ea)" if lang == "he"
                                else " (%s%d vs last)") % (sgn, abs(int(diff)))
        if lang == "he":
            mark = "\u2705" if met else "\u25cb"
            lines.append("%s %s: %s / \u05d9\u05e2\u05d3 %s%s" % (mark, label, ldisp, tdisp, deltastr))
        else:
            mark = "\u2705" if met else "\u25cb"
            lines.append("%s %s: %s / target %s%s" % (mark, label, ldisp, tdisp, deltastr))
    if lang == "he":
        return "\u05de\u05e6\u05d1 \u05db\u05d5\u05e9\u05e8, \u05d0\u05d3\u05d5\u05e0\u05d9:\n" + "\n".join(lines)
    return "Fitness progress, sir:\n" + "\n".join(lines)


def _fitness_progress_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"progress", "fitness progress", "where do i stand",
          "how am i doing", "fitness status", "my progress",
          "am i ready", "standards"}
    if low in en:
        return True
    he = {"\u05de\u05e6\u05d1 \u05db\u05d5\u05e9\u05e8", "\u05d0\u05d9\u05e4\u05d4 \u05d0\u05e0\u05d9 \u05e2\u05d5\u05de\u05d3", "\u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea",
          "\u05db\u05d5\u05e9\u05e8", "\u05d4\u05ea\u05e7\u05d3\u05de\u05d5\u05ea \u05e9\u05dc\u05d9", "\u05d0\u05e0\u05d9 \u05de\u05d5\u05db\u05df"}
    if text in he:
        return True
    return False


# =====================================================================
# Weekly training summary (v4.38) - combat coach brick 3 (read-only)
# =====================================================================
def _this_iso_week(d=None):
    d = d or datetime.date.today()
    return d.isocalendar()[:2]


def weekly_summary(lang="en"):
    data = _load_training_log()
    today = datetime.date.today()
    wk = _this_iso_week(today)
    parts = []

    # --- workouts this week ---
    workouts = data.get("workouts", [])
    wk_workouts = []
    for w in workouts:
        try:
            d = datetime.date.fromisoformat(w.get("date", ""))
            if d.isocalendar()[:2] == wk:
                wk_workouts.append(w)
        except Exception:
            pass
    type_he = {"cardio": "\u05e7\u05e8\u05d3\u05d9\u05d5", "swim": "\u05e9\u05d7\u05d9\u05d9\u05d4",
               "strength": "\u05db\u05d5\u05d7", "general": "\u05db\u05dc\u05dc\u05d9"}
    counts = {}
    for w in wk_workouts:
        t = w.get("type", "general")
        counts[t] = counts.get(t, 0) + 1
    if wk_workouts:
        if lang == "he":
            bd = ", ".join("%d %s" % (n, type_he.get(t, t))
                           for t, n in sorted(counts.items()))
            parts.append("\u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd: %d (%s)" % (len(wk_workouts), bd))
        else:
            bd = ", ".join("%d %s" % (n, t) for t, n in sorted(counts.items()))
            parts.append("Workouts: %d (%s)" % (len(wk_workouts), bd))
    else:
        parts.append("\u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd: 0 \u05d4\u05e9\u05d1\u05d5\u05e2" if lang == "he"
                     else "Workouts: 0 this week")

    # --- weight vs red-line ---
    w_kg = data.get("last_weight_kg")
    if w_kg is not None:
        try:
            w_min = float(data.get("weight_target_min_kg", 68))
        except Exception:
            w_min = 68.0
        try:
            w_val = float(w_kg)
            wdate = data.get("last_weight_date", "")
            if w_val < w_min:
                tag = ("\u05de\u05ea\u05d7\u05ea \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd!" if lang == "he" else "BELOW red-line!")
            elif w_val <= w_min + 1:
                tag = ("\u05e7\u05e8\u05d5\u05d1 \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd" if lang == "he" else "near red-line")
            else:
                tag = ("\u05d8\u05d5\u05d1" if lang == "he" else "ok")
            if lang == "he":
                parts.append("\u05de\u05e9\u05e7\u05dc: %.1f \u05e7\"\u05d2 (\u05e7\u05d5 \u05d0\u05d3\u05d5\u05dd %.0f - %s)" % (w_val, w_min, tag))
            else:
                parts.append("Weight: %.1f kg (red-line %.0f - %s)" % (w_val, w_min, tag))
        except Exception:
            pass

    # --- nutrition (daily) ---
    if data.get("nutrition_date") == today.isoformat():
        cal = data.get("calories_today", 0)
        prot = data.get("protein_today", 0)
        tcal = data.get("target_calories", 3000)
        tprot = data.get("target_protein_g", 130)
        if lang == "he":
            parts.append("\u05ea\u05d6\u05d5\u05e0\u05d4 \u05d4\u05d9\u05d5\u05dd: %s/%s \u05e7\u05dc\u05d5\u05e8\u05d9\u05d5\u05ea, %s/%s\u05d2 \u05d7\u05dc\u05d1\u05d5\u05df" % (cal, tcal, prot, tprot))
        else:
            parts.append("Nutrition today: %s/%s kcal, %s/%s g protein" % (cal, tcal, prot, tprot))

    # --- injuries ---
    injuries = data.get("injuries", [])
    active = [i for i in injuries if i.get("status") == "active"]
    if active:
        names = "; ".join(i.get("desc", "?") for i in active)
        if lang == "he":
            parts.append("\u05e4\u05e6\u05d9\u05e2\u05d5\u05ea \u05e4\u05e2\u05d9\u05dc\u05d5\u05ea: %d (%s)" % (len(active), names))
        else:
            parts.append("Active injuries: %d (%s)" % (len(active), names))
    else:
        parts.append("\u05e4\u05e6\u05d9\u05e2\u05d5\u05ea: \u05d0\u05d9\u05df" if lang == "he" else "Injuries: none")

    # --- fitness pointer ---
    if data.get("fitness_tests"):
        parts.append("\u05d0\u05de\u05d5\u05e8 '\u05de\u05e6\u05d1 \u05db\u05d5\u05e9\u05e8' \u05dc\u05de\u05d3\u05d3\u05d9\u05dd" if lang == "he"
                     else "Say 'progress' for benchmark detail")

    header = "\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9, \u05d0\u05d3\u05d5\u05e0\u05d9:" if lang == "he" else "Weekly summary, sir:"
    return header + "\n" + "\n".join("- " + p for p in parts)


def _weekly_summary_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"weekly summary", "week summary", "my week", "week recap",
          "weekly recap", "summary of my week", "this week summary"}
    if low in en:
        return True
    he = {"\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2\u05d9", "\u05e1\u05d9\u05db\u05d5\u05dd \u05d4\u05e9\u05d1\u05d5\u05e2",
          "\u05de\u05d4 \u05e2\u05e9\u05d9\u05ea\u05d9 \u05d4\u05e9\u05d1\u05d5\u05e2", "\u05e1\u05d9\u05db\u05d5\u05dd \u05e9\u05d1\u05d5\u05e2"}
    if text in he:
        return True
    return False


# =====================================================================
# Weight logging + 68kg red-line (v4.39) - combat coach brick 4
# sets last_weight_kg (which v4.28 briefing already warns on) + history.
# Reuses v4.33 _load/_save_training_log.
# =====================================================================
def _weight_log_parse(msg):
    """Parse a weight-log command -> float kg, else None.
    Requires a weight keyword plus a number; sane range 30-200 kg."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip()
    num = r"(\d{2,3}(?:\.\d{1,2})?)"
    pats = [
        r"(?:log|record|add)\s+(?:my\s+)?weight[:\-\s]+" + num,
        r"i\s+weigh(?:ed)?\s+" + num,
        r"(?:my\s+)?weight\s+(?:is\s+)?" + num + r"\s*(?:kg|kilo|kilos|kgs)?\b",
        r"(?:\u05ea\u05e8\u05e9\u05d5\u05dd|\u05e8\u05e9\u05d5\u05dd|\u05ea\u05e2\u05d3)\s+(?:\u05dc\u05d9\s+)?(?:\u05d0\u05ea\s+)?\u05de\u05e9\u05e7\u05dc[:\-\s]+" + num,
        r"\u05e9\u05e7\u05dc\u05ea\u05d9\s+" + num,
        r"(?:\u05d4?\u05de\u05e9\u05e7\u05dc\s+\u05e9\u05dc\u05d9|\u05d4\u05de\u05e9\u05e7\u05dc)\s+" + num,
    ]
    for p in pats:
        m = re.search(p, text, re.I)
        if m:
            try:
                v = float(m.group(1))
            except Exception:
                continue
            if 30.0 <= v <= 200.0:
                return v
    return None


def log_weight(val, lang="en"):
    data = _load_training_log()
    today = datetime.date.today().isoformat()
    weights = data.setdefault("weights", [])
    weights.append({"kg": val, "date": today})
    data["last_weight_kg"] = val
    data["last_weight_date"] = today
    _save_training_log(data)
    try:
        wmin = float(data.get("weight_target_min_kg", 68))
    except Exception:
        wmin = 68.0
    if val < wmin:
        tag = ("\u05de\u05ea\u05d7\u05ea \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd \u05e9\u05dc %g \u05e7\"\u05d2 - \u05ea\u05d0\u05db\u05dc, \u05d0\u05d3\u05d5\u05e0\u05d9." % wmin if lang == "he"
               else "below the %g kg red line - eat up, sir." % wmin)
    elif val <= wmin + 1:
        tag = ("\u05e7\u05e8\u05d5\u05d1 \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd \u05e9\u05dc %g \u05e7\"\u05d2." % wmin if lang == "he"
               else "close to the %g kg red line." % wmin)
    else:
        tag = ("\u05de\u05e2\u05dc \u05d4\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd. \u05d8\u05d5\u05d1." if lang == "he"
               else "above the red line. Good.")
    if lang == "he":
        return "\u05e0\u05e8\u05e9\u05dd, \u05d0\u05d3\u05d5\u05e0\u05d9: %g \u05e7\"\u05d2 - %s" % (val, tag)
    return "Logged, sir: %g kg - %s" % (val, tag)


def weight_check(lang="en"):
    data = _load_training_log()
    w = data.get("last_weight_kg")
    if w is None:
        return ("\u05e2\u05d3\u05d9\u05d9\u05df \u05dc\u05d0 \u05ea\u05d9\u05e2\u05d3\u05ea \u05de\u05e9\u05e7\u05dc, \u05d0\u05d3\u05d5\u05e0\u05d9. \u05d0\u05de\u05d5\u05e8 '\u05ea\u05e8\u05e9\u05d5\u05dd \u05de\u05e9\u05e7\u05dc 70'." if lang == "he"
                else "No weight logged yet, sir. Say 'log weight 70'.")
    try:
        w = float(w)
        wmin = float(data.get("weight_target_min_kg", 68))
    except Exception:
        return ("\u05dc\u05d0 \u05d4\u05e6\u05dc\u05d7\u05ea\u05d9 \u05dc\u05e7\u05e8\u05d5\u05d0 \u05d0\u05ea \u05d4\u05de\u05e9\u05e7\u05dc, \u05d0\u05d3\u05d5\u05e0\u05d9." if lang == "he"
                else "Couldn't read the weight, sir.")
    # days since
    rel = ""
    wd = data.get("last_weight_date", "")
    try:
        d0 = datetime.date.fromisoformat(wd)
        days = (datetime.date.today() - d0).days
        if lang == "he":
            rel = ("\u05d4\u05d9\u05d5\u05dd" if days == 0 else "\u05d0\u05ea\u05de\u05d5\u05dc" if days == 1 else "\u05dc\u05e4\u05e0\u05d9 %d \u05d9\u05de\u05d9\u05dd" % days)
        else:
            rel = ("today" if days == 0 else "yesterday" if days == 1 else "%d days ago" % days)
    except Exception:
        rel = ""
    # trend vs previous weigh-in
    trend = ""
    weights = data.get("weights", [])
    if len(weights) > 1:
        try:
            prev = float(weights[-2].get("kg"))
            diff = w - prev
            if abs(diff) >= 0.05:
                if lang == "he":
                    verb = "\u05e2\u05dc\u05d9\u05ea" if diff > 0 else "\u05d9\u05e8\u05d3\u05ea"
                    trend = " %s %+.1f \u05e7\"\u05d2 \u05de\u05d4\u05e4\u05e2\u05dd \u05d4\u05e7\u05d5\u05d3\u05de\u05ea" % (verb, diff)
                else:
                    verb = "up" if diff > 0 else "down"
                    trend = " %s %+.1f kg vs last weigh-in" % (verb, diff)
        except Exception:
            pass
    if w < wmin:
        verdict = ("\u05de\u05ea\u05d7\u05ea \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd!" if lang == "he" else "BELOW the red line!")
    elif w <= wmin + 1:
        verdict = ("\u05e7\u05e8\u05d5\u05d1 \u05dc\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd." if lang == "he" else "near the red line.")
    else:
        verdict = ("\u05de\u05e2\u05dc \u05d4\u05e7\u05d5 \u05d4\u05d0\u05d3\u05d5\u05dd. \u05d8\u05d5\u05d1." if lang == "he" else "above the red line. Good.")
    relpart = (" (%s)" % rel) if rel else ""
    if lang == "he":
        return "\u05de\u05e9\u05e7\u05dc \u05d0\u05d7\u05e8\u05d5\u05df: %g \u05e7\"\u05d2%s. \u05e7\u05d5 \u05d0\u05d3\u05d5\u05dd %g - %s%s" % (w, relpart, wmin, verdict, trend)
    return "Latest weight: %g kg%s. Red line %g - %s%s" % (w, relpart, wmin, verdict, trend)


def _weight_target_set_parse(msg):
    """Parse an explicit CHANGE-the-weight-target command -> float kg,
    else None. v5.16s: deterministic bypass of the model for this
    action - past chat logs (injected as long-term memory) contain
    the model's own earlier false "already updated to 72" replies,
    which made it answer from memory instead of calling the tool.
    Requires a change-verb so plain weight LOGGING ("\u05e9\u05e7\u05dc\u05ea\u05d9 71",
    "log weight 70.5") never lands here."""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    num = r"(\d{2,3}(?:\.\d{1,2})?)"
    en = (r"(?:change|set|update|make)\b[^.!?]{0,40}?"
          r"(?:weight\s*target|target\s*weight|weight\s*goal|"
          r"red\s*line|weight)\b[^0-9]{0,12}" + num)
    he = (r"(?:\u05e9\u05e0\u05d4|\u05ea\u05e9\u05e0\u05d4|\u05e2\u05d3\u05db\u05df|\u05ea\u05e2\u05d3\u05db\u05df|"
          r"\u05d4\u05d2\u05d3\u05e8|\u05ea\u05d2\u05d3\u05d9\u05e8|\u05e9\u05d9\u05dd|\u05ea\u05e9\u05d9\u05dd)"
          r"[^.!?]{0,40}?"
          r"(?:\u05d9\u05e2\u05d3\s*\u05d4?\u05de\u05e9\u05e7\u05dc|"
          r"\u05de\u05d8\u05e8\u05ea\s*\u05d4?\u05de\u05e9\u05e7\u05dc|"
          r"\u05de\u05e9\u05e7\u05dc\s*\u05d4?\u05d9\u05e2\u05d3|"
          r"\u05d4?\u05e7\u05d5\s*\u05d4?\u05d0\u05d3\u05d5\u05dd|"
          r"\u05d4?\u05de\u05e9\u05e7\u05dc)"
          r"[^0-9]{0,12}" + num)
    for pat in (en, he):
        m = re.search(pat, text, re.I)
        if m:
            try:
                v = float(m.group(1))
            except Exception:
                continue
            if 30.0 <= v <= 200.0:
                return v
    return None


def _weight_target_set_reply(kg, lang="en"):
    """Run the real tool handler and word the confirmation in the
    user's language. The tool writes the file and records the undo
    action; we only translate its success message."""
    out = set_weight_target(kg)
    if lang == "he" and out.startswith("Weight target updated"):
        return ("\u05d9\u05e2\u05d3 \u05d4\u05de\u05e9\u05e7\u05dc \u05e2\u05d5\u05d3\u05db\u05df "
                "\u05dc-%g \u05e7\"\u05d2, \u05d0\u05d3\u05d5\u05e0\u05d9." % float(kg))
    return out


def _weight_check_intercept(msg):
    if not msg or not isinstance(msg, str):
        return False
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:]*",
                  "", text, flags=re.I)
    text = re.sub(r"^\s*(\u05d4\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\u05d9\s+|\u05d0\u05d5\u05e7\u05d9\s+)?(\u05d2'?\u05d0?\u05e8?\u05d5?\u05d5?\u05d9\u05e1|g\u05d0\u05e8\u05d5\u05d5\u05d9\u05e1)[\s,:]*",
                  "", text)
    text = text.strip().rstrip(".!?,")
    low = text.lower()
    en = {"weight check", "my weight", "what is my weight",
          "what's my weight", "weight status", "am i above 68",
          "am i above the red line", "how much do i weigh",
          "current weight"}
    if low in en:
        return True
    he = {"\u05d1\u05d3\u05d9\u05e7\u05ea \u05de\u05e9\u05e7\u05dc", "\u05de\u05d4 \u05d4\u05de\u05e9\u05e7\u05dc", "\u05d4\u05de\u05e9\u05e7\u05dc \u05e9\u05dc\u05d9",
          "\u05db\u05de\u05d4 \u05d0\u05e0\u05d9 \u05e9\u05d5\u05e7\u05dc", "\u05de\u05d4 \u05d4\u05de\u05e9\u05e7\u05dc \u05e9\u05dc\u05d9", "\u05de\u05e9\u05e7\u05dc",
          "\u05db\u05de\u05d4 \u05d0\u05e0\u05d9 \u05e9\u05d5\u05e7\u05dc \u05e2\u05db\u05e9\u05d9\u05d5"}
    if text in he:
        return True
    return False


# =====================================================================
# IPv4-only outbound (v4.40) - fix httplib2 hang on broken-IPv6 paths
# =====================================================================
# httplib2 (used by googleapiclient for Calendar / Gmail) does not do
# Happy Eyeballs and hangs at TCP connect when www.googleapis.com
# resolves to an AAAA record but local IPv6 routing is broken. We
# filter AAAA results out of socket.getaddrinfo so every outbound
# TCP connection from this process uses IPv4. v4 already works for
# every API JARVIS uses (Anthropic, ElevenLabs, Maps, OpenWeather).
import socket as _v440_socket
if not getattr(_v440_socket, "_v440_ipv4_patched", False):
    _v440_orig_getaddrinfo = _v440_socket.getaddrinfo

    def _v440_ipv4_only_getaddrinfo(host, port, family=0, type=0,
                                    proto=0, flags=0):
        # v4.67: prefer IPv4 (local IPv6 to Google is broken here), but only
        # coerce AF_UNSPEC, honour an explicit family, and ALWAYS fall back to a
        # normal resolve if the IPv4-only lookup fails - so genuinely IPv6-only
        # hosts / explicit AF_INET6 callers still resolve instead of raising.
        fam = _v440_socket.AF_INET if family == 0 else family
        try:
            return _v440_orig_getaddrinfo(host, port, fam, type, proto, flags)
        except _v440_socket.gaierror:
            return _v440_orig_getaddrinfo(host, port, family, type, proto, flags)

    _v440_socket.getaddrinfo = _v440_ipv4_only_getaddrinfo
    _v440_socket._v440_ipv4_patched = True


# ---------------------------------------------------------------------------
# v4.43: Obsidian note search  ("JARVIS, what did I note about X")
# ---------------------------------------------------------------------------
def _obsidian_search_parse(msg):
    """v4.44: detect Obsidian search intent. Returns:
        None  -> no intent
        ""    -> list all notes (no topic given)
        str   -> search for that topic"""
    if not msg or not isinstance(msg, str):
        return None
    text = msg.strip()
    text = re.sub(r"^\s*(hey\s+|hi\s+|ok\s+|okay\s+)?jarvis[\s,:\-]*", "", text, flags=re.I)
    text = re.sub(r"^\s*(היי\s+|אוקיי\s+|אוקי\s+)?(ג[׳'`]?א?ר?ו+יס)[\s,:\-]*", "", text)
    text = text.strip().rstrip("?!.").strip()
    low = text.lower()

    # --- topicless intents (list all notes) ---
    listall_en = [
        r"^do i have (?:any )?notes$",
        r"^show (?:me )?(?:my )?notes$",
        r"^list (?:my )?notes$",
        r"^what notes do i have$",
        r"^what are my notes$",
        r"^my notes$",
        r"^all (?:my )?notes$",
    ]
    for p in listall_en:
        if re.search(p, low):
            return ""
    listall_he = [
        r"^מה הפתקים שלי$",
        r"^אילו פתקים יש לי$",
        r"^יש לי פתקים$",
        r"^הצג (?:לי )?(?:את )?הפתקים(?: שלי)?$",
        r"^הראה (?:לי )?(?:את )?הפתקים(?: שלי)?$",
        r"^רשימת פתקים$",
        r"^כל הפתקים(?: שלי)?$",
        r"^איזה פתקים יש לי$",
    ]
    for p in listall_he:
        if re.search(p, text):
            return ""

    # --- topic-search intents ---
    en_pats = [
        r"what did i (?:note|write|jot|record) (?:down )?about (.+)$",
        r"what do(?:es)? my notes? say about (.+)$",
        r"search (?:my )?(?:notes?|vault|memory) (?:for |about )?(.+)$",
        r"find (?:in )?(?:my )?notes? (?:about |for )?(.+)$",
        r"do i have (?:any )?notes? (?:on|about|regarding) (.+)$",
        r"any notes (?:on|about|regarding) (.+)$",
        r"show (?:me )?(?:my )?notes (?:on|about|regarding) (.+)$",
        r"list (?:my )?notes (?:on|about|regarding) (.+)$",
        r"look up (.+?) in my (?:notes?|vault)$",
    ]
    for p in en_pats:
        m = re.search(p, low)
        if m:
            return m.group(1).strip(" .?!,'\"")
    he_pats = [
        r"מה רשמתי (?:לעצמי )?על (.+)$",
        r"מה כתבתי (?:לעצמי )?על (.+)$",
        r"מה רשמתי בנושא (.+)$",
        r"מה כתבתי בנושא (.+)$",
        r"חפש (?:לי )?(?:בפתקים|בכספת|בזיכרון) (?:על |בנושא )?(.+)$",
        r"תחפש (?:לי )?(?:בפתקים|בכספת|בזיכרון) (?:על |בנושא )?(.+)$",
        r"מה יש לי (?:רשום )?(?:על |בנושא )(.+)$",
        r"מה הפתקים (?:שלי )?אומרים על (.+)$",
        r"יש לי פתקים (?:על |בנושא |לגבי )(.+)$",
        r"יש לי משהו (?:רשום )?(?:על |בנושא |לגבי )(.+)$",
        r"הראה (?:לי )?(?:את )?הפתקים (?:שלי )?(?:על |בנושא |לגבי )(.+)$",
        r"הצג (?:לי )?(?:את )?הפתקים (?:שלי )?(?:על |בנושא |לגבי )(.+)$",
    ]
    for p in he_pats:
        m = re.search(p, text)
        if m:
            return m.group(1).strip(" .?!,'\"")
    return None


def search_obsidian(query, lang="en"):
    """Search every .md file under the Obsidian vault for `query` and return a
    short answer synthesised from what was found. Degrades gracefully."""
    if not query or not query.strip():
        return list_all_notes(lang)
    q = query.strip().lower()
    terms = _obsidian_or_split(q)
    vault = VAULT_DIR
    try:
        if not vault.exists():
            return ("אין עדיין כספת אובסידיאן, אדוני." if lang == "he"
                    else "There's no Obsidian vault yet, sir.")
    except Exception:
        return ("לא הצלחתי לגשת לכספת, אדוני." if lang == "he"
                else "I couldn't reach the vault, sir.")
    matches = []
    total = 0
    CAP = 4000
    try:
        for f in sorted(vault.rglob("*.md")):
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
            except Exception:
                continue
            hits = [i for i, ln in enumerate(lines) if any(tt in ln.lower() for tt in terms)]
            if not hits:
                continue
            keep = set()
            for i in hits:
                for j in range(max(0, i - 2), min(len(lines), i + 3)):
                    keep.add(j)
            ctx = "\n".join(lines[j] for j in sorted(keep) if lines[j].strip())
            try:
                label = f.relative_to(vault)
            except Exception:
                label = f.name
            snippet = "[%s]\n%s" % (label, ctx)
            matches.append(snippet)
            total += len(snippet)
            if total >= CAP:
                break
    except Exception:
        return ("שגיאה בחיפוש בפתקים, אדוני." if lang == "he"
                else "Error searching your notes, sir.")
    if not matches:
        return (("לא מצאתי כלום על '%s' בפתקים שלך, אדוני." % query) if lang == "he"
                else ("I couldn't find anything about '%s' in your notes, sir." % query))
    facts = ("\n\n".join(matches))[:CAP]
    if not ANTHROPIC_API_KEY:
        head = ("מצאתי את זה בפתקים, אדוני:\n" if lang == "he"
                else "Found this in your notes, sir:\n")
        return clean_text(head + facts)
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You are Achilles, a calm British-butler AI. The user searched their "
            "personal Obsidian notes. Below are the matching excerpts (each "
            "tagged with its [filename]). Answer what THEIR NOTES say about '"
            + query + "' in 2 to 4 short sentences, in "
            + ("Hebrew" if lang == "he" else "English")
            + ". Address them as " + ("אדוני" if lang == "he" else "sir")
            + ". Base the answer ONLY on the excerpts; if they are thin, say "
            "what little was found. Plain text, no markdown, no URLs.")
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=400,
            system=sys_p,
            messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or clean_text(facts)
    except Exception:
        return clean_text(facts)


# ---------------------------------------------------------------------------
# v4.43: personalised news section for the daily briefing (fully optional)
# ---------------------------------------------------------------------------
def _obsidian_or_split(q):
    """v4.44: split a query on ' or ' / ' או ' so multi-term searches like
    'sport or fitness' check each term independently."""
    parts = re.split(r"\s+(?:or|או)\s+", q)
    parts = [p.strip() for p in parts if p.strip()]
    return parts or [q]


def list_all_notes(lang="en"):
    """v4.44: short, fast list of every .md note in the Obsidian vault, sorted
    by most-recently-modified. No model call."""
    vault = VAULT_DIR
    try:
        if not vault.exists():
            return ("אין עדיין כספת אובסידיאן, אדוני." if lang == "he"
                    else "There's no Obsidian vault yet, sir.")
    except Exception:
        return ("לא הצלחתי לגשת לכספת, אדוני." if lang == "he"
                else "I couldn't reach the vault, sir.")
    try:
        files = sorted(vault.rglob("*.md"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
    except Exception:
        files = []
    if not files:
        return ("אין לך פתקים שמורים, אדוני." if lang == "he"
                else "You have no saved notes, sir.")
    LIMIT = 15
    shown = files[:LIMIT]
    lines = []
    for f in shown:
        try:
            label = f.relative_to(vault).as_posix()
        except Exception:
            label = f.name
        hint = ""
        try:
            for ln in f.read_text(encoding="utf-8", errors="ignore").splitlines():
                s = ln.strip().lstrip("#").strip()
                if s:
                    hint = s[:60]
                    break
        except Exception:
            pass
        if hint:
            lines.append("%s — %s" % (label, hint))
        else:
            lines.append(str(label))
    extra = len(files) - len(shown)
    if lang == "he":
        head = "יש לך %d פתקים, אדוני. הנה האחרונים:\n" % len(files)
        tail = ("\nועוד %d." % extra) if extra > 0 else ""
    else:
        head = "You have %d notes, sir. The most recent:\n" % len(files)
        tail = ("\nAnd %d more." % extra) if extra > 0 else ""
    return clean_text(head + "\n".join(lines) + tail)


NEWS_INTERESTS = "artificial intelligence and technology, Israel, and major world news"

def _news_briefing_section(lang="en"):
    """Fetch 2-3 recent headlines relevant to NEWS_INTERESTS via Claude +
    web_search, for the daily briefing. Returns '' on ANY failure so the
    briefing never breaks because of the news."""
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        interests = globals().get("NEWS_INTERESTS", "technology, Israel, world news")
        sys_p = (
            "You are a news desk. Use web_search to find 2 or 3 of the most "
            "important and RECENT headlines (prefer the last day or two) "
            "relevant to these interests: " + interests + ". Then output ONLY "
            "a compact plain-text list of those 2-3 headlines, one per line, "
            "each a short factual phrase. No URLs, no numbering, no commentary, "
            "no markdown. Write the headlines in "
            + ("Hebrew" if lang == "he" else "English") + ".")
        tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 2}]
        msgs = [{"role": "user", "content": "Today's headlines for my briefing, please."}]
        r = None
        for _ in range(4):
            r = client.messages.create(
                model="claude-sonnet-5", max_tokens=500,
                system=sys_p, messages=msgs, tools=tools)
            msgs.append({"role": "assistant", "content": r.content})
            if getattr(r, "stop_reason", None) == "tool_use":
                continue
            break
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        news = "\n".join(p.strip() for p in parts if p.strip()).strip()
        news = re.sub(r"https?://\S+", "", news)
        return clean_text(news).strip()
    except Exception as e:
        try:
            print("[diag] news section skipped:", repr(e))
        except Exception:
            pass
        return ""


# --- v5.16w: two-tier brain routing ------------------------------
# Simple turns run on Sonnet 5 (fast, cheap). Turns that look like
# real reasoning work - analysis, planning, code, comparisons, long
# or multi-part questions - escalate to Fable 5. The decision is
# deterministic keyword/shape matching, never an extra API call, so
# routing costs nothing and always behaves the same way.
BRAIN_LIGHT = "claude-sonnet-5"
# v5.18: the research brain is Opus 5, not Fable 5. Opus 5 is the newer
# model - its knowledge runs to May 2026 against Fable's January - it is
# rated "moderate" latency where Fable is "slower", and it costs half as
# much per token. Fable stays the stronger model overall, but for a VOICE
# assistant the latency column decides it: every extra second here is
# silence the user sits through before hearing anything.
BRAIN_HEAVY = "claude-opus-5"
# Max is deliberate: this path only fires when a real research question
# was asked, so the depth is the whole point of escalating. Anthropic do
# warn that max buys small gains for significant cost on ordinary work -
# which is exactly why it is gated behind _pick_brain_model and never
# touches everyday turns. Drop to "xhigh" here if it feels slow.
BRAIN_HEAVY_EFFORT = "max"
# Adaptive thinking spends the SAME budget as the answer. At the old 1024
# ceiling a max-effort turn could burn the whole allowance thinking and
# return a truncated answer or nothing at all. max_tokens is only a CAP -
# unused headroom is never billed - so this is free insurance. Thinking
# blocks are dropped before speaking, so it cannot lengthen the speech.
BRAIN_HEAVY_MAX_TOKENS = 16000

_BRAIN_HEAVY_HE = (
    "\u05ea\u05d7\u05e9\u05d5\u05d1",
    "\u05dc\u05e2\u05d5\u05de\u05e7",
    "\u05ea\u05e0\u05ea\u05d7",
    "\u05ea\u05db\u05e0\u05df",
    "\u05ea\u05db\u05e0\u05d5\u05df",
    "\u05d4\u05e9\u05d5\u05d5\u05d4",
    "\u05d4\u05e9\u05d5\u05d5\u05d0\u05d4",
    "\u05ea\u05e1\u05d1\u05d9\u05e8",
    "\u05d4\u05e1\u05d1\u05e8",
    "\u05de\u05d3\u05d5\u05e2",
    "\u05e7\u05d5\u05d3",
    "\u05d1\u05d0\u05d2",
    "\u05e9\u05d2\u05d9\u05d0\u05d4",
    "\u05e4\u05d5\u05e0\u05e7\u05e6\u05d9\u05d4",
    "\u05d0\u05e1\u05d8\u05e8\u05d8\u05d2\u05d9\u05d4",
    "\u05ea\u05d5\u05db\u05e0\u05d9\u05ea",
    "\u05de\u05d7\u05e7\u05e8",
    "\u05e0\u05de\u05e7",
    "\u05d9\u05ea\u05e8\u05d5\u05e0\u05d5\u05ea",
    "\u05d7\u05e1\u05e8\u05d5\u05e0\u05d5\u05ea",
    "\u05dc\u05e0\u05ea\u05d7",
    "\u05ea\u05db\u05ea\u05d5\u05d1",
    "\u05e1\u05e7\u05e8\u05d9\u05e4\u05d8",
    "\u05d0\u05dc\u05d2\u05d5\u05e8\u05d9\u05ea\u05dd",
    "\u05ea\u05de\u05dc\u05d9\u05e5",
    "\u05d4\u05de\u05dc\u05e6\u05d4",
    "\u05ea\u05e9\u05d5\u05d5\u05d4",
    "\u05dc\u05ea\u05db\u05e0\u05df",
)
_BRAIN_LIGHT_HE = (
    "\u05de\u05d4 \u05d4\u05e9\u05e2\u05d4",
    "\u05de\u05d6\u05d2 \u05d0\u05d5\u05d5\u05d9\u05e8",
    "\u05de\u05d4 \u05e0\u05e9\u05de\u05e2",
    "\u05ea\u05e0\u05d2\u05df",
    "\u05ea\u05d3\u05dc\u05d9\u05e7",
    "\u05ea\u05db\u05d1\u05d4",
    "\u05ea\u05e2\u05e6\u05d5\u05e8",
    "\u05d0\u05d9\u05d6\u05d4 \u05d9\u05d5\u05dd",
    "\u05ea\u05d5\u05d3\u05d4",
    "\u05d1\u05d5\u05e7\u05e8 \u05d8\u05d5\u05d1",
    "\u05dc\u05d9\u05dc\u05d4 \u05d8\u05d5\u05d1",
    "\u05de\u05d4 \u05e7\u05d5\u05e8\u05d4",
)
_BRAIN_HEAVY_EN = (
    "analyz",
    "explain why",
    "think through",
    "think hard",
    "deep dive",
    "in depth",
    "step by step",
    "compare",
    "trade-off",
    "tradeoff",
    "code",
    "debug",
    "function",
    "script",
    "algorithm",
    "strategy",
    "plan ",
    "roadmap",
    "research",
    "pros and cons",
    "recommend",
    "design a",
    "architect",
    "refactor",
    "optimi",
    "why does",
    "how does",
)
_BRAIN_LIGHT_EN = (
    "what time",
    "weather",
    "thanks",
    "thank you",
    "good morning",
    "good night",
    "play ",
    "turn on",
    "turn off",
    "stop ",
    "pause",
)


def _brain_call(client, model, sys_prompt, messages, tools):
    """v5.18: single place that knows how to invoke the brain.

    Effort travels as output_config={"effort": ...}. An older anthropic
    SDK on this machine would reject that keyword outright, and a hard
    failure here would leave ACHILLES mute - so an unsupported keyword
    degrades to a plain call rather than taking the assistant down. The
    same applies if the API itself rejects the value."""
    kw = {"model": model, "system": sys_prompt, "messages": messages}
    if tools is not None:
        kw["tools"] = tools
    if model != BRAIN_HEAVY:
        kw["max_tokens"] = 1024
        return client.messages.create(**kw)
    kw["max_tokens"] = BRAIN_HEAVY_MAX_TOKENS
    try:
        return client.messages.create(
            output_config={"effort": BRAIN_HEAVY_EFFORT}, **kw)
    except TypeError as e:
        print("[brain] SDK does not accept output_config, "
              "running without effort:", e, flush=True)
    except Exception as e:
        low = str(e).lower()
        if "output_config" not in low and "effort" not in low:
            raise
        print("[brain] API rejected effort, running without it:", e, flush=True)
    return client.messages.create(**kw)


def _pick_brain_model(user_message):
    """Choose which model answers this turn. Conservative by design:
    defaults to the cheap model and only escalates on a clear signal,
    so a normal chat never quietly costs heavy-model money."""
    try:
        text = (user_message or "").strip()
        low = text.lower()
        words = len(text.split())
        # Long turns are reasoning work no matter what words they
        # happen to contain, so length is checked FIRST - otherwise a
        # long question containing a casual phrase would be routed
        # cheap purely by accident.
        if words >= 25:
            return BRAIN_HEAVY
        # Short explicit light intents - commands, greetings, status.
        if words <= 12:
            for k in _BRAIN_LIGHT_HE + _BRAIN_LIGHT_EN:
                if k in low:
                    return BRAIN_LIGHT
        # Explicit heavy intents.
        for k in _BRAIN_HEAVY_HE + _BRAIN_HEAVY_EN:
            if k in low:
                return BRAIN_HEAVY
        # Several real questions in one turn is multi-part reasoning -
        # but only when there are actual words, not bare punctuation.
        if low.count("?") >= 2 and words >= 6:
            return BRAIN_HEAVY
        return BRAIN_LIGHT
    except Exception:
        return BRAIN_LIGHT

def think(user_message, memory, lang=""):
    if not ANTHROPIC_API_KEY:
        return "[Error: Missing API Key in .env]"
    # v4.34: if a quiz is pending, this message is the user's answer.
    with _quiz_lock:
        _quiz_active = _quiz_state["active"]
    if _quiz_active:
        _fb = evaluate_quiz_answer(
            user_message,
            lang="he" if lang == "he" or is_hebrew(user_message) else "en")
        if _fb is not None:
            return _fb
    # Deterministic intercept: never let the model refuse a learning command.
    parsed = _learning_intercept(user_message)
    if parsed is not None:
        topic, depth = parsed
        if topic == "__STATUS__":
            return learning_status()
        if topic.startswith("__RESUME__:"):
            return resume_learning(topic[len("__RESUME__:"):])
        if depth == "deep":
            return deep_learn_domain(topic)
        else:
            return learn_topic(topic, "")
    if _whats_new_intercept(user_message):
        return whats_new("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _system_health_intercept(user_message):
        return system_health("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _learned_this_week_intercept(user_message):
        return learned_this_week("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _undo_intercept(user_message):
        return undo_last()
    if _budget_intercept(user_message):
        return budget_status("he" if lang == "he" or is_hebrew(user_message) else "en")
    if _backup_intercept(user_message):
        return backup_vault()
    _dec = _decision_log_parse(user_message)
    if _dec is not None:
        return log_decision(_dec)
    if _decision_review_intercept(user_message):
        return recent_decisions(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _nut = _nutrition_log_parse(user_message)
    if _nut is not None:
        return log_calories(_nut[1]) if _nut[0] == "calories" else log_protein(_nut[1])
    if _nutrition_status_intercept(user_message):
        return nutrition_status(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _quiz_topic = _quiz_start_parse(user_message)
    if _quiz_topic is not None:
        return start_quiz(_quiz_topic, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _inj = _injury_log_parse(user_message)
    if _inj is not None:
        return log_injury(_inj, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _rec = _injury_recovered_parse(user_message)
    if _rec is not None:
        return mark_recovered(_rec, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _injury_status_intercept(user_message):
        return injury_status(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _wo = _workout_log_parse(user_message)
    if _wo is not None:
        return log_workout(_wo, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _workout_status_intercept(user_message):
        return recent_workouts(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _ft = _fitness_test_parse(user_message)
    if _ft is not None:
        return log_fitness_test(_ft, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _tg = _set_target_parse(user_message)
    if _tg is not None:
        return set_fitness_target(_tg, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _fitness_progress_intercept(user_message):
        return fitness_progress(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _weekly_summary_intercept(user_message):
        return weekly_summary(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _wts = _weight_target_set_parse(user_message)
    if _wts is not None:
        # v5.16s: deterministic - the model (and its poisoned long-term
        # memory) never sees an explicit target-change command.
        return _weight_target_set_reply(_wts, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _wt = _weight_log_parse(user_message)
    if _wt is not None:
        return log_weight(_wt, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    if _weight_check_intercept(user_message):
        return weight_check(lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    _obs_q = _obsidian_search_parse(user_message)
    if _obs_q is not None:
        return search_obsidian(_obs_q, lang="he" if lang == "he" or is_hebrew(user_message) else "en")
    # v4.52: deterministic Achilles-screen intercepts. An open/show verb is
    # required so knowledge questions ("what IS a black hole") still go to
    # the model instead of popping a window.
    _low = user_message.lower()
    if re.search(r"(פתח|תפתח|open|show|launch|bring up|תעלה|תציג)[^.!?]{0,24}(black\s?hole|חור שחור|achilles|אכילס)", _low) \
       or re.search(r"(black\s?hole|חור שחור)[^.!?]{0,12}(screen|window|מסך|חלון)", _low):
        return open_achilles("core")
    if re.search(r"(פתח|תפתח|open|show|launch|תראה|תציג|תעלה)[^.!?]{0,24}(solar\s?system|מערכת השמש|הכוכבים|the planets)", _low):
        return open_achilles("solar")
    # v5.19: HERMES / WorldView / Mission Control used to reach their tool
    # only by asking the model to call it - an API round trip, a bill, and
    # a second of silence to open a window that needs no thought at all.
    # Worse, the model can decline to call a tool when its context misleads
    # it, which is the failure this codebase already learned the hard way.
    # An open/show verb stays required, so "what IS hermes" still reaches
    # the model rather than popping a window. The tools remain registered:
    # unusual phrasings still work through the model as before.
    _he = (lang == "he") or is_hebrew(user_message)
    _open_verb = r"(\u05e4\u05ea\u05d7|\u05ea\u05e4\u05ea\u05d7|\u05ea\u05e2\u05dc\u05d4|\u05ea\u05e6\u05d9\u05d2|\u05ea\u05e8\u05d0\u05d4|open|show|launch|bring up|pull up)"
    if re.search(_open_verb + r"[^.!?]{0,24}(hermes|\u05d4\u05e8\u05de\u05e1|\u05d0\u05e8\u05de\u05e1|\u05d4\u05e8\u05de\u05e6|\u05d8\u05e8\u05de\u05d9\u05e0\u05dc)", _low):
        return _open_screen_reply(open_hermes(), _he)
    if re.search(_open_verb + r"[^.!?]{0,24}(world\s?view|\u05d5\u05d5\u05e8\u05dc\u05d3\s?\u05d5\u05d5\u05d9\u05d5|\u05d5\u05e8\u05dc\u05d3\s?\u05d5\u05d5\u05d9\u05d5|\u05d4\u05d2\u05dc\u05d5\u05d1\u05d5\u05e1|globe)", _low):
        return _open_screen_reply(open_worldview(), _he)
    if re.search(_open_verb + r"[^.!?]{0,24}(roadmap|road\s?map|mission\s?control|\u05de\u05e4\u05ea \u05d4\u05d3\u05e8\u05db\u05d9\u05dd|\u05e8\u05d5\u05d3\u05de\u05d0\u05e4)", _low):
        return _open_screen_reply(open_roadmap(), _he)
    # v4.53: task list - open the todo scene / add a task by voice
    _t = re.search(r"(?:תוסיף משימה|תוסיף לרשימה|add (?:a )?task)\s+(.+)", user_message, re.IGNORECASE)
    if _t is not None:
        return todo_add_voice(_t.group(1), "he" if lang == "he" or is_hebrew(user_message) else "en")
    if re.search(r"(פתח|תפתח|open|show|תראה|תציג|תעלה)[^.!?]{0,24}(to\s?do|todo|task list|המשימות|רשימת משימות|רשימת המשימות)", _low):
        return open_achilles("todo")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    # JARVIS speaks ONLY Hebrew or English. Whisper can detect many languages,
    # but on short clips it often mis-detects (e.g. tags a phrase as German).
    # So we collapse everything that isn't clearly Hebrew down to English —
    # the two languages Matan actually uses.
    if lang == "he":
        _lang_note = "\nIMPORTANT: The user is speaking HEBREW. Reply ONLY in Hebrew. Never reply in any other language."
    else:
        _lang_note = "\nIMPORTANT: Reply ONLY in English. Never reply in German, French, or any language other than English, even if the user's words look like another language."
    # Give the model the current local time so it can turn "tomorrow at 4" into
    # a correct ISO datetime for calendar events.
    _time_note = "\nCurrent local time (Israel): " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M (%A)")
    # v4.42: prompt caching to cut API cost. The constant
    # JARVIS_SYSTEM_PROMPT (~4k tokens) is marked cache_control so
    # Anthropic caches it (~5 min) and bills cache hits at ~10% of
    # the input rate. The small variable suffix (language note +
    # current time) goes in its own uncached block so the cached
    # prefix stays byte-identical between calls. sys_prompt_plain is
    # the plain-string fallback used by the no-tools retry path.
    sys_prompt = [
        {"type": "text", "text": JARVIS_SYSTEM_PROMPT,
         "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _lang_note + _time_note},
    ]
    sys_prompt_plain = JARVIS_SYSTEM_PROMPT + _lang_note + _time_note
    globals()["_last_timer_lang"] = "he" if lang == "he" else "en"
    # Combined toolset: built-in web search + our local tools.
    tools = [
        {"type": "web_search_20250305", "name": "web_search", "max_uses": 3},
    ] + LOCAL_TOOLS

    # v4.67: hold the lock for the whole turn so concurrent callers (voice /
    # Telegram / the /ask HTTP thread) can never interleave appends into
    # conversation_history, and normalise/bound the history first.
    with _think_lock:
        _normalize_history()
        if not conversation_history:
            msg = f"[Memory from past conversations:]\n{memory}\n\n[Current message:]\n{user_message}"
        else:
            msg = user_message
        conversation_history.append({"role": "user", "content": msg})

        try:
            # Tool-use loop. Claude may ask to run a local tool; we run it, hand
            # the result back, and let it continue — repeating until it gives a
            # final text answer. The cap (5) prevents any accidental infinite loop.
            _brain_model = _pick_brain_model(user_message)
            if _brain_model != BRAIN_LIGHT:
                print("[brain] escalating to %s" % _brain_model)
            for _ in range(5):
                r = _brain_call(client, _brain_model, sys_prompt,
                                conversation_history, tools)
                # Record exactly what Claude returned (text + any tool requests).
                conversation_history.append({"role": "assistant", "content": r.content})

                if r.stop_reason == "tool_use":
                    # Run every LOCAL tool Claude asked for and collect results.
                    # (web_search runs on Anthropic's side, so we don't handle it.)
                    tool_results = []
                    for block in r.content:
                        if getattr(block, "type", None) == "tool_use" and block.name in (
                                "set_weight_target",  # v5.16k fix: was missing from this
                                # allowlist, so the tool never actually ran even though it
                                # was offered to Claude and dispatched by name below.
                                "open_app", "save_note", "calendar_read", "calendar_add",
                                "calendar_delete", "calendar_update",
                                "gmail_read", "gmail_spam_review", "gmail_move_spam",
                                "find_places", "get_directions", "set_timer",
                                "spotify_play", "spotify_pause", "spotify_next",
                                "spotify_previous", "spotify_volume", "spotify_now_playing",
                                "learn_topic", "deep_learn_domain", "resume_learning",
                                "learning_status", "open_search_panel", "open_worldview",
                                "open_hermes",
                                "open_achilles", "open_roadmap", "share_live_location", "request_location"):
                            out = run_local_tool(block.name, block.input or {})
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": out,
                            })
                    if tool_results:
                        conversation_history.append({"role": "user", "content": tool_results})
                        continue  # let Claude turn the tool output into a reply
                    # v4.67: a tool_use we didn't answer (or only web_search) would
                    # poison the next call; drop the orphaned assistant turn.
                    if (conversation_history
                            and conversation_history[-1].get("role") == "assistant"):
                        conversation_history.pop()
                    break

                # Normal finish: gather text from the content blocks.
                parts = [b.text for b in r.content
                         if getattr(b, "type", None) == "text"]
                reply = " ".join(p.strip() for p in parts if p.strip()).strip()
                if not reply:
                    reply = "Done, sir."
                return clean_text(reply)

            return "I got a bit stuck on that, sir. Could you rephrase?"
        except Exception as e:
            # If tools aren't available for some reason, retry once plainly.
            try:
                _normalize_history()
                r = client.messages.create(
                    model=BRAIN_LIGHT, max_tokens=1024,
                    system=sys_prompt_plain, messages=conversation_history)
                reply = r.content[0].text
                conversation_history.append({"role": "assistant", "content": reply})
                return clean_text(reply)
            except Exception as e2:
                import traceback
                print("[diag] Brain error full traceback:", flush=True)
                traceback.print_exc()
                return f"[Error connecting to Brain: {e2}]"

# --- Daily briefing ("good morning / good evening") --------------------------
# Weather codes from the WMO standard used by Open-Meteo (free, no API key).
_WMO_WEATHER = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle",
    55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain",
    67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "rain showers", 81: "rain showers",
    82: "violent rain showers", 85: "snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail",
}

def get_weather(when="today"):
    """Current/forecast weather for Alfei Menashe via Open-Meteo (free, no key).
    `when` is 'today' or 'tomorrow'. Returns a short English summary string in
    Celsius. Never throws; returns a friendly note on failure."""
    lat, lon = 32.1772, 34.9947  # Alfei Menashe
    url = ("https://api.open-meteo.com/v1/forecast"
           "?latitude=%s&longitude=%s"
           "&current=temperature_2m,weather_code"
           "&daily=temperature_2m_max,temperature_2m_min,weather_code"
           "&timezone=auto" % (lat, lon))
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return "weather unavailable (%s)" % e
    daily = d.get("daily", {})
    idx = 1 if when == "tomorrow" else 0
    try:
        hi = round(daily["temperature_2m_max"][idx])
        lo = round(daily["temperature_2m_min"][idx])
        desc = _WMO_WEATHER.get(daily["weather_code"][idx], "")
        if when == "tomorrow":
            return "%s, high %dC, low %dC" % (desc, hi, lo)
        cur = d.get("current", {}).get("temperature_2m")
        cur_s = ("currently %dC, " % round(cur)) if cur is not None else ""
        return "%s%s, high %dC, low %dC" % (cur_s, desc, hi, lo)
    except Exception:
        return "weather unavailable"

def _briefing_part_from_clock(now):
    """Map the hour to a part of day: morning (5-11), afternoon (12-17),
    evening (18-4)."""
    h = now.hour
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 18:
        return "afternoon"
    return "evening"

# Greeting phrases that trigger a briefing. Kept short so they only fire on a
# greeting, not inside a longer question.
_BRIEFING_MORNING = ["good morning", "morning jarvis", "\u05d1\u05d5\u05e7\u05e8 \u05d8\u05d5\u05d1", "boker tov"]
_BRIEFING_AFTERNOON = ["good afternoon", "\u05e6\u05d4\u05e8\u05d9\u05d9\u05dd \u05d8\u05d5\u05d1\u05d9\u05dd", "tzohoraim tovim"]
_BRIEFING_EVENING = ["good evening", "\u05e2\u05e8\u05d1 \u05d8\u05d5\u05d1", "erev tov"]

def detect_briefing(text):
    """Return 'morning' / 'afternoon' / 'evening' if the message is a greeting
    that should trigger a daily briefing, else None. Only matches short
    messages so 'good morning, what is the weather in Paris' is left to the
    normal brain."""
    if not text:
        return None
    t = text.lower().strip()
    for ch in ",.!?-:;\"'":
        t = t.replace(ch, " ")
    t = " ".join(t.split())
    if len(t.split()) > 4:
        return None
    if any(w in t for w in _BRIEFING_EVENING):
        return "evening"
    if any(w in t for w in _BRIEFING_AFTERNOON):
        return "afternoon"
    if any(w in t for w in _BRIEFING_MORNING):
        return "morning"
    return None

def _training_briefing_section():
    """Read training_log.json next to jarvis.py and return a short facts
    string for the daily briefing. Returns an empty string if no log
    exists (the briefing simply skips training in that case). Best-effort
    - any parse error returns the empty string.

    Expected JSON fields (all optional):
      last_weight_kg          number, e.g. 71.2
      last_weight_date        ISO date "YYYY-MM-DD"
      last_workout_type       string, e.g. "running 5km"
      last_workout_date       ISO date
      weekly_workouts         number
      weight_target_min_kg    number (defaults to 68 - Matan's red line)
    """
    try:
        p = Path(__file__).resolve().parent / "training_log.json"
        if not p.exists():
            return ""
        data = json.loads(p.read_text(encoding="utf-8"))
        lines = []
        w = data.get("last_weight_kg")
        wd = data.get("last_weight_date")
        tgt = data.get("weight_target_min_kg", 68)
        if w is not None:
            line = "Last weight: %g kg" % float(w)
            if wd:
                try:
                    d0 = datetime.date.fromisoformat(wd)
                    days = (datetime.date.today() - d0).days
                    if days == 0:
                        line += " (today)"
                    elif days == 1:
                        line += " (yesterday)"
                    else:
                        line += " (%d days ago)" % days
                except Exception:
                    pass
            try:
                gap = float(w) - float(tgt)
                if gap >= 0:
                    line += "; %+.1f kg above %g kg target" % (gap, tgt)
                else:
                    line += ("; %+.1f kg BELOW %g kg target "
                             "- red line crossed") % (gap, tgt)
            except Exception:
                pass
            lines.append(line)
        wt = data.get("last_workout_type")
        wtd = data.get("last_workout_date")
        if wt and wtd:
            try:
                d0 = datetime.date.fromisoformat(wtd)
                days = (datetime.date.today() - d0).days
                if days == 0:
                    when = "today"
                elif days == 1:
                    when = "yesterday"
                else:
                    when = "%d days ago" % days
                lines.append("Last workout: %s, %s" % (wt, when))
            except Exception:
                lines.append("Last workout: %s on %s" % (wt, wtd))
        elif wt:
            lines.append("Last workout: %s" % wt)
        wc = data.get("weekly_workouts")
        if wc is not None:
            lines.append("Workouts this week: %s" % wc)
        return "\n".join(lines)
    except Exception:
        return ""


def daily_briefing(part="auto", lang="en"):
    """Build and return a short spoken briefing string. Gathers weather,
    calendar, and email, then has the brain phrase it warmly in `lang`
    (he/en). `part` is 'morning' / 'afternoon' / 'evening' / 'auto'."""
    if not ANTHROPIC_API_KEY:
        return "[Error: Missing API Key in .env]"
    now = datetime.datetime.now()
    if part == "auto":
        part = _briefing_part_from_clock(now)
    if part == "evening":
        focus, day, greet = "tomorrow", now + datetime.timedelta(days=1), "Good evening"
    elif part == "afternoon":
        focus, day, greet = "today", now, "Good afternoon"
    else:
        focus, day, greet = "today", now, "Good morning"

    # Weather
    weather = get_weather("tomorrow" if focus == "tomorrow" else "today")

    # Calendar window
    local_tz = datetime.datetime.now().astimezone().tzinfo
    if focus == "tomorrow":
        tmin = day.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        tmin = now
    tmax = day.replace(hour=23, minute=59, second=59, microsecond=0)
    try:
        cal = calendar_read(tmin.replace(tzinfo=local_tz).isoformat(),
                            tmax.replace(tzinfo=local_tz).isoformat())
    except Exception as e:
        cal = "Calendar unavailable: %s" % e

    # Email summary
    try:
        mail = gmail_read(max_results=8)
    except Exception as e:
        mail = "Email unavailable: %s" % e

    training = _training_briefing_section()
    news = _news_briefing_section(lang)
    facts = (
        "GREETING: %s\n"
        "DATE (%s): %s\n"
        "WEATHER (%s, Alfei Menashe): %s\n"
        "%s"
        "%s"
        "CALENDAR (%s):\n%s\n\n"
        "EMAIL:\n%s\n"
        % (greet, focus, day.strftime("%A, %d %B %Y"),
           focus, weather,
           ("TRAINING:\n" + training + "\n\n") if training else "",
           ("NEWS:\n" + news + "\n\n") if news else "",
           focus, cal, mail))

    sys_p = (
        "You are Achilles, a calm British-butler AI assistant. You are giving your "
        "creator (address him as \"sir\" in English or \"\u05d0\u05d3\u05d5\u05e0\u05d9\" in Hebrew) a short "
        "spoken %s briefing. Use the data below. Speak warmly in %s, in 2 to 5 "
        "short sentences. Open with the greeting, then mention the weather, the "
        "key calendar events for the %s, anything notable in the email, and if "
        "a TRAINING section is present, briefly note the training status - "
        "especially if the user is below the 68 kg minimum target or hasn't "
        "trained in several days. If a NEWS section is present, briefly mention "
        "one or two of the headlines. If the calendar, email, or training data is "
        "not connected, unavailable, or empty, simply skip that part without "
        "explaining the technical reason. Do not read out dates as ISO "
        "strings; say them naturally. Plain text only: no markdown, no bullet "
        "points, no URLs."
        % (part, "Hebrew" if lang == "he" else "English", focus))

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=400,
            system=sys_p,
            messages=[{"role": "user", "content": facts}])
        parts = [b.text for b in r.content if getattr(b, "type", None) == "text"]
        reply = " ".join(p.strip() for p in parts if p.strip()).strip()
        return clean_text(reply) or (greet + ", sir.")
    except Exception as e:
        import traceback
        print("[diag] Briefing error full traceback:", flush=True)
        traceback.print_exc()
        # Fall back to a plain, locally-built briefing so JARVIS still speaks.
        return clean_text("%s, sir. The weather is %s." % (greet, weather))

# --- Timers / reminders ------------------------------------------------------
_active_timers = []
_last_timer_lang = "en"

def _timer_fire(label, lang):
    """Called when a timer elapses: announce it by voice (and on the orb)."""
    if lang == "he":
        msg = ("\u05d0\u05d3\u05d5\u05e0\u05d9, \u05d4\u05d8\u05d9\u05d9\u05de\u05e8 \u05dc%s \u05d4\u05e1\u05ea\u05d9\u05d9\u05dd." % label) if label \
            else "\u05d0\u05d3\u05d5\u05e0\u05d9, \u05d4\u05d8\u05d9\u05d9\u05de\u05e8 \u05d4\u05e1\u05ea\u05d9\u05d9\u05dd."
    else:
        msg = ("Sir, your %s timer is up." % label) if label else "Sir, your timer is up."
    try:
        if APP is not None:
            APP.ui(lambda: APP._push("JARVIS", msg))
    except Exception:
        pass
    try:
        beep()
    except Exception:
        pass
    try:
        speak(msg)
    except Exception:
        pass

def set_timer(minutes, label=None):
    """Start a countdown timer. After `minutes` minutes JARVIS announces it by
    voice in the last conversation language. Returns a short confirmation
    string for the brain to phrase naturally."""
    lang = globals().get("_last_timer_lang", "en")
    try:
        mins = float(minutes)
    except Exception:
        return "I need a number of minutes for the timer, sir."
    if mins <= 0:
        return "The timer needs to be longer than zero, sir."
    secs = mins * 60.0
    # v4.67: self-removing wrapper so fired timers don't leak in _active_timers
    # forever (only undo used to prune them; normally-elapsed timers stayed
    # referenced for the whole process lifetime).
    def _fire(_label=label, _lang=lang):
        try:
            _timer_fire(_label, _lang)
        finally:
            try:
                _active_timers.remove(t)
            except ValueError:
                pass
    t = threading.Timer(secs, _fire)
    t.daemon = True
    t.start()
    _active_timers.append(t)
    _record_action("set_timer", {"timer": t, "label": label})
    if mins >= 1:
        dur = "1 minute" if mins == 1 else ("%g minutes" % mins)
    else:
        dur = "%d seconds" % int(round(secs))
    if label:
        return "Timer set for %s (%s), sir." % (dur, label)
    return "Timer set for %s, sir." % dur

# --- Spotify control ---------------------------------------------------------
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_SCOPES = ("user-read-playback-state user-modify-playback-state "
                  "user-read-currently-playing")
_SPOTIFY_TOKEN_FILE = Path("spotify_token.json")


def _spotify_oauth_flow():
    """First-time auth: open browser, capture redirect, exchange code for
    tokens, persist them. Returns the token dict or None on failure."""
    import http.server, urllib.parse, urllib.request, webbrowser, threading, base64
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        print("Spotify: SPOTIFY_CLIENT_ID/SECRET missing from .env")
        return None
    code_holder = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(q)
            if "code" in params:
                code_holder["code"] = params["code"][0]
                body = ("<html><body style='font-family:sans-serif;"
                        "background:#000;color:#fff;text-align:center;"
                        "padding-top:80px'><h1>JARVIS Spotify connected.</h1>"
                        "<p>You can close this tab.</p></body></html>").encode()
            else:
                err = params.get("error", ["unknown"])[0]
                code_holder["error"] = err
                body = (("<html><body><h1>Auth failed: %s</h1></body></html>")
                        % err).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    try:
        server = http.server.HTTPServer(("127.0.0.1", 8888), _Handler)
    except OSError as e:
        print("Spotify: port 8888 busy:", e)
        return None
    t = threading.Thread(target=server.handle_request, daemon=True)
    t.start()

    auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": SPOTIFY_CLIENT_ID,
        "scope": SPOTIFY_SCOPES,
        "redirect_uri": SPOTIFY_REDIRECT_URI,
    })
    print("Spotify: opening browser for one-time authorization...")
    webbrowser.open(auth_url)
    t.join(timeout=180)
    try:
        server.server_close()
    except Exception:
        pass

    code = code_holder.get("code")
    if not code:
        err = code_holder.get("error", "no code returned (timeout?)")
        print("Spotify auth failed:", err)
        return None

    auth_b64 = base64.b64encode(
        ("%s:%s" % (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)).encode()
    ).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": SPOTIFY_REDIRECT_URI,
        }).encode(),
        headers={
            "Authorization": "Basic " + auth_b64,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            tokens = json.loads(r.read())
    except Exception as e:
        print("Spotify token exchange failed:", repr(e))
        return None
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    _SPOTIFY_TOKEN_FILE.write_text(json.dumps(tokens))
    print("Spotify: connected.")
    return tokens


def _spotify_refresh(refresh_token):
    import urllib.parse, urllib.request, base64
    auth_b64 = base64.b64encode(
        ("%s:%s" % (SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)).encode()
    ).decode()
    req = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        data=urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }).encode(),
        headers={
            "Authorization": "Basic " + auth_b64,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            tokens = json.loads(r.read())
    except Exception as e:
        print("Spotify refresh failed:", repr(e))
        return None
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)
    if "refresh_token" not in tokens:
        tokens["refresh_token"] = refresh_token
    _SPOTIFY_TOKEN_FILE.write_text(json.dumps(tokens))
    return tokens


def _spotify_token():
    """Return a valid access token, refreshing or running OAuth as needed."""
    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None
    tokens = None
    if _SPOTIFY_TOKEN_FILE.exists():
        try:
            tokens = json.loads(_SPOTIFY_TOKEN_FILE.read_text())
        except Exception:
            tokens = None
    if tokens and time.time() >= tokens.get("expires_at", 0) - 30:
        tokens = _spotify_refresh(tokens.get("refresh_token", ""))
    if not tokens:
        tokens = _spotify_oauth_flow()
    return tokens.get("access_token") if tokens else None


def _spotify_request(method, path, params=None, body=None):
    import urllib.parse, urllib.request, urllib.error
    token = _spotify_token()
    if not token:
        return {"error": "Spotify not connected, sir."}
    url = "https://api.spotify.com/v1" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
            return json.loads(raw) if raw else {"ok": True}
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode()
        except Exception:
            pass
        if e.code == 404:
            return {"error": "No active Spotify device, sir. Open Spotify on your phone or computer first."}
        if e.code == 403:
            return {"error": "Spotify Premium is required for that, sir."}
        return {"error": "HTTP %d: %s" % (e.code, body_txt[:200])}
    except Exception as e:
        return {"error": repr(e)}



def _spotify_ensure_active_device():
    """Make sure Spotify has an active device. Lists devices; if any exist but
    none is active, transfers playback to the first available one. Returns
    (ok: bool, error_message: str | None)."""
    r = _spotify_request("GET", "/me/player/devices")
    if "error" in r:
        return False, r["error"]
    devices = r.get("devices") or []
    if not devices:
        return False, "Spotify isn't open anywhere, sir. Open Spotify on a device first."
    if any(d.get("is_active") for d in devices):
        return True, None
    target = devices[0]
    transfer = _spotify_request("PUT", "/me/player",
                                body={"device_ids": [target["id"]], "play": False})
    if "error" in transfer:
        return False, ("Couldn't activate %s, sir: %s"
                       % (target.get("name", "device"), transfer["error"]))
    return True, None


def spotify_play(query=None):
    """Play music on Spotify. With a query, search and play the best match.
    Without a query, resume current playback."""
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    if query:
        result = _spotify_request("GET", "/search", params={
            "q": query, "type": "track,artist,album,playlist", "limit": 3,
        })
        if "error" in result:
            return "Couldn't search Spotify: %s" % result["error"]
        tracks = (result.get("tracks") or {}).get("items") or []
        playlists = (result.get("playlists") or {}).get("items") or []
        albums = (result.get("albums") or {}).get("items") or []
        artists = (result.get("artists") or {}).get("items") or []
        if tracks:
            t = tracks[0]
            r = _spotify_request("PUT", "/me/player/play",
                                 body={"uris": [t["uri"]]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing %s by %s, sir." % (
                t.get("name", "Unknown"),
                (t.get("artists") or [{"name": "Unknown"}])[0].get("name", ""),
            )
        if playlists:
            p = playlists[0]
            r = _spotify_request("PUT", "/me/player/play",
                                 body={"context_uri": p["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing the playlist %s, sir." % p.get("name", "")
        if albums:
            a = albums[0]
            r = _spotify_request("PUT", "/me/player/play",
                                 body={"context_uri": a["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing the album %s, sir." % a.get("name", "")
        if artists:
            ar = artists[0]
            r = _spotify_request("PUT", "/me/player/play",
                                 body={"context_uri": ar["uri"]})
            if "error" in r:
                return "Couldn't play: %s" % r["error"]
            return "Playing music by %s, sir." % ar.get("name", "")
        return "No results on Spotify for '%s', sir." % query
    r = _spotify_request("PUT", "/me/player/play")
    if "error" in r:
        return "Couldn't resume: %s" % r["error"]
    return "Resumed, sir."


def spotify_pause():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("PUT", "/me/player/pause")
    if "error" in r:
        return "Couldn't pause: %s" % r["error"]
    return "Paused, sir."


def spotify_next():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("POST", "/me/player/next")
    if "error" in r:
        return "Couldn't skip: %s" % r["error"]
    return "Next track, sir."


def spotify_previous():
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("POST", "/me/player/previous")
    if "error" in r:
        return "Couldn't go back: %s" % r["error"]
    return "Previous track, sir."


def spotify_volume(level):
    try:
        v = int(level)
    except Exception:
        return "I need a volume number from 0 to 100, sir."
    v = max(0, min(100, v))
    ok, err = _spotify_ensure_active_device()
    if not ok:
        return err
    r = _spotify_request("PUT", "/me/player/volume",
                         params={"volume_percent": v})
    if "error" in r:
        return "Couldn't set volume: %s" % r["error"]
    return "Volume set to %d%%, sir." % v


def spotify_now_playing():
    r = _spotify_request("GET", "/me/player/currently-playing")
    if "error" in r:
        return r["error"]
    if not r or not r.get("item"):
        return "Nothing playing, sir."
    item = r["item"]
    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
    return "%s by %s, sir." % (item.get("name", "Unknown"), artists)


# --- ElevenLabs voice (premium, English only) -------------------------------
def _el_pick_voice_id():
    """Find a good British voice ID from the account, once, and cache it.
    Resolves by NAME (no fragile hard-coded ID): tries EL_PREFERRED_VOICES in
    order, then any available voice. Returns None if it can't (so we fall back
    to edge-tts).
    NOTE (v3.13): _el_voice_id_cache is pre-set to a chosen voice ID above, so
    this returns it immediately and the lookup below is normally skipped."""
    global _el_voice_id_cache
    if _el_voice_id_cache:
        return _el_voice_id_cache
    if not ELEVENLABS_API_KEY:
        print("[diag] ElevenLabs: no API key in environment -> using edge-tts.", flush=True)
        return None
    try:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": ELEVENLABS_API_KEY})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        voices = data.get("voices", [])
        by_name = {(v.get("name") or "").lower(): v.get("voice_id") for v in voices}
        for pref in EL_PREFERRED_VOICES:
            vid = by_name.get(pref.lower())
            if vid:
                _el_voice_id_cache = vid
                print(f"[diag] ElevenLabs voice selected: {pref} ({vid})", flush=True)
                return vid
        if voices:
            _el_voice_id_cache = voices[0].get("voice_id")
            print("[diag] ElevenLabs voice (first available):", voices[0].get("name"), flush=True)
            return _el_voice_id_cache
        print("[diag] ElevenLabs: account has no voices.", flush=True)
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        print("[diag] ElevenLabs voices HTTP error:", e.code, detail, flush=True)
    except Exception as e:
        print("[diag] ElevenLabs voice lookup failed:", repr(e), flush=True)
    return None

def speak_elevenlabs(text, fn):
    """Render `text` to `fn` (mp3) with ElevenLabs. Returns True on success,
    False to signal the caller to fall back to edge-tts."""
    if not ELEVENLABS_API_KEY:
        return False
    vid = _el_pick_voice_id()
    if not vid:
        return False
    try:
        body = json.dumps({
            "text": text,
            "model_id": EL_MODEL,
            # calm, consistent butler delivery
            "voice_settings": {"stability": 0.55, "similarity_boost": 0.75,
                               "style": 0.0, "use_speaker_boost": True},
        }).encode("utf-8")
        url = ("https://api.elevenlabs.io/v1/text-to-speech/%s"
               "?output_format=mp3_44100_128" % vid)
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"xi-api-key": ELEVENLABS_API_KEY,
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio = resp.read()
        if not audio:
            return False
        with open(fn, "wb") as f:
            f.write(audio)
        return True
    except urllib.error.HTTPError as e:
        # 401 = bad key, 429 = quota used up, etc. Print it so we can see why.
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        print("[diag] ElevenLabs TTS HTTP error:", e.code, detail, flush=True)
        return False
    except Exception as e:
        print("[diag] ElevenLabs TTS error:", repr(e), flush=True)
        return False

async def _speak(text, voice, fn="jarvis_reply.mp3"):
    # Slow the pace a touch and lower the pitch slightly -> calmer, more
    # natural "butler" delivery instead of a fast, flat robotic read.
    await edge_tts.Communicate(text, voice, rate="-8%", pitch="-3Hz").save(fn)

# v5.16y: play_audio blocks until MCI reports playback finished ("play ... wait"),
# so speak() only returns once ACHILLES has actually stopped talking. Every call
# site used to add a SECOND wait estimated from the word count, which was pure
# dead time: the orb stayed on "speaking" and the mic stayed shut for up to 14s
# after the audio ended. That estimate is gone; this tiny guard is all that is
# left, to let the output device settle before the mic reopens.
_POST_SPEAK_GUARD_S = 0.35

def play_audio(path="jarvis_reply.mp3"):
    try:
        p = os.path.abspath(path)
        mci = ctypes.windll.winmm.mciSendStringW
        mci("close jarvisaudio", None, 0, 0)
        if mci('open "%s" type mpegvideo alias jarvisaudio' % p, None, 0, 0) == 0:
            mci("play jarvisaudio wait", None, 0, 0)
            mci("close jarvisaudio", None, 0, 0)
    except Exception as e:
        print("Audio playback error:", e)

def stop_audio():
    """Immediately stop whatever JARVIS is currently playing (used by F5)."""
    try:
        mci = ctypes.windll.winmm.mciSendStringW
        mci("stop jarvisaudio", None, 0, 0)
        mci("close jarvisaudio", None, 0, 0)
    except Exception:
        pass

def _tts_state(value):
    """v5.16z: drive the orb from inside speak(), because the call sites cannot.
    They flip the orb to "speaking" and then call speak(), but speak() spends the
    first stretch SYNTHESISING - shipping the whole reply to edge-tts/ElevenLabs
    and waiting for the finished mp3 to come back. During that stretch nothing is
    audible, so "speaking" is a lie and the assistant looks hung. Best effort:
    never let an orb update break the voice path."""
    try:
        if APP is not None:
            APP.state = value
    except Exception:
        pass

def _tts_state_get():
    try:
        if APP is not None:
            return APP.state
    except Exception:
        pass
    return None

def _tts_log(engine, chars, synth_s, play_s):
    """v5.16z: one line per spoken reply, so the synthesis wait is a measured
    number instead of a guess. Absolute path - a relative one would follow the
    working directory and land somewhere unpredictable."""
    try:
        p = Path(__file__).resolve().parent / "tts_timing.log"
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(p, "a", encoding="utf-8") as f:
            f.write("%s engine=%s chars=%d synth=%.2fs play=%.2fs%s"
                    % (stamp, engine, chars, synth_s, play_s, "\n"))
    except Exception:
        pass

def speak(text):
    # Use a UNIQUE filename each time. The old code always wrote the same
    # 'jarvis_reply.mp3'; if the previous file was still locked (another copy of
    # JARVIS, or playback not fully closed) the save failed with
    # "Permission denied: jarvis_reply.mp3". A fresh name avoids that entirely.
    fn = "jarvis_reply_%d.mp3" % (int(time.time() * 1000) % 1000000)
    _prev_state = _tts_state_get()
    # Synthesis is still thinking-time: no audio exists yet.
    _tts_state("thinking")
    _t0 = time.time()
    _engine = "none"
    _t_synth = 0.0
    _t_play = 0.0
    try:
        produced = False
        # Voice selection: use the ElevenLabs Alfred voice for replies that are
        # MOSTLY English (i.e. English with a sprinkling of Hebrew place names
        # is still English). Replies that are mostly Hebrew skip ElevenLabs and
        # use edge-tts, which sounds more natural for Hebrew.
        mostly_he = is_mostly_hebrew(text)
        if not mostly_he:
            produced = speak_elevenlabs(text, fn)
            if produced:
                _engine = "elevenlabs"
        if not produced:
            voice = VOICE_HEBREW if mostly_he else VOICE_ENGLISH
            try:
                asyncio.run(_speak(text, voice, fn))
                produced = True
                _engine = "edge"
            except Exception as e:
                if not mostly_he:
                    try:
                        asyncio.run(_speak(text, VOICE_ENGLISH_FALLBACK, fn))
                        produced = True
                        _engine = "edge_fallback"
                    except Exception as e2:
                        print("Voice error (fallback):", e2)
                else:
                    print("Voice error:", e)
        _t_synth = time.time() - _t0
        if produced:
            # Only NOW does sound actually start.
            _tts_state("speaking")
            _t1 = time.time()
            play_audio(fn)
            _t_play = time.time() - _t1
    except Exception as e:
        print("Voice error:", e)
    finally:
        _tts_log(_engine, len(text or ""), _t_synth, _t_play)
        # Hand the orb back exactly as it was found, so callers that never
        # managed the state (boot greeting, F3 repeat) do not strand it.
        if _prev_state is not None:
            _tts_state(_prev_state)
        # Best-effort cleanup so these temp files don't pile up. play_audio
        # blocks until playback ends and closes the handle, so by here it's free.
        try:
            os.remove(fn)
        except Exception:
            pass

def save_log(u, j):
    now = datetime.datetime.now()
    lf = Path(SSD_OBSIDIAN_VAULT) / f"Log_{now.strftime('%Y-%m-%d')}.md"
    with open(lf, "a", encoding="utf-8") as f:
        f.write(f"\n### Chat - {now.strftime('%H:%M:%S')}\n**You:** {u}\n\n**JARVIS:** {j}\n\n---\n")

# =============================================================================
# SEARCH PANEL BACKEND (image + web search via Claude)
# =============================================================================
# Global handle to the running App, so tool functions (which run on a worker
# thread inside think()) can ask the main thread to open the panel window.
APP = None

def _image_block_from_path(path):
    """Read an image file and return an Anthropic image content block, or None."""
    try:
        mt = mimetypes.guess_type(path)[0] or "image/jpeg"
        if mt not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
            mt = "image/jpeg"
        with open(path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode("ascii")
        return {"type": "image",
                "source": {"type": "base64", "media_type": mt, "data": data}}
    except Exception as e:
        print("Image read error:", repr(e))
        return None

def _link_depth_score(url):
    """Rough 'how specific is this URL' score, used ONLY to re-order the
    FALLBACK links (when the brain did not hand us curated product links).
    Pushes deep product pages above bare store homepages."""
    try:
        p = urllib.parse.urlparse(url or "")
        segs = [s for s in (p.path or "").split("/") if s]
        score = len(segs) * 2
        if p.query:
            score += 3
        low = (url or "").lower()
        for kw in ("modelid", "/item", "/p/", "product", "/dp/", "sku", ".aspx"):
            if kw in low:
                score += 4
        return score
    except Exception:
        return 0


def search_with_optional_image(user_text, image_path=None, lang="he"):
    """Search panel: an EXTENSION of the main voice brain. Uses the same
    JARVIS_SYSTEM_PROMPT (so it shares the user's personal context, home
    address, family, Israeli cities, sir/adoni, etc.) plus a search-specific
    overlay (Israeli stores, 2-sentence cap) and place/direction tools.
    Stays separate from think() because it does NOT touch
    conversation_history - each search is one-shot."""
    if not ANTHROPIC_API_KEY:
        return ("[Error: Missing API Key in .env]", [])
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Base = the same system prompt the main voice mode uses, so search
    # inherits all personal context.
    sys_prompt = JARVIS_SYSTEM_PROMPT
    # Search-specific overlay layered on top.
    sys_prompt += (
        "\n\nYOU ARE NOW IN THE PRODUCT SEARCH WINDOW. Additional rules for "
        "this mode:\n"
        "- He is in ISRAEL and can only buy from stores that operate in "
        "Israel. When finding where to buy something, your web_search query "
        "MUST restrict results to Israeli stores. Build the query with "
        "explicit site filters, e.g.:\n"
        "  <product name> site:zap.co.il OR site:ksp.co.il OR site:bug.co.il "
        "OR site:ivory.co.il OR site:idigital.co.il OR site:amazon.co.il\n"
        "Also run a second query in Hebrew if you know the Hebrew term: "
        "'<product> \u05d9\u05e9\u05e8\u05d0\u05dc \u05de\u05d7\u05d9\u05e8'. "
        "Prefer Zap.co.il - it compares prices across Israeli retailers. "
        "Give prices in shekels (NIS / \u20aa) only. NEVER return Amazon.com, "
        "B&H US, AliExpress or other foreign stores - only stores that sell "
        "and ship inside Israel. If you cannot find it in an Israeli store, "
        "say so plainly instead of falling back to a foreign store.\n"
        "- DEFAULT MARKET vs EXPLICIT OVERRIDE: the Israel-only rule "
        "above is the DEFAULT. If the user EXPLICITLY names another "
        "country or market for this search (for example: search the US "
        "market, find this in Germany, or in Hebrew תחפש בשוק האמריקאי "
        "/ בגרמניה), then for THIS request search that country instead, "
        "give prices in the local currency of that country, and the "
        "Israel-only / no-foreign-stores rule does NOT apply. Only "
        "override when a country or market is named explicitly; if none "
        "is mentioned, always default to Israel.\n"
        "- If an image is attached, first identify exactly what the product "
        "is (type, material, colour, style, brand if visible), then search "
        "for it in Israel as above.\n"
        "- You CAN use find_places and get_directions in this window too - "
        "if the user asks where to buy/eat/visit, or asks about distance / "
        "travel time, use those tools as needed. The user's home address is "
        "in the main context above; use it as the default origin for travel "
        "times.\n"
        "- Reply in %s.\n"
        "- CRITICAL FORMAT: keep your reply to AT MOST 2 short sentences. "
        "NEVER write numbered lists, bullet points, paragraphs, or long "
        "descriptions inside your reply text - the user already sees the "
        "clickable result links shown separately below. Your job is only a "
        "very brief headline. Example: 'Found several well-reviewed pizza "
        "places in Kfar Saba, sir. Top mentions include Gutleib and La "
        "Cappa - the links are below.' That's it - 2 sentences, no more. "
        "NEVER speak or write out URLs/links in your reply text.\n\n"
        "DIRECT PRODUCT LINKS - VERY IMPORTANT:\n"
        "After your short spoken reply, output a machine-readable block "
        "listing the BEST links you actually found in the web search "
        "results. This block is shown to the user as clickable rows and is "
        "NOT part of your spoken reply, so putting URLs in it does NOT "
        "break the no-URLs-in-the-reply rule above.\n"
        "- Prefer DIRECT PRODUCT PAGES (the page for the specific item, "
        "with its price) - NOT a store homepage or a broad category/search "
        "page. Good: a zap.co.il model page or a ksp.co.il item page for "
        "the exact product. Bad: the bare ksp.co.il or zap.co.il home "
        "page.\n"
        "- Only use URLs that actually appeared in the web search results. "
        "Never invent, guess, or shorten a URL.\n"
        "- Up to 6 links, best first; put exact-product zap.co.il "
        "price-comparison pages first when you have them.\n"
        "- If you truly found no good product links, leave the block "
        "empty.\n"
        "Output it EXACTLY in this form, on its own lines at the very end:\n"
        "<<<LINKS>>>\n"
        "short title | https://full-url\n"
        "short title | https://full-url\n"
        "<<<ENDLINKS>>>"
        % ("Hebrew" if lang == "he" else "English"))
    sys_prompt += ("\nCurrent local time (Israel): "
                   + datetime.datetime.now().strftime("%Y-%m-%d %H:%M (%A)"))

    content = []
    if image_path:
        blk = _image_block_from_path(image_path)
        if blk:
            content.append(blk)
    content.append({"type": "text",
                    "text": (user_text or "Find this product.")})

    # web_search + find_places + get_directions. calendar/gmail/open_app are
    # intentionally excluded - they do not belong in a product-search context.
    tools = [{"type": "web_search_20250305", "name": "web_search",
              "max_uses": 4}]
    for t in LOCAL_TOOLS:
        if t.get("name") in ("find_places", "get_directions"):
            tools.append(t)

    links = []
    spoken_parts = []
    try:
        msgs = [{"role": "user", "content": content}]
        for _ in range(5):
            r = client.messages.create(
                model="claude-sonnet-5", max_tokens=700,
                system=sys_prompt,
                messages=msgs, tools=tools)
            msgs.append({"role": "assistant", "content": r.content})
            # Collect text + any web_search links from this turn.
            for b in r.content:
                bt = getattr(b, "type", None)
                if bt == "text" and getattr(b, "text", "").strip():
                    spoken_parts.append(b.text.strip())
                elif bt == "web_search_tool_result":
                    results = getattr(b, "content", None) or []
                    for item in results:
                        url = getattr(item, "url", None)
                        title = getattr(item, "title", None) or url
                        if url:
                            links.append((title, url))
            # If Claude called find_places / get_directions locally, run them
            # and feed the results back. web_search is server-side and needs
            # no local handling.
            if r.stop_reason == "tool_use":
                tool_results = []
                for block in r.content:
                    if getattr(block, "type", None) == "tool_use" and \
                            block.name in ("find_places", "get_directions"):
                        out = run_local_tool(block.name, block.input or {})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": out,
                        })
                if tool_results:
                    msgs.append({"role": "user", "content": tool_results})
                continue
            break
        # v4.13: the brain hands us its CHOSEN product links in a machine
        # block  <<<LINKS>>> title | url ... <<<ENDLINKS>>>  at the end of
        # its reply. Prefer those (curated, direct product pages) over the
        # raw search results, and strip the block out of the spoken text.
        full_text = " ".join(spoken_parts)
        brain_links = []
        mblk = re.search(r"<<<\s*LINKS\s*>>>(.*?)<<<\s*ENDLINKS\s*>>>",
                         full_text, re.DOTALL | re.IGNORECASE)
        block_body = mblk.group(1) if mblk else ""
        if block_body:
            for line in block_body.splitlines():
                mu = re.search(r"(https?://\S+)", line)
                if not mu:
                    continue
                url = mu.group(1).rstrip(").,]\u00bb\"'")
                title = line[:mu.start()].strip().rstrip("|").strip() or url
                brain_links.append((title, url))
        # Remove the block (and any dangling, un-closed one) from what we
        # show/speak, then strip any stray URLs as before.
        spoken_raw = re.sub(r"<<<\s*LINKS\s*>>>.*?<<<\s*ENDLINKS\s*>>>", "",
                            full_text, flags=re.DOTALL | re.IGNORECASE)
        spoken_raw = re.sub(r"<<<\s*LINKS\s*>>>.*$", "", spoken_raw,
                            flags=re.DOTALL | re.IGNORECASE)
        spoken_raw = re.sub(r"https?://\S+", "", spoken_raw)
        spoken_raw = re.sub(r"\bwww\.\S+", "", spoken_raw)
        spoken = clean_text(spoken_raw).strip() or "Here is what I found, sir."
        # Pick which link set to show: the brain's curated picks if any,
        # otherwise the raw web_search results re-ordered so deeper product
        # pages beat bare homepages (so the list is NEVER empty).
        if brain_links:
            chosen = brain_links
        else:
            chosen = sorted(links, key=lambda tu: _link_depth_score(tu[1]),
                            reverse=True)
        # de-duplicate by URL, keep order, cap at 8
        seen, uniq = set(), []
        for t, u in chosen:
            if u not in seen:
                seen.add(u)
                uniq.append((t, u))
        return spoken, uniq[:8]
    except Exception as e:
        import traceback
        print("[diag] Search panel full traceback:", flush=True)
        traceback.print_exc()
        return (f"[Search error: {e}]", [])


RAMPS = {
    # Red-orange "molten core" palette. Each state is a slightly different shade
    # of red-orange so you can still tell idle / listening / thinking apart.
    "loading":   ((70, 30, 15),   (150, 80, 40)),
    "idle":      ((120, 35, 10),  (255, 150, 60)),
    "listening": ((150, 45, 10),  (255, 180, 80)),
    "thinking":  ((140, 25, 10),  (255, 120, 40)),
    "speaking":  ((160, 55, 15),  (255, 200, 100)),
}
# Transparency key color. Near-black (not magenta) so the orb's soft glow blends
# toward dark = natural, instead of toward magenta = an ugly pink halo.
KEY = "#050507"
# v4.60: FINAL - the face is the PIL black hole drawn INSIDE the original
# floating frameless orb window. It pops on wake exactly like the orange
# ball always did. No browser window ever opens on the PC; the phone keeps
# the full WebGL page (achilles.html). Do not set this to "blackhole".
ACHILLES_FACE = "orb"

def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else int(v))

def _hexcol(r, g, b):
    return "#%02x%02x%02x" % (_clamp(r), _clamp(g), _clamp(b))

# ============================ TELEGRAM BRIDGE ============================
# Talk to JARVIS from your phone via a Telegram bot, and let JARVIS push
# messages to you. Locked to ONE chat via a pairing code, so a stranger who
# finds the bot cannot read your calendar / notes. Uses long-polling (no
# public URL needed) on a daemon thread. Token = TELEGRAM_BOT_TOKEN in .env.
_TG_CHAT_FILE = str(Path(__file__).resolve().parent / "telegram_chat.json")
_tg_chat_id = None
_tg_pair_code = None
_tg_offset = 0

def _loc_log(msg):
    # v4.87: file-based diagnostics for the location-sharing voice path,
    # same pattern as orb_diag.log - pythonw has no console, so silent
    # failures here were previously invisible.
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "location_diag.log")
        with open(_p, "a", encoding="utf-8") as _f:
            _f.write("[%s] %s\n" % (datetime.datetime.now().strftime("%H:%M:%S"), msg))
    except Exception:
        pass

def _tg_api(method, params=None, timeout=60):
    if not TELEGRAM_BOT_TOKEN:
        _loc_log("_tg_api %s SKIPPED: no TELEGRAM_BOT_TOKEN" % method)
        return None
    url = "https://api.telegram.org/bot%s/%s" % (TELEGRAM_BOT_TOKEN, method)
    data = urllib.parse.urlencode(params).encode("utf-8") if params else None
    try:
        with urllib.request.urlopen(
                urllib.request.Request(url, data=data), timeout=timeout) as r:
            result = json.loads(r.read().decode("utf-8"))
            _loc_log("_tg_api %s OK chat_id=%s ok=%s" %
                     (method, (params or {}).get("chat_id"), result.get("ok")))
            return result
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8")[:300]
        except Exception:
            detail = ""
        _loc_log("_tg_api %s FAILED chat_id=%s HTTP %s: %s" %
                 (method, (params or {}).get("chat_id"), e.code, detail))
        return None
    except Exception as e:
        _loc_log("_tg_api %s FAILED chat_id=%s: %r" %
                 (method, (params or {}).get("chat_id"), e))
        return None

def telegram_send(text, chat_id=None):
    """Push a message to the paired chat (or a specific chat_id).
    Safe no-op if Telegram is not configured / not paired."""
    cid = chat_id if chat_id is not None else _tg_chat_id
    if not TELEGRAM_BOT_TOKEN or cid is None or not text:
        _loc_log("telegram_send SKIPPED token=%s cid=%s text_len=%s" %
                 (bool(TELEGRAM_BOT_TOKEN), cid, len(text or "")))
        return False
    t = text if len(text) <= 4000 else (text[:3990] + "...")
    res = _tg_api("sendMessage", {"chat_id": cid, "text": t})
    ok = bool(res and res.get("ok"))
    _loc_log("telegram_send cid=%s ok=%s" % (cid, ok))
    return ok

def _tg_download_photo(file_id):
    """Download a Telegram photo by file_id. Returns (bytes, mime) or None."""
    try:
        r = _tg_api("getFile", {"file_id": file_id}, timeout=20)
        if not r or not r.get("ok"):
            return None
        file_path = r["result"]["file_path"]
        url = ("https://api.telegram.org/file/bot%s/%s"
               % (TELEGRAM_BOT_TOKEN, file_path))
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = resp.read()
        ext = file_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                "png": "image/png", "webp": "image/webp"}.get(
                    ext, "image/jpeg")
        return data, mime
    except Exception as e:
        _loc_log("telegram photo download failed: %r" % e)
        return None


def _extract_workout_from_image(image_bytes, media_type, caption=""):
    """Claude vision: read a workout summary photo (Fitness app, Watch
    face, gym equipment display, etc.) and extract structured metrics.
    Returns a dict or None if unreadable/failed."""
    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        sys_p = (
            "You read a photo of a workout summary (iPhone Fitness app, "
            "Apple Watch face, gym equipment display, or similar) and "
            "extract structured data. Respond with ONLY a JSON object, no "
            "markdown fences, no prose, matching exactly this schema: "
            '{"readable": true|false, "screen": "workouts"|"day_summary", '
            '"workouts": [{"type": string|null, "dist_km": number|null, '
            '"dur_min": number|null, "hr_avg": number|null, '
            '"kcal": number|null}]}. '
            "\"screen\" is \"day_summary\" when the image shows a daily "
            "activity summary (rings, total steps, total distance, move "
            "goals) rather than individual workout sessions - in that "
            "case return an EMPTY workouts list and never invent a "
            "workout from daily totals. Otherwise \"screen\" is "
            "\"workouts\": list EVERY individual workout session visible "
            "in the image, one object per session, in the order shown. "
            "Convert any distance to kilometers. \"type\" is a short "
            "activity name (Running, Cycling, Swimming, Gym, Walking, "
            "etc), in the same language as any caption provided. Use "
            "null for any field not visible. Set \"readable\" to false "
            "ONLY if the image shows no fitness data at all."
        )
        user_text = "Extract the workout data from this image."
        if caption:
            user_text += " User's caption: " + caption
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=700,
            system=sys_p,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": media_type,
                                              "data": b64}},
                {"type": "text", "text": user_text},
            ]}])
        parts = [b.text for b in r.content
                 if getattr(b, "type", None) == "text"]
        raw = "".join(parts).strip().strip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:].strip()
        data = json.loads(raw)
        if not data.get("readable"):
            return None
        # v5.16r: normalize to the multi-workout shape. Old-style
        # single-object replies (schema drift) are wrapped into a
        # one-item list so every caller sees one shape.
        if not isinstance(data.get("workouts"), list):
            if any(data.get(k) is not None for k in
                   ("type", "dist_km", "dur_min", "hr_avg", "kcal")):
                data["workouts"] = [{k: data.get(k) for k in
                                     ("type", "dist_km", "dur_min",
                                      "hr_avg", "kcal")}]
            else:
                data["workouts"] = []
        if data.get("screen") == "day_summary":
            # never fabricate a workout from daily totals, even if
            # the model disobeyed and listed some
            data["workouts"] = []
        else:
            data["screen"] = "workouts"
            data["workouts"] = [w for w in data["workouts"]
                                if isinstance(w, dict)][:10]
        return data
    except Exception as e:
        _loc_log("workout image extraction failed: %r" % e)
        return None


def _is_geoloc_caption(caption):
    """v5.16k: detect a photo-geolocation-guess request from a Telegram
    caption (e.g. "where is this" / a Hebrew equivalent). Deliberately a
    substring/contains check, not an exact match like
    _weight_check_intercept - captions are short free text, not fixed
    commands."""
    if not caption or not isinstance(caption, str):
        return False
    low = caption.strip().lower()
    en_triggers = ("where is this", "where was this", "where's this",
                   "geolocate", "guess the location", "guess where",
                   "where in the world", "location guess",
                   "where was it taken", "where is it")
    if any(t in low for t in en_triggers):
        return True
    he_triggers = ("\u05d0\u05d9\u05e4\u05d4 \u05d6\u05d4",
                   "\u05d0\u05d9\u05e4\u05d4 \u05e6\u05d5\u05dc\u05dd",
                   "\u05e0\u05d7\u05e9 \u05de\u05d9\u05e7\u05d5\u05dd",
                   "\u05ea\u05e0\u05d7\u05e9 \u05d0\u05d9\u05e4\u05d4",
                   "\u05d0\u05d9\u05e4\u05d4 \u05d6\u05d5 \u05d4\u05ea\u05de\u05d5\u05e0\u05d4",
                   "\u05de\u05d9\u05e7\u05d5\u05dd \u05d1\u05ea\u05de\u05d5\u05e0\u05d4")
    if any(t in caption for t in he_triggers):
        return True
    return False


def _geoloc_display_fix(d):
    """v5.16p: display-name convention for this app - results labeled
    "Palestine"/"West Bank" (any variant, any of city/region/country)
    are shown as "Judea and Samaria"; Gaza-area results keep
    "Gaza Strip". Applied to EVERY geolocation guess (trained model
    and Claude vision) at the exit of the guess functions, so all
    consumers inherit it. Never raises."""
    try:
        if not isinstance(d, dict):
            return d
        gaza = any("gaza" in str(d.get(k) or "").lower()
                   for k in ("city", "region", "country"))
        repl = "Gaza Strip" if gaza else "Judea and Samaria"
        for k in ("city", "region", "country"):
            v = d.get(k)
            if not v:
                continue
            v = re.sub(r"west\s*bank", repl, str(v), flags=re.I)
            if re.search(r"palestin", v, re.I):
                v = repl
            d[k] = v
        if d.get("region") and d.get("region") == d.get("country"):
            d["region"] = None
        if d.get("city") and d.get("city") == d.get("country"):
            d["city"] = None
        return d
    except Exception:
        return d


_OSV5M_LOCAL_URL = "http://127.0.0.1:8850/predict"


def _osv5m_local_guess(image_bytes):
    """v5.16m: ask the local trained geolocation model (osv5m/baseline,
    ~5.1M real photos, CVPR 2024) for a guess, before falling back to
    Claude-vision zero-shot guessing. That model runs as a SEPARATE
    process (geoloc_baseline_server.py, own venv, port 8850, localhost
    only) - never embedded in this process, so a crash or "not running"
    there can never affect ACHILLES. Returns a dict shaped exactly like
    _geoguess_photo()'s own return value, or None if the local service
    is unreachable, errors, or times out - silent by design, since this
    is optional infrastructure and Claude vision always works without
    it."""
    try:
        req = urllib.request.Request(
            _OSV5M_LOCAL_URL,
            data=json.dumps({
                "image_b64": base64.b64encode(image_bytes).decode("ascii"),
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=6) as r:
            result = json.loads(r.read())
    except Exception as e:
        _loc_log("osv5m local model unavailable, falling back to "
                 "Claude vision: %r" % e)
        return None
    if not result.get("ok"):
        return None
    lat, lon = result.get("lat"), result.get("lon")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        return None
    return _geoloc_display_fix({
        "readable": True,
        "country": result.get("country"),
        "region": result.get("region"),
        "city": result.get("city"),
        "lat": lat,
        "lon": lon,
        "confidence": "medium",
        "reasoning": (
            "\u05de\u05d5\u05d3\u05dc \u05de\u05d0\u05d5\u05de\u05df \u05e2\u05dc 5.1 \u05de\u05d9\u05dc\u05d9\u05d5\u05df \u05ea\u05de\u05d5\u05e0\u05d5\u05ea \u05d0\u05de\u05d9\u05ea\u05d9\u05d5\u05ea (OSV5M) \u2014 \u05d3\u05d9\u05d5\u05e7 \u05de\u05de\u05d5\u05e6\u05e2: \u05db-68% \u05d1\u05e8\u05de\u05ea \u05de\u05d3\u05d9\u05e0\u05d4, \u05db-39% \u05d1\u05e8\u05de\u05ea \u05d0\u05d6\u05d5\u05e8"
        ),
        "source": "osv5m",
    })


def _geoguess_photo(image_bytes, media_type, caption="", use_local=True):
    """Guess where a photo was taken. v5.16m: tries the local trained
    model first (osv5m/baseline - see geoloc_baseline_server.py);
    only falls back to Claude-vision zero-shot guessing (the original
    v5.16k behavior, unchanged below) if that service isn't running
    or fails. Never EXIF or file metadata, which is never read either
    way. Returns a dict or None if neither method can make any
    reasonable guess."""
    # v5.16v: the local osv5m model is NO LONGER in the decision
    # path. Measured on 189 GPS-tagged photos it put 63-73% of
    # them in the wrong country (median error 1135 km in Israel),
    # and two-stage fusion returned Claude's own answer anyway
    # (23.6 km vs 23.6 km in Israel, 2.2 vs 2.3 abroad). Skipping
    # it costs nothing in accuracy and saves 2 of every 3 API
    # calls. It stays installed and still shows in compare mode,
    # so re-enabling is a one-line change once it earns its place
    # (Israeli fine-tune / retrieval).
    local = None
    if local is not None:
        # v5.16t FUSION: never return the raw model guess directly -
        # let Claude vision judge it against the pixels first. Any
        # fusion failure - API down, parse error - falls back to the
        # raw model guess, i.e. exactly the old v5.16m behavior.
        fused = _geoloc_fusion_guess(image_bytes, media_type, caption,
                                     local)
        if fused is not None:
            return fused
        return local
    try:
        b64 = base64.b64encode(image_bytes).decode("ascii")
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        # v5.16x: structured-evidence prompt. The model now works
        # through an explicit evidence scan and competing candidates
        # in a scratchpad BEFORE committing, then ends with one
        # marked FINAL_JSON line (parser below). Motivated by the
        # Lloret de Mar blind test: right coastline family, wrong -
        # but more famous - riviera. Output schema is unchanged.
        sys_p = (
            "You are an expert visual geolocator. You determine where "
            "a photo was taken using ONLY what is visible in the frame "
            "- never EXIF or file metadata, which you cannot see "
            "anyway.\n\n"
            "METHOD - work through these steps in order, writing your "
            "observations as you go. This text is a scratchpad; only "
            "the final line is parsed.\n"
            "1. EVIDENCE SCAN - note what you can actually see in each "
            "family: vegetation and climate (species, dryness, "
            "season); architecture (roof shapes and materials, wall "
            "finishes, shutters, balconies, age, density); text and "
            "scripts (read every legible sign, even partial - the "
            "script alone narrows the region); road furniture "
            "(marking colors, curb style, guardrails, bollards, "
            "signposts); driving side and vehicles (models, taxis, "
            "buses, plate shape and color); terrain and coastline "
            "morphology (rock type, slope, water color); sun and "
            "shadows (rough latitude); people and dress.\n"
            "2. CANDIDATES - name 2-3 specific candidate regions that "
            "fit, each with its strongest point FOR and AGAINST. "
            "Include at least one LESS FAMOUS look-alike: tourist "
            "coasts, alpine towns and beach resorts are routinely "
            "mistaken for their most famous example - a Costa Brava "
            "cove is not Saint-Tropez, a Black Sea resort is not the "
            "Cote d Azur. Famousness is not evidence.\n"
            "3. DISCRIMINATE - pick the single detail that best "
            "separates your candidates and decide from it. If nothing "
            "separates them, take the strongest total evidence and "
            "lower your confidence.\n"
            "4. COMMIT - one final location. Never output a compromise "
            "point between candidates - it lands in the sea or in a "
            "random field. lat/lon must be INSIDE your chosen "
            "locality.\n\n"
            "CONFIDENCE calibration: high = you would bet the true "
            "spot is within 25 km; medium = within 150 km; low = "
            "confident only at country level or less. Honest low "
            "confidence is worth more than a lucky-looking guess.\n\n"
            "End your reply with exactly one line:\n"
            "FINAL_JSON: {\"readable\": true|false, \"country\": "
            "string|null, \"region\": string|null, \"city\": "
            "string|null, \"lat\": number|null, \"lon\": "
            "number|null, \"confidence\": \"high\"|\"medium\"|"
            "\"low\", \"reasoning\": string}\n"
            "\"reasoning\" is 1-2 short sentences naming the "
            "decisive visual cues, in the same language as any "
            "caption provided (a Hebrew caption gets Hebrew "
            "reasoning). Always give your best guess even at low "
            "confidence - set \"readable\" false ONLY if the image "
            "has no usable visual signal at all (e.g. an extreme "
            "close-up with no context)."
        )
        user_text = "Where was this photo taken?"
        if caption:
            user_text += " User's caption: " + caption
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=900,
            system=sys_p,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": media_type,
                                              "data": b64}},
                {"type": "text", "text": user_text},
            ]}])
        parts = [b.text for b in r.content
                 if getattr(b, "type", None) == "text"]
        raw = "".join(parts).strip()
        # v5.16x: the reply is now scratchpad + one marked line.
        # Parse from the marker; if the model ever drops the marker,
        # fall back to the old whole-reply-is-JSON parse so format
        # drift degrades gracefully instead of failing.
        m = raw.rfind("FINAL_JSON:")
        if m >= 0:
            data = json.loads(
                raw[m + len("FINAL_JSON:"):].strip().strip("`"))
        else:
            fb = raw.strip("`")
            if fb[:4].lower() == "json":
                fb = fb[4:].strip()
            data = json.loads(fb)
        if not data.get("readable"):
            return None
        return _geoloc_display_fix(data)
    except Exception as e:
        _loc_log("geoguess image extraction failed: %r" % e)
        return None


def _geoloc_fusion_guess(image_bytes, media_type, caption, candidate,
                         blind=None):
    """v5.16u FUSION (two-stage, anchor-free): stage 1 asks Claude to
    geolocate the photo BLIND - it never sees the local model's
    guess, so it cannot be anchored by a wrong candidate. Stage 2
    shows Claude its own committed answer alongside the model's
    candidate and asks it to reconcile, defaulting to KEEP its blind
    answer unless the candidate clearly helps. This replaces the
    v5.16t single-call design, which leaked the candidate into the
    only reasoning step and measurably dragged good answers toward
    bad candidates. Callers may pass an already-computed blind guess
    (compare mode does) to avoid a duplicate API call. Returns a dict
    with source "fusion" and fusion_action "kept"/"refined"/
    "overridden", or None on failure - callers then fall back to the
    raw candidate, so fusion can only ever match or beat v5.16m."""
    try:
        cand_lat, cand_lon = candidate.get("lat"), candidate.get("lon")
        if not isinstance(cand_lat, (int, float)) or \
                not isinstance(cand_lon, (int, float)):
            return None
        cand_place = ", ".join(
            [p for p in (candidate.get("city"), candidate.get("region"),
                         candidate.get("country")) if p]) or "unnamed area"
        if blind is None:
            blind = _geoguess_photo(image_bytes, media_type, caption,
                                    use_local=False)
        if not blind or not blind.get("readable"):
            return None
        b_lat, b_lon = blind.get("lat"), blind.get("lon")
        if not isinstance(b_lat, (int, float)) or \
                not isinstance(b_lon, (int, float)):
            return None
        b_place = ", ".join(
            [p for p in (blind.get("city"), blind.get("region"),
                         blind.get("country")) if p]) or "unnamed area"
        b64 = base64.b64encode(image_bytes).decode("ascii")
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        schema = (
            '{"readable": true, "country": string|null, "region": '
            'string|null, "city": string|null, "lat": number|null, '
            '"lon": number|null, "confidence": "high"|"medium"|"low", '
            '"fusion_action": "kept"|"refined"|"overridden", '
            '"reasoning": string}'
        )
        sys_p = (
            "You already geolocated a photo from visual clues alone. "
            "Now you are shown TWO location estimates for the SAME "
            "photo: (A) your own independent estimate, and (B) a "
            "candidate from a separate locally-trained model. That "
            "model places roughly 1 photo in 3 in the wrong country "
            "entirely, but when its country is right it can be more "
            "precise than unaided guessing. Decide the final answer by "
            "these rules, in order. (1) DEFAULT to your own estimate "
            "(A). (2) Only if B is in the same country and roughly the "
            "same region as A, AND you were not confident about the "
            "exact spot, may you adopt B's coordinates as a more "
            "precise fix - set action \"refined\". (3) If A and B "
            "disagree on country or region, KEEP A and set action "
            "\"kept\" - do NOT move toward B. (4) Set action "
            "\"overridden\" only if, looking again, you are now "
            "convinced B is right and A was your own mistake - not "
            "merely because B exists. ISRAEL PLATE CHECK: if the photo "
            "shows a vehicle with a clearly Israeli plate - reflective "
            "YELLOW front and rear, black digits, a narrow BLUE stripe "
            "on the left with the Israeli flag and \"IL\" - treat "
            "country as Israel with high confidence and reject any "
            "candidate placing it elsewhere (neighbouring countries "
            "use white plates; Palestinian-Authority plates are green "
            "and white). This is a neutral visual check on a physical "
            "object. Respond with ONLY a JSON object, no markdown "
            "fences, no prose, matching exactly this schema: " + schema +
            ". \"reasoning\" is 1-2 short sentences in the same "
            "language as any caption provided, naming why you kept, "
            "refined, or overrode."
        )
        user_text = (
            "Estimate A (yours): lat %.5f, lon %.5f - %s.\n"
            "Candidate B (local model): lat %.5f, lon %.5f - %s.\n"
            "Give the final reconciled answer." % (
                b_lat, b_lon, b_place, cand_lat, cand_lon, cand_place))
        if caption:
            user_text += " User's caption: " + caption
        r = client.messages.create(
            model="claude-sonnet-5", max_tokens=400,
            system=sys_p,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                              "media_type": media_type,
                                              "data": b64}},
                {"type": "text", "text": user_text},
            ]}])
        parts = [b.text for b in r.content
                 if getattr(b, "type", None) == "text"]
        raw = "".join(parts).strip().strip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:].strip()
        result = json.loads(raw)
        if not result.get("readable"):
            blind["source"] = "fusion"
            blind["fusion_action"] = "kept"
            return _geoloc_display_fix(blind)
        if result.get("fusion_action") not in (
                "kept", "refined", "overridden"):
            result["fusion_action"] = "kept"
        if not isinstance(result.get("lat"), (int, float)) or \
                not isinstance(result.get("lon"), (int, float)):
            result["lat"], result["lon"] = b_lat, b_lon
        result["source"] = "fusion"
        return _geoloc_display_fix(result)
    except Exception as e:
        _loc_log("geoloc fusion failed, falling back to raw "
                 "candidate: %r" % e)
        return None


def _tg_geoloc_confirmation_text(data, lang="he"):
    """v5.16k: format a _geoguess_photo() result for a Telegram reply."""
    loc_parts = [p for p in (data.get("city"), data.get("region"),
                              data.get("country")) if p]
    if loc_parts:
        loc = ", ".join(loc_parts)
    elif lang == "he":
        loc = ("\u05dc\u05d0 \u05d4\u05e6\u05dc\u05d7\u05ea\u05d9 \u05dc\u05d0\u05de\u05d5\u05d3 "
               "\u05de\u05d9\u05e7\u05d5\u05dd \u05de\u05d3\u05d5\u05d9\u05e7")
    else:
        loc = "couldn't pin down a specific place"
    conf_raw = (data.get("confidence") or "").lower()
    if lang == "he":
        conf_map = {"high": "\u05d2\u05d1\u05d5\u05d4",
                    "medium": "\u05d1\u05d9\u05e0\u05d5\u05e0\u05d9",
                    "low": "\u05e0\u05de\u05d5\u05da"}
    else:
        conf_map = {"high": "high", "medium": "medium", "low": "low"}
    conf = conf_map.get(conf_raw, conf_raw or "?")
    lat, lon = data.get("lat"), data.get("lon")
    coord = ""
    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
        coord = " (%.4f, %.4f)" % (lat, lon)
    reasoning = (data.get("reasoning") or "").strip()
    if data.get("source") == "fusion":
        pin = "\U0001F500"  # shuffle: fused model-plus-vision path
        tag = ("\u05de\u05e9\u05d5\u05dc\u05d1 - \u05de\u05d5\u05d3\u05dc + \u05e8\u05d0\u05d9\u05d9\u05d4"
               if lang == "he" else "fused - model + vision")
        head = "%s %s%s \u2014 %s" % (pin, loc, coord, tag)
    elif data.get("source") == "osv5m":
        pin = "\U0001F3AF"  # target: marks the trained-model path,
                            # distinct from the Claude-vision pin below
        tag = ("\u05de\u05d5\u05d3\u05dc \u05de\u05d0\u05d5\u05de\u05df" if lang == "he"
               else "trained model")
        head = "%s %s%s \u2014 %s" % (pin, loc, coord, tag)
    else:
        pin = "\U0001F4CD"
        if lang == "he":
            head = "%s %s%s \u2014 \u05d1\u05d9\u05d8\u05d7\u05d5\u05df %s" % (
                pin, loc, coord, conf)
        else:
            head = "%s %s%s \u2014 confidence: %s" % (pin, loc, coord, conf)
    return head + ("\n" + reasoning if reasoning else "")


def _training_log_add_workout_from_extract(data, src="photo", when=None):
    """Write an extracted workout into training_log.json - same schema
    and caps as the /training_workout HTTP endpoint. Returns the written
    entry dict, or None on failure. v5.16q: optional when= (a
    pre-validated YYYY-MM-DD string) logs the workout under that date
    instead of today - for uploads the owner forgot to send on the
    day itself."""
    try:
        p = Path(__file__).resolve().parent / "training_log.json"
        today = datetime.date.today().isoformat()
        entry_date = when or today
        with _training_lock:
            try:
                log = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                log = {}
            log.setdefault("weight_target_min_kg", 68)
            workouts = log.setdefault("workouts", [])
            entry = {"d": entry_date, "t": (data.get("type") or "Workout")[:80],
                     "src": src}
            for qk, jk in (("dist_km", "km"), ("dur_min", "min"),
                           ("hr_avg", "hr"), ("kcal", "kcal")):
                v = data.get(qk)
                if isinstance(v, (int, float)) and v > 0:
                    entry[jk] = round(float(v), 1)
            workouts.append(entry)
            workouts.sort(key=lambda w: w.get("d", ""))
            del workouts[:-120]
            if entry["d"] >= (log.get("last_workout_date") or ""):
                log["last_workout_type"] = entry["t"]
                log["last_workout_date"] = entry["d"]
            cut = (datetime.date.today()
                   - datetime.timedelta(days=6)).isoformat()
            log["weekly_workouts"] = sum(
                1 for w in workouts if (w.get("d") or "") >= cut)
            p.write_text(json.dumps(log, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return entry
    except Exception as e:
        _loc_log("training log write (photo) failed: %r" % e)
        return None


def _tg_photo_confirmation_text(entry):
    parts = [entry.get("t", "Workout")]
    if "min" in entry: parts.append(str(entry["min"]) + " \u05d3\u05e7\u05d5\u05ea")
    if "km" in entry: parts.append(str(entry["km"]) + " km")
    if "hr" in entry: parts.append("\u05d3\u05d5\u05e4\u05e7 \u05de\u05de\u05d5\u05e6\u05e2 " + str(entry["hr"]))
    if "kcal" in entry: parts.append(str(entry["kcal"]) + " \u05e7\u05dc\u05d5\u05e8\u05d9\u05d5\u05ea")
    return "\u2705 \u05e0\u05e8\u05e9\u05dd: " + " \u00b7 ".join(parts)


def _tg_load_chat():
    global _tg_chat_id
    try:
        if os.path.exists(_TG_CHAT_FILE):
            with open(_TG_CHAT_FILE, "r", encoding="utf-8") as f:
                _tg_chat_id = json.load(f).get("chat_id")
    except Exception:
        _tg_chat_id = None

def _tg_save_chat(cid):
    global _tg_chat_id
    _tg_chat_id = cid
    try:
        with open(_TG_CHAT_FILE, "w", encoding="utf-8") as f:
            json.dump({"chat_id": cid}, f)
    except Exception:
        pass


class App:
    # v4.52: 'state' is a property so EVERY existing "self.state = ..."
    # assignment in the file also mirrors into _achilles_state, which the
    # :7778 proxy serves at GET /state. The Achilles black-hole screen polls
    # it to animate idle/listening/thinking/speaking. Zero call-site changes.
    @property
    def state(self):
        return getattr(self, "_state_val", "loading")

    @state.setter
    def state(self, v):
        self._state_val = v
        try:
            _achilles_state["state"] = v
            _achilles_state["ts"] = time.time()
        except Exception:
            pass

    def __init__(self, root):
        global APP
        APP = self
        self.root = root
        self.state = "loading"
        self.wake_on = False
        self.busy = False
        self.stop = False
        self.model = None
        self.wake_model = None
        self.memory = ""
        self.outbox = []
        self._lock = threading.Lock()
        self._hold = ""
        self._hold_until = 0.0
        self.panel = None        # the big search window (created on demand)
        self.panel_busy = False
        # For the function keys: remember the last full exchange (for F2 = save)
        # and the last spoken reply (for F3 = repeat).
        self._last_user = ""
        self._last_reply = ""
        self._preroll = None   # pre-roll audio captured at wake time
        # v4.57: black-hole face layers, pre-rendered in the background
        # so launch is never blocked. Until ready, the old orb shows.
        self._bhL = None
        self._bh_ph = 0.0
        self._bh_star_a = 0.0
        if HAVE_PIL:
            threading.Thread(target=self._bh_build_async, daemon=True).start()

        sw = root.winfo_screenwidth()
        self.EW, self.EH = 400, 470
        self.ex = sw - self.EW - 30
        self.ey = 60

        self.mode = "hidden"      # hidden | expanded
        self.req_mode = "hidden"
        self.typing = False       # typing box visible?
        self.req_typing = False

        root.title("ACHILLES")
        # v4.82: RE-TESTING overrideredirect(True) for the borderless floating-orb
        # look. v4.79 removed it because it was invisible - but at the time the
        # window was being dynamically parked off-screen and un-parked on every
        # wake (the actual trigger for the Windows/DWM compositing failure).
        # Since v4.81 the window is created once and never moves again, so that
        # specific dynamic no longer exists. This is a deliberate, logged
        # experiment, not an assumption - orb_diag.log will show which branch ran.
        root.overrideredirect(True)
        # v4.79: taskbar-anchor Toplevel hack REMOVED. It existed only to give
        # a borderless overrideredirect window a taskbar presence; a normal
        # bordered window (see above) already gets one for free, and this extra
        # off-screen Toplevel was also a plausible source of z-order/focus
        # interference with the main window's painting.
        try:
            _ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "achilles.ico")
            if os.path.isfile(_ico):
                try:
                    root.iconbitmap(default=_ico)
                except Exception:
                    pass
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(u"horn.achilles.jarvis")
        except Exception as _e:
            print("[diag] taskbar icon setup skipped:", repr(_e))
        def _on_anchor_close():
            try:
                self.stop = True
            except Exception:
                pass
            try:
                root.destroy()
            except Exception:
                pass
        root.protocol("WM_DELETE_WINDOW", _on_anchor_close)
        # v4.76: file-based orb diagnostics, defined here (before first use).
        # pythonw has no console, so plain print() of errors in the render/show
        # path is invisible - this makes them visible in orb_diag.log next to jarvis.py.
        def _orb_log(msg):
            try:
                _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orb_diag.log")
                with open(_p, "a", encoding="utf-8") as _f:
                    _f.write("[%s] %s\n" % (datetime.datetime.now().strftime("%H:%M:%S"), msg))
            except Exception:
                pass
        self._orb_log = _orb_log
        root.attributes("-topmost", True)
        # v4.83: RE-ENABLING transparency. v4.78 disabled it as a diagnostic
        # step when NOTHING was visible; v4.79-v4.82 since showed the real
        # trigger was the old dynamic off-screen park/un-park cycle (gone since
        # v4.81), not transparency itself. With overrideredirect now confirmed
        # working on a static window (v4.82 screenshot), transparency is the
        # remaining piece for the true floating-orb look (no visible box).
        try:
            root.attributes("-transparentcolor", KEY)
            self._orb_log("v4.83 transparentcolor RE-ENABLED key=%s" % KEY)
        except Exception as _e:
            self._orb_log("v4.83 transparentcolor FAILED: %r" % (_e,))
        root.config(bg=KEY)
        self._geo_on  = "%dx%d+%d+%d" % (self.EW, self.EH, self.ex, self.ey)
        self._geo_off = "%dx%d+-32000+-32000" % (self.EW, self.EH)
        # v4.75: park off-screen instead of withdraw(). On Windows an
        # overrideredirect(True) window that is withdraw()n often refuses
        # to re-map via deiconify(), so the orb never reappears. Keeping it
        # always-mapped but parked off-screen avoids deiconify entirely.
        # v4.81: STOP HIDING THE ORB. Five straight patches (v4.75-v4.80) tried to
        # fix the hide/show transition itself and each uncovered a new failure mode
        # in it. The window now stays on-screen, in place, from boot onward -
        # permanently. This is a deliberate simplification, not a workaround: if
        # showing-after-hiding is what keeps breaking, the fix is to never hide.
        # The orb still visually reflects idle/listening/speaking/thinking via its
        # own animation state - it just never leaves the screen.
        root.geometry(self._geo_on)
        self._orb_log("BOOT sw=%d EW=%d EH=%d ex=%d ey=%d geo_on=%r (always-on-screen mode)"
                       % (sw, self.EW, self.EH, self.ex, self.ey, self._geo_on))
        # v4.91: write the EXACT running file path + PID somewhere impossible
        # to confuse with any log inside the project folder - answers "which
        # jarvis.py is actually executing" with certainty, no ambiguity.
        try:
            _this_file = os.path.abspath(__file__)
            _ver_line = "(unknown)"
            try:
                with open(_this_file, encoding="utf-8") as _vf:
                    _lines = _vf.readlines()
                    if len(_lines) > 3:
                        _ver_line = _lines[3].strip()
            except Exception:
                pass
            _wf = os.path.join(os.path.dirname(_this_file), "which_jarvis_is_running.txt")
            _content = ("Running file: %s\nPID: %d\nStarted: %s\nVersion line: %s\n"
                        % (_this_file, os.getpid(),
                           datetime.datetime.now().isoformat(), _ver_line))
            with open(_wf, "w", encoding="utf-8") as _f:
                _f.write(_content)
        except Exception as _e:
            self._orb_log("which_jarvis_is_running.txt write FAILED: %r" % (_e,))
        def _snapshot():
            try:
                self._orb_log("SNAPSHOT viewable=%s state=%s x=%d y=%d w=%d h=%d cv=%dx%d pil=%s mode=%s req_mode=%s"
                              % (root.winfo_viewable(), root.state(), root.winfo_x(), root.winfo_y(),
                                 root.winfo_width(), root.winfo_height(),
                                 self.cv.winfo_width(), self.cv.winfo_height(), self.use_pil,
                                 self.mode, self.req_mode))
            except Exception as _e:
                self._orb_log("SNAPSHOT FAILED: %r" % (_e,))
        root.after(800, _snapshot)

        self.SS = 3  # supersample factor for Pillow anti-aliasing (higher = smoother but heavier)
        self.use_pil = HAVE_PIL

        self.cv = tk.Canvas(root, bg=KEY, highlightthickness=0, bd=0)
        self.cv.pack(fill=tk.BOTH, expand=True)
        # v4.83: border rectangle REMOVED - with transparency back on, a solid
        # rectangle outline is exactly what makes it look like "a window" instead
        # of a floating orb. Title text kept, floating with no box behind it.
        try:
            self.cv.create_text(self.EW // 2, 16, text="A C H I L L E S",
                                fill="#f0a050", font=("Segoe UI", 10, "bold"))
        except Exception as _e:
            self._orb_log("static chrome FAILED: %r" % (_e,))

        self.entry = tk.Entry(root, bg="#161b22", fg="#e6edf3",
                              insertbackground="#58a6ff", relief=tk.FLAT,
                              font=("Segoe UI", 11))
        self.entry.bind("<Return>", self._send_typed)

        # particles
        self.N = 360
        self.pts = []
        ga = 2.399963
        for i in range(self.N):
            y = 1 - (i / (self.N - 1)) * 2
            rr = (1 - y * y) ** 0.5
            th = i * ga
            self.pts.append((np.cos(th) * rr, y, np.sin(th) * rr))

        # canvas image (Pillow path) AND oval items (fallback) — always create
        # both so the fallback renderer can never crash on missing attributes.
        self.img_id = self.cv.create_image(0, 0, anchor="nw")
        self._tkimg = None
        self.items = [self.cv.create_oval(0, 0, 0, 0, outline="", fill="")
                      for _ in range(self.N)]
        self.ripple_id = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
        self.ring_id = self.cv.create_oval(0, 0, 0, 0, outline="", width=2)
        self.status_id = self.cv.create_text(0, 0, text="", fill="#9aa7b4",
                                              font=("Segoe UI", 9))

        self.ang = 0.0
        self.zoom = 1.0
        self.sel = 0
        self.prev = "loading"
        self.ripple = 0.0
        self.ripple_on = False
        self._drag = (0, 0)
        self._moved = False

        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Talk", command=lambda: self.talk(True))
        self.menu.add_command(label="Type", command=self._open_typing)
        self.menu.add_command(label="Search window", command=lambda: self.ui(self.open_panel))
        self.menu.add_command(label="Toggle Wake Word", command=self.toggle_wake)
        self.menu.add_separator()
        self.menu.add_command(label="Quit JARVIS", command=self.quit)

        self.cv.bind("<Button-3>", self._show_menu)
        # v4.61: double-click = fullscreen portal (listening stays on wake word)
        self.cv.bind("<Double-Button-1>", lambda e: threading.Thread(
            target=open_portal, daemon=True).start())
        self.cv.bind("<Button-1>", self._drag_start)
        self.cv.bind("<B1-Motion>", self._drag_move)
        root.bind_all("<Escape>", lambda e: self._hide())
        # Function keys. When the fullscreen search window is open these drive
        # IT (F1 type, F2 speak, F3 image, F5 stop talking); otherwise they keep
        # their normal main-window jobs (F1 typing box, F2 save, F3 repeat).
        root.bind_all("<F1>", lambda e: self._key_f1())
        root.bind_all("<F2>", lambda e: self._key_f2())
        root.bind_all("<F3>", lambda e: self._key_f3())
        root.bind_all("<F5>", lambda e: self._key_f5())

        threading.Thread(target=self._boot, daemon=True).start()
        threading.Thread(target=self._signal_watch, daemon=True).start()
        threading.Thread(target=self._telegram_loop, daemon=True).start()
        self.animate()

    # ---- thread-safe UI helper ----
    def ui(self, fn):
        """Run a callback on the main (tkinter) thread. Global hotkeys (the
        'keyboard' library) fire on their OWN thread, and tkinter is not
        thread-safe, so calling UI code directly from there crashes. We marshal
        the callback onto the main thread with after(). This method was being
        called by the F1/F2/F3 hotkeys but never existed -> that was the
        'App object has no attribute ui' crash. Now it exists."""
        try:
            self.root.after(0, fn)
        except Exception:
            pass

    # ---- search panel (big window: type / speak / pick image + links) ----
    # --- search-window theme (dark, luxury, molten-amber accent) ---
    _UI = {
        "bg": "#0a0c10", "panel": "#11151b", "input": "#161b22",
        "hover": "#1f2733", "accent": "#ff8c42", "accent2": "#ffa55f",
        "ink": "#1a1205", "text": "#e6edf3", "muted": "#8b97a5",
        "link": "#7cc4ff", "divider": "#222a35",
    }

    def _hoverable(self, widget, normal, hover):
        """Make a button gently change colour when the mouse is over it."""
        widget.bind("<Enter>", lambda e: widget.config(bg=hover))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal))

    # ----- canvas drawing helpers for the cinematic search window -----
    def _round_rect(self, cv, x1, y1, x2, y2, r=14, **kw):
        """Draw a rounded rectangle on a canvas; returns the polygon item id."""
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return cv.create_polygon(pts, smooth=True, **kw)

    def _make_orb_image(self, size=240):
        """Render the molten-amber glowing orb as an RGBA Pillow image."""
        cx = cy = size / 2.0
        R = size * 0.30
        glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        for rad, a in [(R * 2.7, 28), (R * 2.0, 44), (R * 1.5, 70), (R * 1.15, 110)]:
            gd.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(255, 120, 40, a))
        glow = glow.filter(ImageFilter.GaussianBlur(size * 0.045))
        core = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        cd = ImageDraw.Draw(core)
        steps = 30
        for i in range(steps):
            t = i / (steps - 1)
            rr = R * (1 - t)
            col = (255, int(120 + 125 * t), int(40 + 155 * t), 255)
            cd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=col)
        core = core.filter(ImageFilter.GaussianBlur(size * 0.012))
        return Image.alpha_composite(glow, core)

    def _make_backdrop_image(self, w, h):
        """Render the dark vertical gradient + warm top glow as an RGB image."""
        top, bottom = (16, 16, 22), (6, 7, 10)
        grad = Image.new("RGB", (w, h))
        gd = ImageDraw.Draw(grad)
        for y in range(h):
            t = y / max(1, h - 1)
            gd.line([(0, y), (w, y)],
                    fill=(int(top[0] * (1 - t) + bottom[0] * t),
                          int(top[1] * (1 - t) + bottom[1] * t),
                          int(top[2] * (1 - t) + bottom[2] * t)))
        glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        gld = ImageDraw.Draw(glow)
        gx, gy = w // 2, int(h * 0.15)
        for rad, a in [(360, 16), (260, 24), (170, 32), (90, 40)]:
            gld.ellipse([gx - rad, gy - rad, gx + rad, gy + rad], fill=(255, 110, 40, a))
        glow = glow.filter(ImageFilter.GaussianBlur(60))
        return Image.alpha_composite(grad.convert("RGBA"), glow).convert("RGB")

    def _cbutton(self, cv, x1, y1, x2, y2, label, cmd, primary=False):
        """Draw a rounded, hoverable button directly on the canvas."""
        c = self._UI
        base = c["accent"] if primary else c["input"]
        hov = c["accent2"] if primary else c["hover"]
        fg = c["ink"] if primary else c["text"]
        outline = "" if primary else c["divider"]
        tag = "cbtn%d" % self._cbtn_n
        self._cbtn_n += 1
        rid = self._round_rect(cv, x1, y1, x2, y2, r=14,
                               fill=base, outline=outline, tags=(tag,))
        cv.create_text((x1 + x2) // 2, (y1 + y2) // 2, text=label, fill=fg,
                       font=("Segoe UI", 11, "bold"), tags=(tag,))
        cv.tag_bind(tag, "<Enter>",
                    lambda e, i=rid: (cv.itemconfig(i, fill=hov), cv.config(cursor="hand2")))
        cv.tag_bind(tag, "<Leave>",
                    lambda e, i=rid: (cv.itemconfig(i, fill=base), cv.config(cursor="")))
        cv.tag_bind(tag, "<Button-1>", lambda e: cmd())

    def _render_orb_frame(self, size, ang):
        """Render ONE frame of the real particle orb (round glow, no square),
        reusing the same points as the main orb. Returns a PIL RGBA image."""
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        R = size * 0.30
        focal = R * 2.6
        cx = cy = size / 2.0
        # warm ROUND backing disc (this is why there is no square halo)
        disc = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        dd = ImageDraw.Draw(disc)
        dr_r = R * 1.55
        steps = 22
        for k in range(steps):
            t = k / (steps - 1.0)
            rr = dr_r * (1.0 - t)
            dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                       fill=(int(40 + 90 * t), int(15 + 35 * t), int(8 + 12 * t), 255))
        try:
            disc = disc.filter(ImageFilter.GaussianBlur(size * 0.02))
        except Exception:
            pass
        img.alpha_composite(disc)
        dr = ImageDraw.Draw(img)
        sa, ca = np.sin(ang), np.cos(ang)
        lo, hi = RAMPS["idle"]
        pts = self.pts[::2]  # subsample for speed (weak CPU)
        order = sorted(((-p[0] * sa + p[2] * ca), idx) for idx, p in enumerate(pts))
        for z, i in order:
            px0, py0, pz0 = pts[i]
            x = px0 * ca + pz0 * sa
            sc = focal / (focal + z * R)
            X = cx + x * R * sc
            Y = cy + py0 * R * sc
            depth = (z + 1) / 2.0
            rad = 1.1 + 2.0 * depth
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            a = int(70 + 170 * depth)
            gr = rad * 2.4
            dr.ellipse([X - gr, Y - gr, X + gr, Y + gr],
                       fill=(_clamp(r), _clamp(g), _clamp(b), int(a * 0.28)))
            dr.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                       fill=(_clamp(r), _clamp(g), _clamp(b), _clamp(a)))
        try:
            img = img.filter(ImageFilter.GaussianBlur(0.5))
        except Exception:
            pass
        return img

    def _panel_close(self):
        """Close the fullscreen search window (Esc). Also cuts off any
        in-progress JARVIS speech so the user isn't talked at after closing."""
        self._panel_speaking = False
        try:
            stop_audio()
        except Exception:
            pass
        try:
            if self.panel is not None:
                self.panel.destroy()
        except Exception:
            pass

    def _panel_show_typing(self):
        """Reveal the (normally hidden) typing field and focus it."""
        try:
            self.panel.focus_force()
            self._pulse_cv.itemconfig(self._entry_win, state="normal")
            self.panel_entry.focus_set()
        except Exception:
            pass

    def _panel_stop_speaking(self):
        """F5: cut JARVIS off mid-sentence in the search window."""
        self._panel_speaking = False
        stop_audio()

    def _panel_is_open(self):
        """True when the fullscreen search window is up on screen."""
        try:
            return (self.panel is not None
                    and tk.Toplevel.winfo_exists(self.panel)
                    and bool(self.panel.winfo_ismapped()))
        except Exception:
            return False

    # F-key dispatchers: when the search window is open the keys drive IT;
    # otherwise they keep their normal main-window jobs.
    def _key_f1(self):
        self._panel_show_typing() if self._panel_is_open() else self._open_typing()

    def _key_f2(self):
        self._panel_speak() if self._panel_is_open() else self._save_last_exchange()

    def _key_f3(self):
        self._panel_pick_image() if self._panel_is_open() else self._repeat_last()

    def _key_f5(self):
        # v4.3: F5 stops speech globally, not just in the search window.
        if self._panel_is_open():
            self._panel_stop_speaking()
        else:
            stop_audio()

    def _panel_pulse_tick(self):
        """Spin the orb every frame; show the amber pulse line ONLY while
        JARVIS is speaking."""
        if not (self.panel and tk.Toplevel.winfo_exists(self.panel)):
            return
        try:
            cv = self._pulse_cv
            if getattr(self, "_hud_time", None) is not None:
                now = datetime.datetime.now()
                cv.itemconfig(self._hud_time, text=now.strftime("%H:%M:%S"))
                cv.itemconfig(self._hud_date, text=now.strftime("%A, %d %B %Y"))
            if getattr(self, "_orb_frames", None):
                self._orb_idx = (self._orb_idx + 1) % len(self._orb_frames)
                cv.itemconfig(self._orb_item, image=self._orb_frames[self._orb_idx])
            if getattr(self, "_panel_speaking", False):
                cv.itemconfig(self._pulse_item, state="normal")
                cv.itemconfig(self._pulse_glow, state="normal")
                x0, x1, y = self._pulse_x0, self._pulse_x1, self._pulse_y
                ph = self._pulse_phase
                n = 70
                pts = []
                for i in range(n + 1):
                    t = i / n
                    env = np.sin(np.pi * t)
                    yv = y + 16.0 * env * (0.7 * np.sin(8 * t * np.pi + ph)
                                           + 0.3 * np.sin(15 * t * np.pi - ph * 1.7))
                    pts += [x0 + (x1 - x0) * t, yv]
                cv.coords(self._pulse_item, *pts)
                cv.coords(self._pulse_glow, *pts)
                self._pulse_phase += 0.5
            else:
                cv.itemconfig(self._pulse_item, state="hidden")
                cv.itemconfig(self._pulse_glow, state="hidden")
        except Exception:
            pass
        self.panel.after(60, self._panel_pulse_tick)

    def open_panel(self):
        """Create (or re-show) the fullscreen cinematic search window."""
        if self.panel is not None and tk.Toplevel.winfo_exists(self.panel):
            self.panel.deiconify()
            self.panel.lift()
            return
        c = self._UI
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        W, H = sw, sh
        w = tk.Toplevel(self.root)
        self.panel = w
        w.configure(bg=c["bg"])
        w.overrideredirect(True)        # borderless: no white title bar / Python icon
        w.geometry("%dx%d+0+0" % (W, H))
        w.attributes("-topmost", True)
        try:
            w.focus_force()
        except Exception:
            pass
        w.bind("<Escape>", lambda e: self._panel_close())

        cv = tk.Canvas(w, width=W, height=H, bg=c["bg"],
                       highlightthickness=0, bd=0)
        cv.pack(fill=tk.BOTH, expand=True)
        self._pulse_cv = cv
        self._cbtn_n = 0
        self._panel_link_n = 0
        self._panel_speaking = False

        cxm = W // 2
        orb_cy = int(H * 0.21)
        osize = max(180, min(int(min(W, H) * 0.26), 360))

        # --- top-left HUD: live clock + version + status + projects ---
        VER = "v4.16"
        hx = 44
        self._hud_time = cv.create_text(hx, 46, anchor="nw", text="00:00:00",
                                        fill=c["accent"], font=("Consolas", 30, "bold"))
        self._hud_date = cv.create_text(hx, 92, anchor="nw", text="",
                                        fill=c["muted"], font=("Consolas", 13))
        cv.create_text(hx, 130, anchor="nw", text="JARVIS  %s" % VER,
                       fill=c["text"], font=("Consolas", 12, "bold"))
        cv.create_text(hx, 152, anchor="nw", text="STATUS  \u00b7  ONLINE",
                       fill=c["accent2"], font=("Consolas", 11))
        cv.create_text(hx, 188, anchor="nw", text="PROJECTS", fill=c["muted"],
                       font=("Consolas", 11, "bold"))
        cv.create_text(hx, 210, anchor="nw", text="\u203a JARVIS  (this assistant)",
                       fill=c["text"], font=("Consolas", 11))

        # --- the real particle orb (pre-rendered frames cycled to spin it) ---
        self._orb_frames = []
        self._orb_idx = 0
        if self.use_pil:
            NF = 24
            for k in range(NF):
                pil = self._render_orb_frame(osize, (k / NF) * 2 * np.pi)
                self._orb_frames.append(ImageTk.PhotoImage(pil))
            self._orb_item = cv.create_image(cxm, orb_cy, image=self._orb_frames[0])
        else:
            self._orb_item = cv.create_oval(cxm - osize // 4, orb_cy - osize // 4,
                                            cxm + osize // 4, orb_cy + osize // 4,
                                            fill=c["accent"], outline="")

        # --- wordmark + subtitle (this IS the logo) ---
        title_y = orb_cy + osize // 2 + 18
        cv.create_text(cxm, title_y, text="ACHILLES", fill=c["accent"],
                       font=("Segoe UI", 30, "bold"))
        cv.create_text(cxm, title_y + 30, text="P R O D U C T   S E A R C H",
                       fill=c["muted"], font=("Segoe UI", 11, "bold"))

        # --- pulse line (hidden until JARVIS speaks) ---
        self._pulse_y = title_y + 64
        self._pulse_x0 = int(W * 0.30)
        self._pulse_x1 = int(W * 0.70)
        self._pulse_glow = cv.create_line(
            self._pulse_x0, self._pulse_y, self._pulse_x1, self._pulse_y,
            fill="#7a3d14", width=6, capstyle="round", joinstyle="round",
            smooth=True, state="hidden")
        self._pulse_item = cv.create_line(
            self._pulse_x0, self._pulse_y, self._pulse_x1, self._pulse_y,
            fill=c["accent"], width=2, capstyle="round", joinstyle="round",
            smooth=True, state="hidden")
        self._pulse_phase = 0.0

        # --- conversation text (transparent: same colour as the background) ---
        TX1, TX2 = int(W * 0.16), int(W * 0.84)
        TY1, TY2 = int(H * 0.42), int(H * 0.84)
        self.panel_out = tk.Text(cv, bg=c["bg"], fg=c["text"],
                                 insertbackground=c["text"], font=("Segoe UI", 13),
                                 wrap="word", relief=tk.FLAT, bd=0,
                                 highlightthickness=0, padx=10, pady=8)
        cv.create_window(TX1, TY1, anchor="nw", window=self.panel_out,
                         width=TX2 - TX1, height=TY2 - TY1)
        self.panel_out.bind("<MouseWheel>",
                            lambda e: self.panel_out.yview_scroll(int(-e.delta / 120), "units"))
        self.panel_out.configure(state="disabled")
        o = self.panel_out
        o.tag_config("you",    foreground=c["link"],   font=("Segoe UI", 13, "bold"))
        o.tag_config("jarvis", foreground=c["accent"], font=("Segoe UI", 13, "bold"))
        o.tag_config("sys",    foreground=c["muted"],  font=("Segoe UI", 11, "italic"))
        o.tag_config("body",   foreground=c["text"], spacing1=2, spacing3=12,
                     lmargin1=4, lmargin2=4)

        # --- hidden typing field (revealed by the Type button) ---
        self.panel_entry = tk.Entry(cv, bg=c["input"], fg=c["text"],
                                    insertbackground=c["accent"], relief=tk.FLAT,
                                    bd=0, highlightthickness=1,
                                    highlightbackground=c["divider"],
                                    highlightcolor=c["accent"], font=("Segoe UI", 13))
        self._entry_win = cv.create_window(cxm, int(H * 0.875), anchor="center",
                                           window=self.panel_entry,
                                           width=int(W * 0.5), height=38,
                                           state="hidden")
        self.panel_entry.bind("<Return>", lambda e: self._panel_ask_typed())

        # --- controls are F-keys now (kept off the screen, as requested) ---
        cv.create_text(cxm, int(H * 0.93),
                       text="F1  Type        F2  Speak        F3  Image        "
                            "F5  Stop        Esc  Close",
                       fill=c["muted"], font=("Segoe UI", 12))

        self._panel_write("JARVIS", "Ready, sir. Press F1 to write, F2 to speak, "
                          "or F3 to send a product image. F5 stops me speaking. I "
                          "search Israeli stores and reply in English unless you "
                          "write in Hebrew.")
        self._panel_pulse_tick()

    def _panel_write(self, who, text):
        """Append a line of plain text to the panel output."""
        if self.panel is None or not tk.Toplevel.winfo_exists(self.panel):
            return
        self.panel_out.configure(state="normal")
        tag = "you" if who == "You" else ("sys" if who == "System" else "jarvis")
        self.panel_out.insert("end", f"{who}  ", tag)
        self.panel_out.insert("end", text + "\n\n", "body")
        self.panel_out.see("end")
        self.panel_out.configure(state="disabled")

    def _panel_add_link(self, title, url):
        """Append a clickable link line to the panel output."""
        if self.panel is None or not tk.Toplevel.winfo_exists(self.panel):
            return
        c = self._UI
        self.panel_out.configure(state="normal")
        tagname = "link%d" % self._panel_link_n
        self._panel_link_n += 1
        self.panel_out.tag_config("bullet", foreground=c["accent"],
                                  font=("Segoe UI", 12, "bold"))
        self.panel_out.insert("end", "   \u203a  ", "bullet")
        self.panel_out.insert("end", (title or url) + "\n", (tagname,))
        self.panel_out.tag_config(tagname, foreground=c["link"], underline=True,
                                  spacing3=6)
        self.panel_out.tag_bind(tagname, "<Button-1>",
                                lambda e, u=url: webbrowser.open(u))
        self.panel_out.tag_bind(tagname, "<Enter>",
                                lambda e: self.panel_out.config(cursor="hand2"))
        self.panel_out.tag_bind(tagname, "<Leave>",
                                lambda e: self.panel_out.config(cursor=""))
        self.panel_out.see("end")
        self.panel_out.configure(state="disabled")

    def _panel_run(self, user_text, image_path=None):
        """Worker: run the search and render results into the panel + speak."""
        if self.panel_busy:
            return
        self.panel_busy = True
        try:
            # Search panel defaults to ENGLISH; switch to Hebrew only if the
            # user's text actually contains Hebrew letters.
            lang = "he" if is_hebrew(user_text or "") else "en"
            # v4.7: a greeting in the search window gives a briefing too
            # (skipped when an image is attached - that is a real search).
            bpart = None if image_path else detect_briefing(user_text)
            if bpart:
                self.ui(lambda: self._panel_write("System", "Briefing..."))
                brief = daily_briefing(bpart, lang)
                self.ui(lambda b=brief: self._panel_write("JARVIS", b))
                self._panel_speaking = True
                try:
                    speak(brief)
                finally:
                    self._panel_speaking = False
                return
            self.ui(lambda: self._panel_write("System", "Searching..."))
            spoken, links = search_with_optional_image(user_text, image_path, lang)
            def render():
                self._panel_write("JARVIS", spoken)
                if links:
                    self._panel_write("System", "Links (click to open):")
                    for t, u in links:
                        self._panel_add_link(t, u)
                else:
                    self._panel_write("System", "No links found.")
            self.ui(render)
            self._panel_speaking = True
            try:
                speak(spoken)
            except Exception:
                pass
            finally:
                self._panel_speaking = False
        finally:
            self.panel_busy = False

    def _panel_ask_typed(self):
        if self.panel is None or self.panel_busy:
            return
        txt = self.panel_entry.get().strip()
        if not txt:
            return
        self.panel_entry.delete(0, tk.END)
        try:
            self._pulse_cv.itemconfig(self._entry_win, state="hidden")
        except Exception:
            pass
        self._panel_write("You", txt)
        threading.Thread(target=self._panel_run, args=(txt,), daemon=True).start()

    def _panel_speak(self):
        """Record one spoken request and run it through the panel."""
        if self.panel is None or self.panel_busy or self.model is None:
            return
        def worker():
            self.ui(lambda: self._panel_write("System", "Listening... speak now."))
            af = record_until_silence()
            text, _lang = transcribe(self.model, af)
            text = (text or "").strip()
            if len(text) < 2:
                self.ui(lambda: self._panel_write("System", "I didn't catch that, sir."))
                return
            self.ui(lambda: self._panel_write("You", text))
            self._panel_run(text)
        threading.Thread(target=worker, daemon=True).start()

    def _panel_pick_image(self):
        if self.panel is None or self.panel_busy:
            return
        path = filedialog.askopenfilename(
            parent=self.panel, title="Choose a product image",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.gif *.webp"),
                       ("All files", "*.*")])
        if not path:
            return
        self._panel_write("You", "[image] " + os.path.basename(path))
        prompt = self.panel_entry.get().strip() or "Identify this product and find where to buy it."
        self.panel_entry.delete(0, tk.END)
        threading.Thread(target=self._panel_run, args=(prompt, path), daemon=True).start()

    # ---- mode handling (main thread only) ----
    def _req(self, m):
        self.req_mode = m

    def _face_req(self):
        # v4.54: voice flows pop the old orb ONLY when the black-hole
        # face is disabled. F1/F2/F3 bypass this and use _req directly.
        if ACHILLES_FACE != "blackhole":
            self._req("expanded")
            # v4.67: apply on the main thread right now so the visual feedback
            # (the orb) pops the instant the wake fires, not on the next tick.
            try:
                self.ui(self._force_show)
            except Exception:
                pass

    def _hide(self):
        self.req_typing = False
        self.req_mode = "hidden"

    def _force_show(self):
        # v4.71: guard-free, unconditional re-show for the wake path. animate()'s
        # _apply_mode only reacts to a req_mode!=mode transition; if self.mode ever
        # desyncs from the real window state (it did after a hide/show cycle), the
        # orb stayed withdrawn on the next wake even though req_mode was "expanded".
        # This forces the window visible and to the front every time, and is safe
        # because it only runs on wake (not on every animation tick).
        self.mode = "expanded"
        self.req_mode = "expanded"
        self._orb_log("_force_show ENTER geo_on=%r state=%r" % (self._geo_on, self.root.state()))
        try:
            # v4.80: since v4.79 dropped overrideredirect, this is now a REAL
            # window that can genuinely be minimized/iconic. Confirmed by testing:
            # the orb showed on boot but never again on repeat wakes - a normal
            # window parked off-screen for a while can end up iconic, and
            # .geometry() alone does not restore visibility from that state;
            # deiconify()+state('normal') are required first.
            self.root.deiconify()
            self.root.state("normal")
            self.root.geometry(self._geo_on)
            self.root.lift()
            self.root.attributes("-topmost", False)
            self.root.attributes("-topmost", True)
            self.root.attributes("-alpha", 1.0)  # v4.84: force fully opaque on wake
            self.root.focus_force()
            self.root.update_idletasks()
            self._orb_log("_force_show OK viewable=%s state=%s x=%d y=%d" %
                          (self.root.winfo_viewable(), self.root.state(),
                           self.root.winfo_x(), self.root.winfo_y()))
        except Exception as _e:
            self._orb_log("_force_show FAILED: %r" % (_e,))

    def _apply_mode(self):
        # v4.77: level-triggered, not edge-triggered. The orb_diag.log evidence
        # showed _force_show() successfully call .geometry(geo_on), then
        # immediately read back the OLD off-screen coordinates - something else
        # (a delayed _hide() from the prior turn, racing on the Tk main thread)
        # was reverting it within the same tick. Reacting only to a req_mode!=mode
        # transition means a lost race stays lost forever. Re-asserting the target
        # geometry on EVERY tick (~33ms) instead means any such race self-heals
        # within one frame - the user sees at most a ~33ms flicker, not a
        # permanently invisible orb.
        try:
            # v4.81: mode/req_mode is kept ONLY for the animation-throttle switch
            # below (slower tick + frozen frame while "hidden") and the typing-box
            # placement. It no longer controls window position - the window always
            # stays at self._geo_on. This is the self-heal check, just permanently
            # targeting the one on-screen spot instead of toggling on/off.
            self.mode = self.req_mode
            try:
                cur_x, cur_y = self.root.winfo_x(), self.root.winfo_y()
                iconic = (self.root.state() != "normal")
            except Exception:
                cur_x = cur_y = None
                iconic = False
            mismatched = (cur_x is not None and (cur_x != self.ex or cur_y != self.ey))
            if mismatched or iconic:
                if iconic:
                    self.root.deiconify()
                    self.root.state("normal")
                self.root.geometry(self._geo_on)
                self.root.lift()
                self.root.attributes("-topmost", True)
                self._orb_log("_apply_mode SELF-HEAL was=(%s,%s) expected=(%s,%s) iconic=%s" %
                              (cur_x, cur_y, self.ex, self.ey, iconic))
            # v4.84: visibility is now controlled ONLY via whole-window alpha
            # (opacity), never geometry/withdraw/deiconify. The window itself
            # never moves or changes state - it just fades to fully transparent
            # (alpha=0) when "hidden" and back to opaque (alpha=1) when
            # "expanded". This is orthogonal to every mechanism that broke
            # earlier today (position, iconic state, overrideredirect mapping).
            target_alpha = 1.0 if self.mode == "expanded" else 0.0
            try:
                cur_alpha = float(self.root.attributes("-alpha"))
            except Exception:
                cur_alpha = None
            if cur_alpha is None or abs(cur_alpha - target_alpha) > 0.01:
                try:
                    self.root.attributes("-alpha", target_alpha)
                    self._orb_log("_apply_mode ALPHA was=%s target=%s mode=%s" %
                                  (cur_alpha, target_alpha, self.mode))
                except Exception as _ea:
                    self._orb_log("_apply_mode ALPHA FAILED: %r" % (_ea,))
            if self.req_typing != self.typing:
                self.typing = self.req_typing
                if self.typing and self.mode == "expanded":
                    self.entry.place(relx=0.5, rely=1.0, y=-12, anchor="s", relwidth=0.82)
                    self.entry.focus_set()
                else:
                    self.entry.place_forget()
        except Exception as _e:
            self._orb_log("_apply_mode FAILED: %r" % (_e,))
            raise

    # ---- interactions ----
    def _show_menu(self, e):
        try:
            self.menu.tk_popup(e.x_root, e.y_root)
        finally:
            self.menu.grab_release()

    def _drag_start(self, e):
        self._drag = (e.x, e.y)
        self._moved = False

    def _drag_move(self, e):
        self._moved = True
        x = self.root.winfo_x() + e.x - self._drag[0]
        y = self.root.winfo_y() + e.y - self._drag[1]
        self.root.geometry("+%d+%d" % (x, y))
        self.ex, self.ey = x, y

    def _open_typing(self):
        self._req("expanded")
        self.req_typing = True

    def _save_last_exchange(self):
        """F2: save the last full exchange (you + JARVIS) as an Obsidian note."""
        if not self._last_user and not self._last_reply:
            self._req("expanded")
            self._push("System", "Nothing to save yet, sir.")
            return
        note = f"You: {self._last_user}\n  JARVIS: {self._last_reply}"
        status = save_note(note)
        self._req("expanded")
        self._push("System", status)

    def _repeat_last(self):
        """F3: repeat JARVIS's last spoken reply aloud. Works even mid-listen,
        because pressing F3 is an explicit request."""
        if not self._last_reply:
            self._req("expanded")
            self._push("System", "I haven't said anything yet, sir.")
            return
        self._req("expanded")
        self._push("System", "Repeating last reply.")
        threading.Thread(target=lambda: speak(self._last_reply), daemon=True).start()

    # ---- control actions ----
    def talk(self, collapse_after):
        if not self.busy and self.model is not None:
            self._face_req()
            threading.Thread(target=self._turn, args=(False, collapse_after),
                             daemon=True).start()

    def _send_typed(self, _e=None):
        if self.busy or self.model is None:
            return
        txt = self.entry.get().strip()
        if not txt:
            return
        self.entry.delete(0, tk.END)
        threading.Thread(target=self._typed_turn, args=(txt,), daemon=True).start()

    def toggle_wake(self):
        self.wake_on = not self.wake_on

    def quit(self):
        self.stop = True
        try:
            if os.path.exists(SHOW_SIGNAL):
                os.remove(SHOW_SIGNAL)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            os._exit(0)

    # ---- shared state ----
    def _push(self, who, text):
        with self._lock:
            self.outbox.append({"who": who, "text": text})

    def status_text(self):
        s = self.state
        if s == "loading":
            return "Loading models..."
        if s == "listening":
            return "Listening...  (say 'write' to type)"
        if s == "thinking":
            return "Thinking..."
        if s == "speaking":
            return "Speaking..."
        if self.typing:
            return "Type and press Enter"
        return "Listening for 'Achilles'" if self.wake_on else "Wake word OFF"

    # ---- desktop-icon signal watcher ----
    def _signal_watch(self):
        while not self.stop:
            try:
                if os.path.exists(SHOW_SIGNAL):
                    os.remove(SHOW_SIGNAL)
                    if not self.busy:
                        self.talk(collapse_after=True)
            except Exception:
                pass
            time.sleep(0.4)

    # ---- worker logic ----
    def _boot(self):
        ensure_directories()
        self.state = "loading"
        self._face_req()
        self.wake_model = WhisperModel(WAKE_MODEL_SIZE, device="cpu", compute_type="int8")
        self.model = WhisperModel("small", device="cpu", compute_type="int8")
        self.memory = load_long_term_memory()
        if not ANTHROPIC_API_KEY:
            self.state = "idle"
            self._push("System", "No API key found in .env")
            return
        self.state = "idle"
        self.wake_on = True
        self._push("System", "Achilles online, sir.")
        try:
            speak("Achilles online, sir.")
        except Exception:
            pass
        # v4.54: open the black-hole face window - the assistant's
        # visual face from now on. Daemon thread so boot never blocks.
        if ACHILLES_FACE == "blackhole":
            def _open_face():
                try:
                    time.sleep(1.0)
                    print("[face]", open_achilles("core", face=True), flush=True)
                except Exception as e:
                    print("[diag] face window failed:", repr(e), flush=True)
            threading.Thread(target=_open_face, daemon=True).start()
        time.sleep(1.6)
        # v4.5: first launch of the day -> automatic briefing by clock.
        try:
            self._maybe_auto_briefing()
        except Exception as e:
            print("[diag] auto-briefing failed:", repr(e), flush=True)
        try:
            self._maybe_auto_backup()
        except Exception as e:
            print("[diag] auto-backup failed:", repr(e), flush=True)
        self._hide()
        threading.Thread(target=self._wake_loop, daemon=True).start()
        # Global hotkeys: work anywhere in Windows, even when the orb is hidden.
        # Handlers marshal back to the main thread via self.ui() because tkinter
        # isn't thread-safe.
        if HAVE_KEYBOARD:
            try:
                keyboard.add_hotkey("f1", lambda: self.ui(self._key_f1))
                keyboard.add_hotkey("f2", lambda: self.ui(self._key_f2))
                keyboard.add_hotkey("f3", lambda: self.ui(self._key_f3))
                keyboard.add_hotkey("f5", lambda: self.ui(self._key_f5))
            except Exception as e:
                print("Hotkey registration failed:", e)

    def _maybe_auto_briefing(self):
        """v4.5: on the first launch of a calendar day, greet with a short
        briefing chosen by the clock. Tracked via .jarvis_last_briefing so it
        fires only once per day."""
        marker = Path(".jarvis_last_briefing")
        today = datetime.date.today().isoformat()
        try:
            if marker.exists() and marker.read_text(encoding="utf-8").strip() == today:
                return  # already briefed today
        except Exception:
            pass
        try:
            marker.write_text(today, encoding="utf-8")
        except Exception:
            pass
        part = _briefing_part_from_clock(datetime.datetime.now())
        self._face_req()
        self.state = "thinking"
        brief = daily_briefing(part, "en")
        self._push("JARVIS", brief)
        self._last_reply = brief
        self.state = "speaking"
        try:
            speak(brief)
        except Exception:
            pass
        time.sleep(_POST_SPEAK_GUARD_S)

    def _maybe_auto_backup(self):
        """v4.31: first launch of a calendar day -> background vault
        backup. Tracked via .jarvis_last_backup so it fires only once
        per day. Runs in a daemon thread so the wake-loop is not
        delayed by zip compression."""
        marker = Path(".jarvis_last_backup")
        today = datetime.date.today().isoformat()
        try:
            if marker.exists() and marker.read_text(
                    encoding="utf-8").strip() == today:
                return  # already backed up today
        except Exception:
            pass
        try:
            marker.write_text(today, encoding="utf-8")
        except Exception:
            pass
        threading.Thread(target=backup_vault, daemon=True).start()


    def _turn(self, announce, collapse_after):
        try:
            try:
                with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                    _wf.write("[turn] entered announce=%s\n" % (announce,))
            except Exception:
                pass
            self.busy = True
            if announce:
                beep()
            # First turn of this exchange
            keep_going = self._one_exchange(first=True)
            # Continuous conversation: after answering, listen for a follow-up
            # for a few seconds. If the user speaks, keep the conversation going
            # WITHOUT needing "Hey JARVIS" again. Silence ends the exchange.
            while keep_going and not self.stop:
                keep_going = self._one_exchange(first=False)
        except Exception as e:
            try:
                with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                    _wf.write("[turn-error] %r\n" % (e,))
            except Exception:
                pass
            self._push("System", "Error: " + str(e))
        finally:
            self.busy = False
            self.state = "idle"
            if collapse_after and not self.typing:
                time.sleep(1.0)
                self._hide()

    def _one_exchange(self, first):
        """Listen once, answer once. Returns True if we should keep listening
        for a follow-up (conversation mode), False to end."""
        self.state = "listening"
        if first:
            self._q_chain = 0
            # use the pre-roll captured at wake time so the first word survives
            pr = getattr(self, "_preroll", None)
            self._preroll = None
            af = record_until_silence(preroll=pr)
        else:
            # follow-up: give up if no speech starts within a few seconds.
            # After JARVIS asks a question we widen this window (set below).
            _to = getattr(self, "_next_followup_timeout", 5.0)
            self._next_followup_timeout = 5.0
            af = record_followup(start_timeout=_to)
            if af is None:
                return False  # no follow-up -> end the conversation
        self.state = "thinking"
        user_text, lang = transcribe(self.model, af)
        try:
            with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                _wf.write("[cmd first=%s] af=%r text=%r lang=%r\n" % (first, af, user_text, lang))
        except Exception:
            pass
        # The pre-roll may include the wake word itself ("Hey Jarvis"); strip it
        # from the front of the command so it isn't treated as part of the query.
        if first and user_text:
            user_text = strip_wake_prefix(user_text)
        # Noise filter: a real command is rarely just one or two stray
        # characters. Whisper turns keyboard clacks / coughs into empty text or
        # tiny fragments, so we discard anything too short to be a real command.
        cleaned = (user_text or "").strip()
        if len(cleaned) < 3 or not re.search(r'[A-Za-z\u0590-\u05FF]', cleaned):
            # v4.12: if this is the FIRST turn right after the wake word
            # and we heard nothing useful, the user most likely said only
            # "Hey JARVIS" and then paused, waiting for an acknowledgement,
            # instead of giving the command in the same breath. So we
            # acknowledge and keep listening for the command, instead of
            # going straight back to sleep (which used to force a second
            # "Hey JARVIS").
            if first:
                ack = "כן, אדוני?" if lang == "he" else "Yes, sir?"
                self._push("JARVIS", ack)
                self.state = "speaking"
                speak(ack)
                return True   # keep listening; the follow-up turn catches the command
            return False  # nothing meaningful was said -> ignore (likely noise)
        # "write" opens the typing box instead of answering
        if detect_write(user_text) and len(user_text.split()) <= 3:
            self._req("expanded")
            self.req_typing = True
            self._push("System", "Typing enabled. Go ahead, sir.")
            return False
        # v4.5: a spoken greeting -> daily briefing instead of a normal answer.
        bpart = detect_briefing(user_text)
        if bpart:
            self._push("You", user_text)
            self.state = "thinking"
            blang = "he" if (lang == "he" or is_hebrew(user_text)) else "en"
            brief = daily_briefing(bpart, blang)
            self._push("JARVIS", brief)
            save_log(user_text, brief)
            self._last_user = user_text
            self._last_reply = brief
            self.state = "speaking"
            speak(brief)
            time.sleep(_POST_SPEAK_GUARD_S)
            return False  # v4.72: end after the briefing; wake again for more
        # Graceful goodbye: if the user is clearly ending the chat, give a short
        # sign-off (in their language) instead of silently closing.
        if detect_goodbye(user_text):
            bye = pick_farewell(lang == "he" or is_hebrew(user_text))
            self._push("You", user_text)
            self._push("JARVIS", bye)
            save_log(user_text, bye)
            self._last_user = user_text
            self._last_reply = bye
            self.state = "speaking"
            speak(bye)
            time.sleep(_POST_SPEAK_GUARD_S)
            return False  # end the conversation after the farewell
        self._push("You", user_text)
        # Lock reply language to what Whisper detected (he/en), so Hebrew speech
        # always gets a Hebrew answer even if the transcript is imperfect.
        reply = think(user_text, self.memory, lang)
        # v3.14: the brain marks a dismissal/goodbye (in ANY wording) by ending
        # its reply with the token <END>. If we see it, strip it from what we
        # show/speak and end the conversation after this turn.
        end_now = bool(re.search(r'<\s*END\s*>', reply, re.IGNORECASE))
        if end_now:
            reply = re.sub(r'<\s*END\s*>', '', reply, flags=re.IGNORECASE).strip()
            if not reply:
                reply = pick_farewell(lang == "he")
        # v5.17: close a spoken answer by offering more, so the floor is
        # explicitly handed back. Skipped when the brain already marked a
        # dismissal (<END>) - being asked "anything else?" right after saying
        # goodbye is exactly the annoyance this must avoid - and skipped when
        # the reply is itself a question, since two questions in a row is
        # worse than none.
        # v5.17b: FIRST-TURN ONLY. Appending on every follow-up turn too
        # manufactures a question mark on almost every reply, which feeds
        # straight into the existing keep-listening-if-a-question mechanic
        # below - directly undoing the v4.72 "one command per wake" guard
        # against runaway follow-up chains. A decline that is not on the
        # fixed GOODBYE_WORDS list and that the model does not confidently
        # tag <END> would then get ANOTHER manufactured offer, repeating.
        # Restricting to first keeps the close-with-an-offer behaviour
        # exactly once per wake, and lets the existing goodbye/<END> paths
        # release normally on whatever the user says next.
        if first and (not end_now) and reply and not _is_question(reply):
            reply = reply.rstrip() + " " + pick_followup_offer(
                lang == "he" or is_mostly_hebrew(reply))
        self._push("JARVIS", reply)
        save_log(user_text, reply)
        # Remember this exchange for the function keys (F2 save / F3 repeat).
        self._last_user = user_text
        self._last_reply = reply
        self.state = "speaking"
        speak(reply)
        time.sleep(_POST_SPEAK_GUARD_S)
        # v5.10: if JARVIS's own reply is a QUESTION, keep the mic open and wait
        # for the answer (no wake word needed) instead of ending. The chain cap
        # plus the follow-up silence timeout prevent any runaway loop.
        if (not end_now) and _is_question(reply):
            self._q_chain = getattr(self, "_q_chain", 0) + 1
            if self._q_chain <= 5:
                self._next_followup_timeout = 8.0
                return True
        self._q_chain = 0
        return False  # v4.72: one command per wake - end after answering so
        # background noise can't trip an endless follow-up/hallucinate loop.
        # (Say the wake word again for another command; it's instant now.)

    def _typed_turn(self, text):
        try:
            self.busy = True
            self._push("You", text)
            self.state = "thinking"
            # For typed text, detect language directly from the characters.
            lang = "he" if is_hebrew(text) else "en"
            # v4.7: a typed greeting -> daily briefing instead of a normal answer.
            bpart = detect_briefing(text)
            if bpart:
                brief = daily_briefing(bpart, lang)
                self._push("JARVIS", brief)
                save_log(text, brief)
                self._last_user = text
                self._last_reply = brief
                self.state = "speaking"
                speak(brief)
                time.sleep(_POST_SPEAK_GUARD_S)
                return
            reply = think(text, self.memory, lang)
            self._push("JARVIS", reply)
            save_log(text, reply)
            # Remember this exchange for the function keys (F2 save / F3 repeat).
            self._last_user = text
            self._last_reply = reply
            self.state = "speaking"
            speak(reply)
            time.sleep(_POST_SPEAK_GUARD_S)
        except Exception as e:
            self._push("System", "Error: " + str(e))
        finally:
            self.busy = False
            self.state = "idle"

    def _telegram_turn(self, text):
        """Run the brain on a Telegram message - text only, no voice."""
        lang = "he" if is_hebrew(text) else "en"
        bpart = detect_briefing(text)
        if bpart:
            return daily_briefing(bpart, lang)
        return think(text, self.memory, lang)

    def _telegram_loop(self):
        global _tg_offset, _tg_pair_code
        if not TELEGRAM_BOT_TOKEN:
            return
        import random
        _tg_load_chat()
        time.sleep(3)  # let _boot finish loading long-term memory first
        if _tg_chat_id is None:
            _tg_pair_code = "%06d" % random.randint(0, 999999)
            try:
                with open(str(Path(__file__).resolve().parent
                              / "telegram_pairing.txt"), "w",
                          encoding="utf-8") as _pf:
                    _pf.write("JARVIS Telegram pairing code: " + _tg_pair_code
                              + "  (send this code to your bot to link it)")
            except Exception:
                pass
            try:
                self._push("JARVIS", "\u05d8\u05dc\u05d2\u05e8\u05dd: "
                           "\u05e9\u05dc\u05d7 \u05dc\u05d1\u05d5\u05d8 "
                           "\u05d0\u05ea \u05d4\u05e7\u05d5\u05d3 " + _tg_pair_code
                           + " \u05db\u05d3\u05d9 \u05dc\u05d7\u05d1\u05e8.")
            except Exception:
                pass
            print("[telegram] pairing code: " + _tg_pair_code, flush=True)
        else:
            print("[telegram] paired with chat %s - listening." % _tg_chat_id,
                  flush=True)
        # drain backlog so we don't replay old messages from before startup
        r0 = _tg_api("getUpdates", {"timeout": 0, "offset": -1}, timeout=10)
        if r0 and r0.get("ok") and r0.get("result"):
            _tg_offset = r0["result"][-1]["update_id"] + 1
        while not self.stop:
            r = _tg_api("getUpdates",
                        {"timeout": 50, "offset": _tg_offset}, timeout=60)
            if not r or not r.get("ok"):
                time.sleep(3)
                continue
            for upd in r.get("result", []):
                _tg_offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                cid = msg["chat"]["id"]
                # --- photo -> workout auto-log (v5.16e) ---
                if ("photo" in msg and _tg_chat_id is not None
                        and cid == _tg_chat_id):
                    photos = msg.get("photo") or []
                    caption = (msg.get("caption") or "").strip()
                    dl = (_tg_download_photo(photos[-1]["file_id"])
                          if photos else None)
                    if not dl:
                        telegram_send(
                            "\u274c \u05db\u05e9\u05dc\u05d5\u05df \u05d1\u05d4\u05d5\u05e8\u05d3\u05ea \u05d4\u05ea\u05de\u05d5\u05e0\u05d4.", cid)
                        continue
                    if _is_geoloc_caption(caption):
                        guess = _geoguess_photo(dl[0], dl[1], caption)
                        if not guess:
                            telegram_send(
                                "\u274c \u05dc\u05d0 \u05d4\u05e6\u05dc\u05d7\u05ea\u05d9 \u05dc\u05e0\u05d7\u05e9 \u05de\u05d9\u05e7\u05d5\u05dd \u05de\u05d4\u05ea\u05de\u05d5\u05e0\u05d4 \u05d4\u05d6\u05d0\u05ea.", cid)
                            continue
                        telegram_send(_tg_geoloc_confirmation_text(guess), cid)
                        continue
                    extracted = _extract_workout_from_image(
                        dl[0], dl[1], caption)
                    if not extracted:
                        telegram_send(
                            "\u274c \u05dc\u05d0 \u05d4\u05e6\u05dc\u05d7\u05ea\u05d9 \u05dc\u05d6\u05d4\u05d5\u05ea \u05e0\u05ea\u05d5\u05e0\u05d9 \u05d0\u05d9\u05de\u05d5\u05df \u05d1\u05ea\u05de\u05d5\u05e0\u05d4.", cid)
                        continue
                    if extracted.get("screen") == "day_summary":
                        telegram_send(
                            "\u2139\ufe0f \u05d6\u05d4 \u05de\u05e1\u05da \u05e1\u05d9\u05db\u05d5\u05dd \u05d9\u05d5\u05de\u05d9 - \u05e1\u05da \u05d4\u05db\u05dc \u05d9\u05d5\u05de\u05d9, \u05dc\u05d0 \u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd \u05d1\u05d5\u05d3\u05d3\u05d9\u05dd. \u05e9\u05dc\u05d7 \u05e6\u05d9\u05dc\u05d5\u05dd \u05e9\u05dc \u05e8\u05e9\u05d9\u05de\u05ea \u05d4\u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd \u05d5\u05d0\u05e8\u05e9\u05d5\u05dd \u05db\u05dc \u05d0\u05d7\u05d3.", cid)
                        continue
                    _wl = extracted.get("workouts") or []
                    _entries = []
                    for _w in _wl:
                        _e = _training_log_add_workout_from_extract(_w)
                        if _e:
                            _entries.append(_e)
                    if _entries:
                        _lines = [_tg_photo_confirmation_text(_e2)
                                  for _e2 in _entries]
                        _head = ""
                        if len(_entries) > 1:
                            _head = ("\u05e0\u05e8\u05e9\u05de\u05d5 %d \u05d0\u05d9\u05de\u05d5\u05e0\u05d9\u05dd:\n"
                                     % len(_entries))
                        telegram_send(_head + "\n".join(_lines), cid)
                    else:
                        telegram_send(
                            "\u274c \u05e9\u05de\u05d9\u05e8\u05ea \u05d4\u05e8\u05d9\u05e9\u05d5\u05dd \u05e0\u05db\u05e9\u05dc\u05d4.", cid)
                    continue
                if "text" not in msg:
                    continue
                text = msg["text"].strip()
                if not text:
                    continue
                # --- pairing (only while unpaired) ---
                if _tg_chat_id is None:
                    if _tg_pair_code and text == _tg_pair_code:
                        _tg_save_chat(cid)
                        try:
                            os.remove(str(Path(__file__).resolve().parent
                                          / "telegram_pairing.txt"))
                        except Exception:
                            pass
                        telegram_send("\u05de\u05d7\u05d5\u05d1\u05e8. JARVIS "
                                      "\u05e6\u05de\u05d5\u05d3 \u05d0\u05dc\u05d9\u05da "
                                      "\u05e2\u05db\u05e9\u05d9\u05d5, \u05d0\u05d3\u05d5\u05e0\u05d9. "
                                      "\u05e9\u05dc\u05d7 \u05dc\u05d9 \u05db\u05dc \u05d3\u05d1\u05e8.",
                                      cid)
                        try:
                            self._push("JARVIS", "Telegram paired.")
                        except Exception:
                            pass
                    else:
                        telegram_send("\u05e9\u05dc\u05d7 \u05d0\u05ea \u05e7\u05d5\u05d3 "
                                      "\u05d4\u05e6\u05d9\u05de\u05d5\u05d3 \u05e9\u05de\u05d5\u05e4\u05d9\u05e2 "
                                      "\u05e2\u05dc JARVIS \u05db\u05d3\u05d9 \u05dc\u05d7\u05d1\u05e8.",
                                      cid)
                    continue
                # --- authorized chat only ---
                if cid != _tg_chat_id:
                    telegram_send("\u05dc\u05d0 \u05de\u05d5\u05e8\u05e9\u05d4.", cid)
                    continue
                # --- run the brain (serialize with voice/typed turns) ---
                waited = 0.0
                while self.busy and waited < 60:
                    time.sleep(0.5); waited += 0.5
                self.busy = True
                try:
                    _tg_api("sendChatAction",
                            {"chat_id": cid, "action": "typing"}, timeout=10)
                    reply = self._telegram_turn(text)
                except Exception as e:
                    reply = "Error: " + str(e)
                finally:
                    self.busy = False
                telegram_send(reply or "(no reply)", cid)
                try:
                    self._push("Telegram", text)
                    self._push("JARVIS", reply)
                except Exception:
                    pass

    def _wake_loop(self):
        # v4.70: Vosk streaming wake detection (replaces the Whisper wake path).
        # A small en-us model with a fixed grammar recognizes the wake word
        # reliably and near-instantly, with essentially no hallucinated
        # false-fires. The model is loaded once and cached locally.
        try:
            import queue as _queue
            from vosk import Model as _VoskModel, KaldiRecognizer as _KaldiRec
        except Exception as e:
            # v4.74: Vosk unavailable -> DON'T leave the orb un-poppable. Fall
            # back to the Whisper wake engine (the proven v4.67 path) so saying
            # the wake word still pops the orb. Before this fix a missing Vosk
            # install returned here and the orb, hidden after boot, could never
            # reappear on wake -> the reported "floating orb never appears when
            # invoked". self.wake_model (Whisper "tiny") is already loaded at boot.
            print("[diag] Vosk import failed, falling back to Whisper wake:",
                  repr(e), flush=True)
            try:
                self._push("System", "Using Whisper wake engine, sir.")
            except Exception:
                pass
            self._wake_loop_whisper()
            return
        try:
            _vmodel = _VoskModel(lang="en-us")
        except Exception as e:
            # v4.74: same fallback if the Vosk model can't be downloaded/loaded,
            # so activation (and therefore the orb) never silently dies.
            print("[diag] Vosk model load failed, falling back to Whisper wake:",
                  repr(e), flush=True)
            try:
                self._push("System", "Using Whisper wake engine, sir.")
            except Exception:
                pass
            self._wake_loop_whisper()
            return
        _GRAMMAR = '["achilles", "hey achilles", "[unk]"]'
        pre_len = int(SAMPLE_RATE * PREROLL_SEC)
        blk = int(SAMPLE_RATE * 0.15)
        print("[wake] Vosk wake engine ready (say 'Achilles').", flush=True)

        while not self.stop:
            if not self.wake_on or self.busy:
                time.sleep(0.2)
                continue
            rec = _KaldiRec(_vmodel, SAMPLE_RATE, _GRAMMAR)
            rec.SetWords(True)
            q = _queue.Queue()
            pre = {"buf": np.zeros(pre_len, dtype=np.float32)}

            def cb(indata, frames, t_info, status, _q=q, _pre=pre):
                x = indata[:, 0]
                _q.put((np.clip(x, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes())
                n = len(x)
                b = _pre["buf"]
                b = np.roll(b, -n)
                b[-n:] = x
                _pre["buf"] = b

            triggered = False
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                    dtype='float32', blocksize=blk, callback=cb):
                    while not self.stop and self.wake_on and not self.busy:
                        try:
                            data = q.get(timeout=0.3)
                        except _queue.Empty:
                            continue
                        hit = False
                        if rec.AcceptWaveform(data):
                            # v4.73: fire ONLY on a finalized segment that is
                            # cleanly the wake word - "achilles" present, NO
                            # out-of-vocabulary "[unk]" token mixed in, and
                            # short. Background video/music decodes as runs of
                            # "[unk]", so this rejects the false-fire storm.
                            _res = json.loads(rec.Result())
                            _txt = _res.get("text", "").strip()
                            _toks = _txt.split()
                            hit = ("achilles" in _toks and "[unk]" not in _toks
                                   and 1 <= len(_toks) <= 6)
                            if _txt:
                                _cf = [w.get("conf", 1.0)
                                       for w in _res.get("result", [])
                                       if w.get("word") == "achilles"]
                                _mc = min(_cf) if _cf else 1.0
                                try:
                                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                                        _wf.write("[heard] vosk final=%r conf=%.2f wake=%s\n"
                                                  % (_txt, _mc, hit))
                                except Exception:
                                    pass
                        # partials are intentionally ignored now (they
                        # fluctuate and caused constant false triggers).
                        if hit:
                            triggered = True
                            self._preroll = pre["buf"].copy()
                            break
            except Exception as e:
                print("[diag] wake-loop mic reopen failed, retrying:", repr(e), flush=True)
                try:
                    self._push("System", "Microphone unavailable - retrying. "
                               "Close other apps using the mic, sir.")
                except Exception:
                    pass
                time.sleep(0.6)
            if triggered:
                try:
                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                        _wf.write("[trigger] firing _turn\n")
                except Exception:
                    pass
                self._push("System", "Wake word detected.")
                self._face_req()
                self._turn(True, collapse_after=True)
                time.sleep(0.6)

    def _wake_loop_whisper(self):
        # v4.74: Whisper-based wake fallback (the v4.67 engine), used when Vosk
        # is not installed or its model can't load. Uses the already-loaded
        # self.wake_model ("tiny") + WAKE_GATE + detect_wake(); on a hit it pops
        # the orb via _face_req() and runs one turn, exactly like the Vosk path.
        print("[wake] Whisper wake engine ready (say the wake word).", flush=True)
        ring_len = int(SAMPLE_RATE * WAKE_WINDOW)
        block = int(SAMPLE_RATE * 0.1)
        while not self.stop:
            if not self.wake_on or self.busy or self.wake_model is None:
                time.sleep(0.2)
                continue
            ring = {"buf": np.zeros(ring_len, dtype=np.float32)}
            lock = threading.Lock()

            def cb(indata, frames, t_info, status, _ring=ring, _lock=lock):
                x = indata[:, 0]
                n = len(x)
                with _lock:
                    b = _ring["buf"]
                    b = np.roll(b, -n)
                    b[-n:] = x
                    _ring["buf"] = b

            triggered = False
            try:
                with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32',
                                    blocksize=block, callback=cb):
                    time.sleep(WAKE_STEP)
                    while not self.stop and self.wake_on and not self.busy:
                        with lock:
                            buf = ring["buf"].copy()
                        if float(np.max(np.abs(buf))) >= WAKE_GATE:
                            sf.write("wake_window.wav", buf, SAMPLE_RATE)
                            try:
                                text = transcribe_wake(self.wake_model, "wake_window.wav")
                            except Exception:
                                text = ""
                            _hit = (bool(text) and detect_wake(text)
                                    and len(text.split()) <= 8)
                            if text:
                                try:
                                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                                        _wf.write("[heard] whisper %r match=%s\n" % (text, _hit))
                                except Exception:
                                    pass
                            if _hit:
                                triggered = True
                                # tail of the ring as pre-roll so the first
                                # command word (same breath) isn't lost.
                                with lock:
                                    tail = ring["buf"][-int(SAMPLE_RATE * PREROLL_SEC):].copy()
                                self._preroll = tail
                                break
                        time.sleep(WAKE_STEP)
            except Exception as e:
                # Mic may be briefly busy (just released by a conversation).
                # Surface it (a console-less GUI hides print()) then back off and
                # retry instead of dying quietly.
                print("[diag] whisper wake-loop mic reopen failed, retrying:",
                      repr(e), flush=True)
                try:
                    self._push("System", "Microphone unavailable - retrying. "
                               "Close other apps using the mic, sir.")
                except Exception:
                    pass
                time.sleep(0.6)
            if triggered:
                try:
                    with open("wake_diag.log", "a", encoding="utf-8") as _wf:
                        _wf.write("[trigger] firing _turn (whisper)\n")
                except Exception:
                    pass
                self._push("System", "Wake word detected.")
                self._face_req()
                self._turn(True, collapse_after=True)
                # Settle: give the OS a moment to free the audio device before we
                # re-open it, or the next InputStream open can fail and the wake
                # path goes silently deaf.
                time.sleep(0.6)

    # ---- Pillow renderer ----
    # ---- v4.57: BLACK HOLE face (drawn inside this same window) -----------
    def _bh_build_async(self):
        """Pre-render the black-hole layers off the UI thread."""
        try:
            # v5.17a: 760 measured as the sweet spot - +46% linear resolution
            # and double the baked frames for ~1.3x the per-frame cost of the
            # old 520 (1024 measured ~1.9x and would drop the frame rate).
            self._bh_make_layers(760)
            print("[face] black-hole layers ready", flush=True)
        except Exception as e:
            print("[diag] black-hole prerender failed, keeping orb:", repr(e),
                  flush=True)

    def _bh_make_layers(self, S):
        """Build all static/animated layers once with numpy + PIL."""
        NF = 48  # v5.17a: halves the angular gap the cross-fade must hide
        ax = np.linspace(-1.0, 1.0, S, dtype=np.float32)
        x, y = np.meshgrid(ax, ax)
        yd = y / 0.26                      # squash = camera tilt over the disk
        r = np.sqrt(x * x + yd * yd)
        th = np.arctan2(yd, x)
        rc = np.sqrt(x * x + y * y)        # true screen-space radius
        RH, D1, D2 = 0.28, 0.34, 0.93      # shadow / disk inner / disk outer
        hot = np.clip(1.0 - (r - D1) / (D2 - D1), 0.0, 1.0)
        ring = (np.clip((r - D1) / 0.06, 0.0, 1.0)
                * np.clip((D2 - r) / 0.18, 0.0, 1.0))
        dop = np.clip(1.0 + 0.75 * np.cos(th), 0.45, 1.8) ** 1.3
        front_m = np.clip(y / 0.05, 0.0, 1.0)    # near half passes IN FRONT
        back_m = 1.0 - front_m

        def to_img(cr, cg, cb, a, mask=None):
            if mask is not None:
                a = a * mask
            arr = (np.dstack([np.clip(cr, 0, 1), np.clip(cg, 0, 1),
                              np.clip(cb, 0, 1), np.clip(a, 0, 1)])
                   * 255).astype(np.uint8)
            return Image.fromarray(arr, "RGBA")

        fronts, backs = [], []
        for k in range(NF):
            ph = (k / float(NF)) * 2.0 * np.pi
            # v4.58: the whole texture is a function of (theta - phase),
            # so material streaks SWEEP coherently around the ring while
            # the doppler bright side stays fixed in space - real rotation.
            ta = th - ph
            sw = (0.62 + 0.30 * np.sin(2.0 * ta + r * 3.0)
                  + 0.16 * np.sin(5.0 * ta + r * 9.0)
                  + 0.07 * np.sin(11.0 * ta - r * 16.0)
                  + 0.04 * np.sin(23.0 * ta + r * 31.0))
            em = ring * (0.30 + 1.35 * hot ** 1.6) * np.clip(sw, 0.05, 2.0) * dop
            em = np.clip(em, 0.0, 1.6)
            cr = (0.55 + 0.50 * hot) * em
            cg = (0.20 + 0.62 * hot) * em
            cb = (0.06 + 0.50 * hot) * em
            a = em * 1.4

            def with_glow(im):
                try:
                    g = im.filter(ImageFilter.GaussianBlur(12))  # v5.17a: scaled with S
                    g.alpha_composite(im)
                    return g
                except Exception:
                    return im
            fronts.append(with_glow(to_img(cr, cg, cb, a, front_m)))
            backs.append(with_glow(to_img(cr * 0.85, cg * 0.85, cb * 0.85,
                                          a, back_m)))

        # lensed halo arcing over the top of the shadow
        halo = np.clip(1.0 - np.abs(rc - RH * 1.14) / 0.045, 0.0, 1.0) ** 1.5
        upper = np.clip((-y + 0.05) / 0.45, 0.0, 1.0)
        lower = np.clip((y - 0.10) / 0.50, 0.0, 1.0)
        hdop = np.clip(1.0 - 0.55 * np.cos(np.arctan2(y, x)), 0.45, 1.6)
        hem = halo * (0.10 + 1.05 * upper + 0.50 * lower) * hdop
        arc = to_img(0.98 * hem, 0.66 * hem, 0.36 * hem, hem)

        # thin photon ring hugging the shadow
        pr = np.clip(1.0 - np.abs(rc - RH * 1.02) / 0.020, 0.0, 1.0) ** 1.1
        rdop = np.clip(1.0 + 0.30 * x / np.maximum(rc, 1e-4), 0.65, 1.35)
        pr = pr * rdop
        ring_img = to_img(1.0 * pr, 0.82 * pr, 0.55 * pr, pr)

        # the event horizon: pure black, razor edge
        zer = np.zeros_like(rc)
        sh_a = np.clip((RH - rc) / 0.012 + 1.0, 0.0, 1.0)
        shadow = to_img(zer, zer, zer, sh_a)

        # v4.58: clean PURE-BLACK disc backdrop, crisp edge, no stars -
        # exactly the user's spec: black circle -> black hole -> ring.
        edge = np.clip((0.985 - rc) / 0.012, 0.0, 1.0)
        stars = to_img(np.full_like(rc, 0.004), np.full_like(rc, 0.004),
                       np.full_like(rc, 0.008), edge)

        # v5.17a: arc/shadow/ring are static and composited consecutively
        # every tick - bake them into ONE "mid" layer once, saving two
        # full-size composites per frame. Old keys kept for compatibility.
        mid = arc.copy()
        mid.alpha_composite(shadow)
        mid.alpha_composite(ring_img)
        self._bhL = {"S": S, "NF": NF, "stars": stars, "front": fronts,
                     "back": backs, "arc": arc, "ring": ring_img,
                     "shadow": shadow, "mid": mid}

    def _render_bh(self, Wc, Hc, st, now):
        """The black hole IS the orb now: same window, same states, new
        face. Falls back to the particle orb until layers are ready."""
        L = getattr(self, "_bhL", None)
        if L is None:
            return self._render_pil(Wc, Hc, st, now)
        S = L["S"]

        if st == "listening":
            spd, boost = 2.2, 1.35
        elif st == "thinking":
            spd, boost = 3.0, 0.55
        elif st == "speaking":
            spd, boost = 1.6, 1.25 + 0.30 * abs(np.sin(now / 160.0))
        else:
            spd, boost = 1.0, (0.55 if st == "loading" else 1.0)
        # v4.62: very slow majestic spin (~45s/rev at idle) + cross-fade
        # between adjacent baked frames -> perfectly SMOOTH at any speed.
        # v5.17a: 0.090 with NF=48 is the same angular speed 0.045 gave at
        # NF=24 - the spin FEELS identical, only smoother.
        self._bh_ph = (self._bh_ph + 0.090 * spd) % L["NF"]
        i = int(self._bh_ph)
        j = (i + 1) % L["NF"]
        f = self._bh_ph - i
        front = Image.blend(L["front"][i], L["front"][j], f)
        back = Image.blend(L["back"][i], L["back"][j], f)
        if abs(boost - 1.0) > 0.03:
            front = ImageEnhance.Brightness(front).enhance(boost)
            back = ImageEnhance.Brightness(back).enhance(boost)

        img = L["stars"].copy()
        img.alpha_composite(back)
        img.alpha_composite(L.get("mid") or L["arc"])  # v5.17a: pre-baked mid
        if "mid" not in L:
            img.alpha_composite(L["shadow"])
            img.alpha_composite(L["ring"])
        img.alpha_composite(front)
        dr = ImageDraw.Draw(img)

        if st == "thinking":
            # a captured blue star orbits the hole; camera leans in on it
            self._bh_star_a += 0.045
            px = S / 2.0 + np.cos(self._bh_star_a) * S * 0.30
            py = S / 2.0 + np.sin(self._bh_star_a) * S * 0.10 - S * 0.05
            gg = 0.7 + 0.3 * np.sin(now / 110.0)
            for rad, alp in ((13.2, 60), (7.3, 130), (3.5, 255)):  # v5.17a: x S/520
                dr.ellipse([px - rad, py - rad, px + rad, py + rad],
                           fill=(int(160 + 60 * gg), int(200 + 40 * gg), 255,
                                 int(alp * gg)))
            z = 1.45
            cw = S / z
            cxz = min(max(px, cw / 2.0), S - cw / 2.0)
            cyz = min(max(py, cw / 2.0), S - cw / 2.0)
            img = img.crop((int(cxz - cw / 2), int(cyz - cw / 2),
                            int(cxz + cw / 2), int(cyz + cw / 2)))
            img = img.resize((S, S), Image.LANCZOS)
            dr = ImageDraw.Draw(img)

        if self.ripple_on:                       # speaking ripple, as before
            self.ripple += 0.02
            if self.ripple >= 1.0:
                self.ripple_on = False
            else:
                rr = self.ripple * S * 0.62
                aa = int(max(0, (1 - self.ripple) * 180))
                dr.ellipse([S / 2 - rr, S / 2 - rr, S / 2 + rr, S / 2 + rr],
                           outline=(255, 150, 70, aa), width=3)  # v5.17a: x S/520

        D = max(2, int(min(Wc, Hc) * 0.97))
        img = img.resize((D, D), Image.LANCZOS)
        out = Image.new("RGBA", (Wc, Hc), (0, 0, 0, 0))
        out.alpha_composite(img, (int(Wc / 2 - D / 2),
                                  int(Hc / 2 - D / 2 - 12)))
        return ImageTk.PhotoImage(out)

    def _render_pil(self, Wc, Hc, st, now):
        SS = self.SS
        W, H = Wc * SS, Hc * SS
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        R = min(W, H) * 0.30
        focal = R * 2.6
        cx, cy = W / 2.0, H / 2.0 - 14 * SS

        # warm backing disc, a bit larger than the sphere (skip while zoomed in)
        if st != "thinking":
            disc_r = R * 1.55
            disc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            dd = ImageDraw.Draw(disc)
            steps = 26
            for k in range(steps):
                t = k / (steps - 1.0)
                rr = disc_r * (1.0 - t)
                cc = (int(40 + 90 * t), int(15 + 35 * t), int(8 + 12 * t), 255)
                dd.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=cc)
            try:
                disc = disc.filter(ImageFilter.GaussianBlur(SS * 1.2))
            except Exception:
                pass
            img.alpha_composite(disc)
            dr = ImageDraw.Draw(img)

        spin = 0.0015 if st == "thinking" else (0.006 if st == "listening" else 0.0035)
        self.ang += spin
        pulse = 1.0
        if st == "listening":
            pulse = 1 + 0.06 * np.sin(now / 130.0)
        elif st == "idle":
            pulse = 1 + 0.02 * np.sin(now / 700.0)
        tzoom = 2.3 if st == "thinking" else 1.0
        self.zoom += (tzoom - self.zoom) * 0.10
        zc = min(self.zoom, 1.5)

        sa, ca = np.sin(self.ang), np.cos(self.ang)
        ox = oy = 0.0
        if st == "thinking":
            spx, spy, spz = self.pts[self.sel]
            sx0 = spx * ca + spz * sa
            sz0 = -spx * sa + spz * ca
            sc0 = focal / (focal + sz0 * R)
            ox = sx0 * R * sc0
            oy = spy * R * sc0

        lo, hi = RAMPS.get(st, RAMPS["idle"])
        # sort back-to-front for nicer overlap
        order = []
        for i in range(self.N):
            px0, py0, pz0 = self.pts[i]
            z = -px0 * sa + pz0 * ca
            order.append((z, i))
        order.sort()

        selX = selY = None
        selR = 2.0
        for z, i in order:
            px0, py0, pz0 = self.pts[i]
            x = px0 * ca + pz0 * sa
            y = py0
            sc = focal / (focal + z * R) * pulse
            X = cx + (x * R * sc - ox) * self.zoom
            Y = cy + (y * R * sc - oy) * self.zoom
            depth = (z + 1) / 2.0
            rad = (1.3 + 2.3 * depth) * zc * SS
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            a = int(70 + 170 * depth)
            if st == "thinking" and i == self.sel:
                r, g, b, a = 235, 248, 255, 255
                rad *= 2.4
                selX, selY, selR = X, Y, rad
            elif st == "thinking":
                a = int(a * 0.4)
            # soft glow halo
            gr = rad * 2.4
            dr.ellipse([X - gr, Y - gr, X + gr, Y + gr],
                       fill=(_clamp(r), _clamp(g), _clamp(b), int(a * 0.28)))
            dr.ellipse([X - rad, Y - rad, X + rad, Y + rad],
                       fill=(_clamp(r), _clamp(g), _clamp(b), _clamp(a)))

        if st == "thinking" and selX is not None:
            gg = 0.5 + 0.4 * np.sin(now / 110.0)
            rr = selR + (10 + 3 * np.sin(now / 110.0)) * SS
            dr.ellipse([selX - rr, selY - rr, selX + rr, selY + rr],
                       outline=(255, _clamp(170 * gg + 40), _clamp(40 * gg + 10),
                                220), width=max(1, SS))

        if self.ripple_on:
            self.ripple += 0.02
            if self.ripple >= 1.0:
                self.ripple_on = False
            else:
                rr = self.ripple * R * 2.0
                aa = int(max(0, (1 - self.ripple) * 180))
                dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                           outline=(255, 140, 50, aa), width=max(1, int(2 * SS)))

        if SS != 1:
            img = img.resize((Wc, Hc), Image.LANCZOS)
        # soft overall bloom
        try:
            img = img.filter(ImageFilter.GaussianBlur(0.4))
        except Exception:
            pass
        return ImageTk.PhotoImage(img)

    # ---- animation (main thread) ----
    def animate(self):
        # v4.67 CRITICAL: this method MUST always reschedule itself, or the whole
        # display loop dies and the orb can never appear again on the next wake
        # (req_mode is set to "expanded" but nothing ever applies it). So the
        # body is guarded and the after() reschedule lives in finally.
        if self.stop:
            return
        delay = 33
        try:
            self._apply_mode()

            with self._lock:
                msgs = self.outbox
                self.outbox = []
            for m in msgs:
                txt = m["text"]
                if len(txt) > 66:
                    txt = txt[:63] + "..."
                self._hold = txt
                self._hold_until = time.time() + 4.0

            st = self.state
            if st != self.prev:
                if st == "thinking":
                    self.sel = int(np.random.randint(0, self.N))
                if st == "speaking":
                    self.ripple = 0.0
                    self.ripple_on = True
                self.prev = st

            if self.mode != "expanded":
                delay = 80
            else:
                Wc = max(self.cv.winfo_width(), 1)
                Hc = max(self.cv.winfo_height(), 1)
                now = time.time() * 1000.0

                if self.use_pil and Wc > 2 and Hc > 2:
                    try:
                        self._tkimg = self._render_pil(Wc, Hc, st, now)  # v4.69: orange dot-orb is the base face
                        self.cv.itemconfig(self.img_id, image=self._tkimg)
                        self.cv.coords(self.img_id, 0, 0)
                    except Exception as e:
                        self.use_pil = False
                        print("PIL render failed, fallback:", e)
                        try:
                            self._orb_log("PIL render FAILED -> canvas fallback: %r" % (e,))
                        except Exception:
                            pass
                else:
                    self._render_canvas(Wc, Hc, st, now)

                self.cv.coords(self.status_id, Wc / 2.0, Hc - 40)
                self.cv.tag_raise(self.status_id)
                if self._hold_until > time.time():
                    self.cv.itemconfig(self.status_id, text=self._hold)
                else:
                    self.cv.itemconfig(self.status_id, text=self.status_text())
        except Exception as _e:
            print("[diag] animate frame error (continuing):", repr(_e), flush=True)
            try:
                self._orb_log("animate FAILED: %r" % (_e,))
            except Exception:
                pass
        finally:
            if not self.stop:
                try:
                    self.root.after(delay, self.animate)
                except Exception:
                    pass

    # ---- fallback canvas renderer ----
    def _render_canvas(self, Wc, Hc, st, now):
        R = min(Wc, Hc) * 0.30
        focal = R * 2.6
        cx, cy = Wc / 2.0, Hc / 2.0 - 14
        spin = 0.0015 if st == "thinking" else (0.006 if st == "listening" else 0.0035)
        self.ang += spin
        pulse = 1.0
        if st == "listening":
            pulse = 1 + 0.06 * np.sin(now / 130.0)
        elif st == "idle":
            pulse = 1 + 0.02 * np.sin(now / 700.0)
        tzoom = 2.3 if st == "thinking" else 1.0
        self.zoom += (tzoom - self.zoom) * 0.10
        zc = min(self.zoom, 1.5)
        sa, ca = np.sin(self.ang), np.cos(self.ang)
        ox = oy = 0.0
        if st == "thinking":
            spx, spy, spz = self.pts[self.sel]
            sx0 = spx * ca + spz * sa
            sz0 = -spx * sa + spz * ca
            sc0 = focal / (focal + sz0 * R)
            ox = sx0 * R * sc0
            oy = spy * R * sc0
        lo, hi = RAMPS.get(st, RAMPS["idle"])
        selX, selY, selR = cx, cy, 2.0
        for i in range(self.N):
            px0, py0, pz0 = self.pts[i]
            x = px0 * ca + pz0 * sa
            z = -px0 * sa + pz0 * ca
            y = py0
            sc = focal / (focal + z * R) * pulse
            X = cx + (x * R * sc - ox) * self.zoom
            Y = cy + (y * R * sc - oy) * self.zoom
            depth = (z + 1) / 2.0
            rad = (1.3 + 2.2 * depth) * zc
            r = lo[0] + (hi[0] - lo[0]) * depth
            g = lo[1] + (hi[1] - lo[1]) * depth
            b = lo[2] + (hi[2] - lo[2]) * depth
            if st == "thinking" and i == self.sel:
                r, g, b = 235, 248, 255
                rad *= 2.4
                selX, selY, selR = X, Y, rad
            elif st == "thinking":
                r, g, b = r * 0.4, g * 0.4, b * 0.4
            self.cv.coords(self.items[i], X - rad, Y - rad, X + rad, Y + rad)
            self.cv.itemconfig(self.items[i], fill=_hexcol(r, g, b), outline="")
        if st == "thinking":
            gg = 0.5 + 0.4 * np.sin(now / 110.0)
            rr = selR + 9 + 3 * np.sin(now / 110.0)
            self.cv.coords(self.ring_id, selX - rr, selY - rr, selX + rr, selY + rr)
            self.cv.itemconfig(self.ring_id,
                               outline=_hexcol(230 * gg + 25, 245 * gg + 10, 255 * gg))
        else:
            self.cv.itemconfig(self.ring_id, outline="")
        if self.ripple_on:
            self.ripple += 0.02
            rr = self.ripple * R * 2.0
            if self.ripple >= 1.0:
                self.ripple_on = False
                self.cv.itemconfig(self.ripple_id, outline="")
            else:
                self.cv.coords(self.ripple_id, cx - rr, cy - rr, cx + rr, cy + rr)
                self.cv.itemconfig(self.ripple_id, outline="#46e0d6")
        else:
            self.cv.itemconfig(self.ripple_id, outline="")

def main():
    root = tk.Tk()
    App(root)
    # --- WorldView server autostart (worldview_autostart) --------------
    # Keep the :7777 server alive for the whole session (phone access via
    # LAN / Tailscale) instead of only while a WorldView window is open.
    try:
        import threading as _thr
        from pathlib import Path as _P
        def _wv_autostart():
            try:
                _fd = _P(__file__).resolve().parent
                _ensure_worldview_server(_fd, port=7777)
            except Exception as _e:
                print("[diag] worldview autostart failed:", repr(_e))
        _thr.Thread(target=_wv_autostart, daemon=True).start()
    except Exception as _e:
        print("[diag] worldview autostart not scheduled:", repr(_e))
    # --- Secure live location sharing: v4.89 LAZY START ----------------
    # Boot autostart REMOVED on purpose. In v4.85-v4.88 the share server +
    # Tailscale Funnel calls ran during application startup; a stall there
    # could take down the whole boot (orb + voice). Now nothing location-
    # related runs at boot; _ensure_location_sharing() is invoked lazily
    # inside share_live_location() on first use, so a worst-case hang is
    # contained to that one voice command.
    # ------------------------------------------------------------------
    root.mainloop()

if __name__ == "__main__":
    main()