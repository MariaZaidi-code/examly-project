import sys, time, pathlib
from playwright.sync_api import sync_playwright
ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "ui_shots"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
from app import db, auth
BASE = "http://127.0.0.1:8000"
with db.conn() as c:
    user = db.one(c, "SELECT * FROM users ORDER BY id LIMIT 1")
    token, _ = auth.create_session(c, user["id"])
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
    ctx.add_cookies([{"name": auth.COOKIE, "value": token, "url": BASE}])
    page = ctx.new_page()
    page.goto(BASE + "/", wait_until="networkidle")
    page.click("nav button:nth-child(8)")  # Flashcards (8th? let's check)
    page.wait_for_timeout(1500)
    page.screenshot(path=str(OUT / "fc_new.png"))
    # flip
    page.click("#fsb")
    page.wait_for_timeout(500)
    page.screenshot(path=str(OUT / "fc_flipped.png"))
    # rate good
    page.click('[data-act="fcGood"]')
    page.wait_for_timeout(1200)
    page.screenshot(path=str(OUT / "fc_next.png"))
    ctx.close(); browser.close()
with db.conn() as c:
    c.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
print("done")
