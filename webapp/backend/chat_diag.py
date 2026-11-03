"""Diagnostic: drive the AI Study Assistant in a real browser.

Sends a question, captures console errors, network failures and the chat DOM,
and screenshots the view so we can see what breaks.
"""
import sys, time, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import requests
from app import db, auth

BASE = "http://127.0.0.1:8000"
OUT = ROOT / "ui_shots"
OUT.mkdir(exist_ok=True)

with db.conn() as c:
    user = db.one(c, "SELECT * FROM users ORDER BY id LIMIT 1")
    token, _ = auth.create_session(c, user["id"])

console, netfail, responses = [], [], []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
    ctx.add_cookies([{"name": auth.COOKIE, "value": token, "url": BASE}])
    page = ctx.new_page()
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}") if m.type in ("error", "warning") else None)
    page.on("requestfailed", lambda r: netfail.append(f"{r.method} {r.url} -> {r.failure}"))
    page.on("response", lambda r: responses.append(f"{r.status} {r.url}") if "/api/" in r.url else None)

    page.goto(BASE + "/", wait_until="networkidle")
    page.click("nav button:nth-child(2)")          # AI Study Assistant
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "d0_assistant_initial.png"))
    print("status pill:", page.text_content("#aStatus"))
    print("doc count:", page.text_content("#aDocN"))
    geo = page.evaluate("""() => { const l=document.querySelector('#chatLog');
        return {h:Math.round(l.getBoundingClientRect().height), client:l.clientHeight,
                scroll:l.scrollHeight, top:Math.round(l.getBoundingClientRect().top)}; }""")
    print("chat geometry before:", geo, "-> scrollable:", geo["scroll"] > geo["client"])

    # ask one question (geometry is what matters; history already has many)
    for q in ["What is a primary key?"]:
        page.fill("#chatIn", q)
        page.click("#chatSend")
        page.wait_for_timeout(1000)
        # wait for the placeholder to be replaced (up to 60s - LLM budget)
        t0 = time.time()
        while time.time() - t0 < 70:
            txt = page.text_content("#chatLog") or ""
            if "Searching your notes..." not in txt:
                break
            page.wait_for_timeout(500)
        print(f"after {q!r}: msgs={page.eval_on_selector_all('#chatLog .msg', 'els => els.length')} "
              f"height={page.eval_on_selector('#chatLog', 'el => el.getBoundingClientRect().height'):.0f} "
              f"pageScrollY={page.evaluate('window.scrollY')}")
        page.wait_for_timeout(300)

    page.screenshot(path=str(OUT / "d1_assistant_after_3q.png"))
    fin = page.evaluate("""() => {
        const l=document.querySelector('#chatLog'), send=document.querySelector('#chatSend');
        const r=send.getBoundingClientRect(), lr=l.getBoundingClientRect();
        return {h:Math.round(lr.height), client:l.clientHeight, scroll:l.scrollHeight,
                pageH:Math.round(document.body.scrollHeight), scrollY:Math.round(window.scrollY),
                sendBottom:Math.round(r.bottom), vh:window.innerHeight,
                ah:document.querySelectorAll('#chatLog .ah').length,
                rawHash:/#\\w/.test(l.textContent),
                atBottom: Math.abs(l.scrollHeight - l.clientHeight - l.scrollTop) < 60}; }""")
    print("final geometry:", fin)
    checks = {
        "chat log height capped (< 100vh-250)": fin["h"] < fin["vh"] - 250,
        "chat log internally scrollable": fin["scroll"] > fin["client"],
        "page does not stretch (fits ~1 viewport)": fin["pageH"] <= fin["vh"] + 40,
        "send input visible without page scroll": fin["sendBottom"] < fin["vh"] and fin["scrollY"] < 50,
        "newest message auto-scrolled into view": fin["atBottom"],
        "markdown headers rendered (no raw ##)": fin["ah"] > 0 and not fin["rawHash"],
    }
    for k, v in checks.items():
        print(("  PASS  " if v else "  FAIL  ") + k)
    ctx.close(); browser.close()

print("console errors/warnings:", console or "none")
print("failed requests:", netfail or "none")
print("api responses:")
for r in responses: print("  ", r)
