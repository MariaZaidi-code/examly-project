"""UI verification with Playwright: screenshots the key states.

1. Live workspace (account 'maria'): sidebar name, greeting, checklist.
2. Fresh empty workspace on port 8001: the 'upload your documents' hero.
"""
import sys, time, pathlib, subprocess, tempfile, socket
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "ui_shots"
OUT.mkdir(exist_ok=True)

sys.path.insert(0, str(ROOT))
import requests
from app import db, auth

BASE_LIVE = "http://127.0.0.1:8000"


def live_cookie():
    with db.conn() as c:
        user = db.one(c, "SELECT * FROM users ORDER BY id LIMIT 1")
        token, _ = auth.create_session(c, user["id"])
    return token


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def start_fresh_server(port, db_path):
    env = dict(**{k: v for k, v in __import__("os").environ.items()},
               EXAMLY_DB=str(db_path), EXAMLY_ENV_FILE=str(ROOT / "no_such.env"), EXAMLY_DISABLE_LLM="1")
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)],
                            cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            requests.get(f"http://127.0.0.1:{port}/api/auth/status", timeout=1); return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("fresh server did not start")


def main():
    shots = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        # --- 1. live workspace -------------------------------------------------
        ctx = browser.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
        ctx.add_cookies([{"name": auth.COOKIE, "value": live_cookie(), "url": BASE_LIVE}])
        page = ctx.new_page()
        page.goto(BASE_LIVE + "/", wait_until="networkidle")
        page.wait_for_timeout(1600)                      # count-up + rise animations
        sb_name = page.text_content("#sbName").strip()
        greet = page.text_content("#ovGreet").strip()
        ov_name = page.text_content("#ovName").strip()
        intro_hidden = page.eval_on_selector("#ovIntro", "el => el.hidden")
        print(f"live: sidebar={sb_name!r} greeting={greet!r} card={ov_name!r} intro_hidden={intro_hidden}")
        assert sb_name == "Maria" and "Maria" in greet and ov_name == "Maria", "name not shown!"
        p1 = OUT / "01_overview_live.png"; page.screenshot(path=str(p1), full_page=False); shots.append(p1)

        page.click('nav button:nth-child(6)')            # Study Materials
        page.wait_for_timeout(900)
        dz = page.text_content("#mDz").strip()
        print("dropzone:", dz[:60])
        assert "Drop your file here" in dz
        p2 = OUT / "02_materials_dropzone.png"; page.screenshot(path=str(p2)); shots.append(p2)
        ctx.close()

        # --- 2. brand-new empty workspace (upload prompt) ----------------------
        port = free_port()
        tmpdb = pathlib.Path(tempfile.mkdtemp()) / "fresh.db"
        proc = start_fresh_server(port, tmpdb)
        try:
            base = f"http://127.0.0.1:{port}"
            ctx = browser.new_context(viewport={"width": 1440, "height": 940}, device_scale_factor=2)
            page = ctx.new_page()
            page.goto(base + "/login", wait_until="networkidle")
            page.wait_for_timeout(400)
            p0 = OUT / "00_login_first_run.png"; page.screenshot(path=str(p0)); shots.append(p0)
            # create the account -> straight into the empty dashboard
            page.fill("#u", "maria"); page.fill("#p", "secret123")
            page.click("#b"); page.wait_for_url(base + "/", timeout=15000)
            page.wait_for_timeout(1600)
            intro_hidden = page.eval_on_selector("#ovIntro", "el => el.hidden")
            hero = page.text_content("#ovIntro").strip()
            print(f"fresh: intro_hidden={intro_hidden} hero={hero[:70]!r}")
            assert not intro_hidden and "Upload your first documents" in hero, "empty-state hero missing!"
            p3 = OUT / "03_empty_dashboard_upload_prompt.png"; page.screenshot(path=str(p3)); shots.append(p3)
            # and the upload screen it leads to
            page.click("#ovIntro .btn.p"); page.wait_for_timeout(900)
            p4 = OUT / "04_upload_screen.png"; page.screenshot(path=str(p4)); shots.append(p4)
            ctx.close()
        finally:
            proc.terminate()

        browser.close()

    print("screenshots:", ", ".join(p.name for p in shots))
    print("UI CHECKS PASSED")


if __name__ == "__main__":
    main()
