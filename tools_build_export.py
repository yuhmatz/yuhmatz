#!/usr/bin/env python3
"""Bundle the audit + handoff into one self-contained, printable HTML file."""
import html
import re
from pathlib import Path

import markdown

REPO = Path("/home/user/yuhmatz")
OUT = REPO / "ACHILLES_v5.36_audit_export.html"

EXTS = ["extra", "tables", "fenced_code", "sane_lists", "toc"]


def render(path):
    md = markdown.Markdown(extensions=EXTS, extension_configs={"toc": {"permalink": False}})
    return md.convert(path.read_text(encoding="utf-8"))


def severity_badges(body):
    """Tag finding headings so they can be colour-coded, and add anchors."""
    def repl(m):
        level, attrs, text = m.group(1), m.group(2), m.group(3)
        sev = ""
        code = re.match(r"\s*(C|H|M|L|A)-(\d+)\b", html.unescape(text))
        if code:
            sev = {"C": "crit", "H": "high", "M": "med", "L": "low", "A": "arch"}[code.group(1)]
        cls = f' class="finding {sev}"' if sev else ""
        return f"<h{level}{cls}{attrs}>{text}</h{level}>"

    return re.sub(r"<h([1-6])((?:\s[^>]*)?)>(.*?)</h\1>", repl, body, flags=re.S)


def build_toc(body, prefix):
    """Extract h1/h2 for the sidebar."""
    items = []
    for m in re.finditer(r'<h([12])[^>]*id="([^"]+)"[^>]*>(.*?)</h\1>', body, flags=re.S):
        lvl, anchor, text = m.group(1), m.group(2), re.sub(r"<[^>]+>", "", m.group(3))
        items.append((int(lvl), f"{prefix}{anchor}", html.unescape(text).strip()))
    return items


def prefix_ids(body, prefix):
    return re.sub(r'(<h[1-6][^>]*\sid=")', r"\g<1>" + prefix, body)


audit = prefix_ids(severity_badges(render(REPO / "SECURITY_AUDIT_v5.36.md")), "a-")
handoff = prefix_ids(severity_badges(render(REPO / "HANDOFF.md")), "h-")

toc = [(0, None, "AUDIT")] + build_toc(audit, "") + \
      [(0, None, "HANDOFF")] + build_toc(handoff, "")

nav = []
for lvl, anchor, text in toc:
    if anchor is None:
        nav.append(f'<div class="nav-sec">{html.escape(text)}</div>')
    else:
        nav.append(f'<a class="nav-l{lvl}" href="#{anchor}">{html.escape(text)}</a>')
nav_html = "\n".join(nav)

CSS = """
:root{
  --bg:#fbfaf8; --fg:#1f1d1b; --muted:#6b6660; --rule:#e3ded6; --card:#fff;
  --code-bg:#f4f1ec; --accent:#b8451f;
  --crit:#a8331a; --crit-bg:#fdf0ec; --high:#b2661a; --high-bg:#fdf5ea;
  --med:#7a6420;  --med-bg:#faf6e8;  --low:#5a6b52;  --low-bg:#f2f6ef;
  --arch:#4a5a6b; --arch-bg:#eef2f6;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#16151a; --fg:#e8e5e0; --muted:#9a948c; --rule:#2e2c33; --card:#1c1b21;
    --code-bg:#232128; --accent:#e8825c;
    --crit:#f08a70; --crit-bg:#2a1a17; --high:#e8ae6a; --high-bg:#2a2117;
    --med:#d6c476;  --med-bg:#262315;  --low:#9dbb8f;  --low-bg:#1b2419;
    --arch:#9ab4cc; --arch-bg:#1a2129;
  }
}
:root[data-theme="dark"]{
  --bg:#16151a; --fg:#e8e5e0; --muted:#9a948c; --rule:#2e2c33; --card:#1c1b21;
  --code-bg:#232128; --accent:#e8825c;
  --crit:#f08a70; --crit-bg:#2a1a17; --high:#e8ae6a; --high-bg:#2a2117;
  --med:#d6c476;  --med-bg:#262315;  --low:#9dbb8f;  --low-bg:#1b2419;
  --arch:#9ab4cc; --arch-bg:#1a2129;
}
:root[data-theme="light"]{
  --bg:#fbfaf8; --fg:#1f1d1b; --muted:#6b6660; --rule:#e3ded6; --card:#fff;
  --code-bg:#f4f1ec; --accent:#b8451f;
  --crit:#a8331a; --crit-bg:#fdf0ec; --high:#b2661a; --high-bg:#fdf5ea;
  --med:#7a6420;  --med-bg:#faf6e8;  --low:#5a6b52;  --low-bg:#f2f6ef;
  --arch:#4a5a6b; --arch-bg:#eef2f6;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.65 ui-serif,Georgia,"Iowan Old Style",Palatino,serif;
  -webkit-text-size-adjust:100%}
.wrap{display:grid;grid-template-columns:262px minmax(0,1fr);gap:0;
  max-width:1240px;margin:0 auto}
nav{position:sticky;top:0;align-self:start;max-height:100vh;overflow-y:auto;
  padding:28px 18px 60px;border-right:1px solid var(--rule);
  font:12.5px/1.45 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
nav a{display:block;color:var(--muted);text-decoration:none;padding:3px 6px;
  border-radius:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
nav a:hover{color:var(--accent);background:var(--code-bg)}
.nav-l1{font-weight:650;color:var(--fg)!important;margin-top:9px}
.nav-l2{padding-left:14px!important}
.nav-sec{margin:20px 0 6px;font-size:10.5px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent);font-weight:700}
main{padding:44px 46px 120px;min-width:0}
h1,h2,h3,h4{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif;
  line-height:1.25;letter-spacing:-.012em}
h1{font-size:31px;margin:52px 0 18px;padding-bottom:11px;border-bottom:2px solid var(--rule)}
h2{font-size:22px;margin:40px 0 13px}
h3{font-size:17px;margin:30px 0 9px}
h4{font-size:15px;margin:22px 0 7px;color:var(--muted)}
h3.finding{padding:9px 13px;border-radius:6px;border-left:4px solid;margin-top:34px}
h3.crit{color:var(--crit);background:var(--crit-bg);border-color:var(--crit)}
h3.high{color:var(--high);background:var(--high-bg);border-color:var(--high)}
h3.med {color:var(--med); background:var(--med-bg); border-color:var(--med)}
h3.low {color:var(--low); background:var(--low-bg); border-color:var(--low)}
h3.arch{color:var(--arch);background:var(--arch-bg);border-color:var(--arch)}
p,li{max-width:74ch}
a{color:var(--accent)}
code{font:0.855em/1.5 ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
  background:var(--code-bg);padding:.12em .38em;border-radius:3px;
  overflow-wrap:break-word}
pre{background:var(--code-bg);border:1px solid var(--rule);border-radius:7px;
  padding:14px 16px;overflow-x:auto;margin:15px 0}
pre code{background:none;padding:0;font-size:12.9px;line-height:1.62;white-space:pre}
blockquote{margin:20px 0;padding:13px 18px;background:var(--code-bg);
  border-left:4px solid var(--accent);border-radius:0 6px 6px 0}
blockquote p{margin:0}
hr{border:0;border-top:1px solid var(--rule);margin:44px 0}
.tablewrap{overflow-x:auto;margin:18px 0;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;width:100%;min-width:460px;
  font:14px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif}
th,td{border:1px solid var(--rule);padding:8px 11px;text-align:left;vertical-align:top}
th{background:var(--code-bg);font-weight:650}
td code,th code{font-size:12.4px}
ul,ol{padding-left:24px}
li{margin:5px 0}
.masthead{border:1px solid var(--rule);background:var(--card);border-radius:10px;
  padding:24px 26px;margin-bottom:18px}
.masthead h1{margin:0 0 6px;border:0;padding:0;font-size:27px}
.masthead .sub{color:var(--muted);font:13.5px/1.6 ui-sans-serif,system-ui,sans-serif}
.chips{display:flex;flex-wrap:wrap;gap:7px;margin-top:15px}
.chip{font:11.5px/1 ui-sans-serif,system-ui,sans-serif;font-weight:700;
  padding:6px 11px;border-radius:20px;border:1px solid}
.chip.crit{color:var(--crit);background:var(--crit-bg);border-color:var(--crit)}
.chip.high{color:var(--high);background:var(--high-bg);border-color:var(--high)}
.chip.med {color:var(--med); background:var(--med-bg); border-color:var(--med)}
.chip.low {color:var(--low); background:var(--low-bg); border-color:var(--low)}
.banner{border:1px solid var(--crit);background:var(--crit-bg);color:var(--crit);
  border-radius:9px;padding:15px 19px;margin:18px 0 8px;
  font:14px/1.6 ui-sans-serif,system-ui,sans-serif}
.banner b{font-weight:750}
#themer{position:fixed;top:12px;right:14px;z-index:9;background:var(--card);
  color:var(--muted);border:1px solid var(--rule);border-radius:18px;
  padding:6px 13px;cursor:pointer;
  font:11.5px/1 ui-sans-serif,system-ui,sans-serif}
#themer:hover{color:var(--accent);border-color:var(--accent)}
@media (max-width:900px){
  .wrap{grid-template-columns:1fr}
  nav{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--rule);
    padding:18px 20px}
  main{padding:26px 20px 80px}
  p,li{max-width:none}
}
@media print{
  nav,#themer{display:none}
  .wrap{display:block;max-width:none}
  main{padding:0}
  body{background:#fff;color:#000;font-size:10.5pt}
  pre,blockquote,table{break-inside:avoid}
  h1,h2,h3{break-after:avoid}
  h1{page-break-before:always} h1:first-of-type{page-break-before:avoid}
  a{color:#000;text-decoration:none}
}
"""

JS = """
(function(){
  var r=document.documentElement, b=document.getElementById('themer');
  function cur(){ return r.getAttribute('data-theme') ||
    (matchMedia('(prefers-color-scheme:dark)').matches?'dark':'light'); }
  function paint(){ b.textContent = cur()==='dark' ? 'Light' : 'Dark'; }
  b.addEventListener('click', function(){
    r.setAttribute('data-theme', cur()==='dark'?'light':'dark'); paint();
  });
  paint();
  // wrap tables so wide ones scroll instead of pushing the page sideways
  document.querySelectorAll('main table').forEach(function(t){
    if(t.parentNode.classList.contains('tablewrap')) return;
    var d=document.createElement('div'); d.className='tablewrap';
    t.parentNode.insertBefore(d,t); d.appendChild(t);
  });
})();
"""

MASTHEAD = """
<div class="masthead">
  <h1>ACHILLES / JARVIS v5.36</h1>
  <div class="sub">
    Security &amp; quality audit, and remediation handoff<br>
    <code>jarvis_v536_2.py</code> (14,453 lines) &middot;
    <code>worldview_25.html</code> (4,281 lines)<br>
    Audited 26 July 2026 &middot; branch <code>claude/security-quality-audit-4ya46b</code>
  </div>
  <div class="chips">
    <span class="chip crit">6 Critical</span>
    <span class="chip high">11 High</span>
    <span class="chip med">15 Medium</span>
    <span class="chip low">12 Low</span>
  </div>
</div>
<div class="banner">
  <b>Read first.</b> The <code>:7778</code> proxy binds <code>0.0.0.0</code> with wildcard CORS
  and no authentication. Its routes expose API keys, calendar and email content, uncapped
  Anthropic spend, an open SSRF, and the full LLM brain with all its tools &mdash; reachable both
  from the LAN/tailnet and from any web page open in a browser on the host.
  Phase&nbsp;0 (&sect;&nbsp;Prioritised remediation plan) closes every remote path in ~150 lines.
</div>
"""

doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACHILLES v5.36 — Security Audit &amp; Handoff</title>
<style>{CSS}</style>
</head>
<body>
<button id="themer" type="button">Dark</button>
<div class="wrap">
<nav>{nav_html}</nav>
<main>
{MASTHEAD}
{audit}
<hr>
{handoff}
</main>
</div>
<script>{JS}</script>
</body>
</html>
"""

OUT.write_text(doc, encoding="utf-8")
print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
