"""UI verification for the Flashcards document selector.

Checks: selector lists indexed documents, scoping changes the deck/scope
label, the Build button appears for a specific file, and building cards from
that file produces cards sourced only from it.
"""
import sys, time, pathlib
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "ui_shots"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
import requests
from app import db, auth

BASE = "http://127.0.0.1:8000"
ok = True

def check(label, cond, extra=""):
    global ok
    ok = ok and bool(cond)
    print(("  PASS  " if cond else "  FAIL  ") + label + ((" -> " + str(extra)) if extra else ""))

with db.conn() as c:
    user = db.one(c, "SELECT * FROM users ORDER BY id LIMIT 1")
    token, _ = auth.create_session(c, user["id"])
    docs = db.rows(c, "SELECT id, filename FROM documents WHERE status='indexed' ORDER BY id")

sess = requests.Session()
sess.cookies.set(auth.COOKIE, token)

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
    ctx.add_cookies([{"name": auth.COOKIE, "value": token, "url": BASE}])
    page = ctx.new_page()
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    page.goto(BASE + "/", wait_until="networkidle")
    page.click("nav button:nth-child(8)")               # Flashcards
    page.wait_for_timeout(1500)

    opts = page.eval_on_selector_all("#fcDoc option", "els => els.map(e => [e.value, e.textContent])")
    check("selector lists All + every indexed doc", len(opts) == 1 + len(docs), f"{len(opts)} opts vs {1+len(docs)} docs")
    check("scope label starts at 'all documents'", page.text_content("#fcScopeN").strip() == "all documents")
    check("build button hidden for 'All documents'", not page.is_visible("#fcBuild"))
    all_total = page.text_content("#fcStats").strip()[:80]

    # scope to a document
    target = next(d for d in docs if "normalization" in d["filename"].lower()) if any("normalization" in d["filename"].lower() for d in docs) else docs[0]
    page.select_option("#fcDoc", str(target["id"]))
    page.wait_for_timeout(1200)
    check("scope label shows the selected file", target["filename"] in page.text_content("#fcScopeN"), page.text_content("#fcScopeN"))
    check("build button appears for a specific file", page.is_visible("#fcBuild"))
    scoped_total = page.text_content("#fcStats").strip()[:80]
    print(f"       stats all={all_total!r} scoped={scoped_total!r}")
    page.screenshot(path=str(OUT / "f0_flashcards_scoped.png"))

    # build cards from that file, then confirm the deck is sourced only from it
    before = sess.get(BASE + "/api/flashcards", params={"document_id": target["id"]}).json()["total"]
    page.click("#fcBuild")
    page.wait_for_timeout(2500)
    after = sess.get(BASE + "/api/flashcards", params={"document_id": target["id"]}).json()["total"]
    check("building cards from the file increases its deck", after > before, f"{before} -> {after}")
    f = sess.get(BASE + "/api/flashcards", params={"document_id": target["id"]}).json()
    check("every card sourced from the selected file",
          all(c["source"]["file"] == target["filename"] for c in f["cards"]), f["scope"])
    page.screenshot(path=str(OUT / "f1_flashcards_built.png"))

    # back to all documents
    page.select_option("#fcDoc", "")
    page.wait_for_timeout(1000)
    check("reset to All documents", page.text_content("#fcScopeN").strip() == "all documents")
    check("no console errors", not errors, errors[:3])
    ctx.close(); browser.close()

print("RESULT:", "UI CHECKS PASSED" if ok else "FAILURES PRESENT")
sys.exit(0 if ok else 1)
