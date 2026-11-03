"""Upload the six sample Database Systems notes and verify they are indexed correctly.

Usage (server must be running):
    python ingest_sample.py
    python ingest_sample.py --user ayesha --password secret123
    python ingest_sample.py --base http://127.0.0.1:8000 --subject "Database Systems"

Exits 0 only when all six documents are indexed with pages and chunks and the assistant
returns a grounded citation from one of them.
"""
import argparse, pathlib, sys, time
import requests

HERE = pathlib.Path(__file__).resolve().parent
DOCS = HERE / "sample_materials" / "database_systems"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--subject", default="Database Systems")
    ap.add_argument("--user")
    ap.add_argument("--password", default="")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args()

    files = sorted(DOCS.glob("*.md"))
    if len(files) != 6:
        print(f"expected 6 notes in {DOCS}, found {len(files)}")
        return 1

    s = requests.Session()
    if a.user:
        r = s.post(a.base + "/api/auth/login", json={"username": a.user, "password": a.password})
        if r.status_code != 200:
            print("login failed:", r.status_code, r.text[:200])
            return 1

    r = s.post(a.base + "/api/subjects", json={"name": a.subject})
    r.raise_for_status()
    sid = next(x["id"] for x in r.json() if x["name"] == a.subject)

    for f in files:
        r = s.post(a.base + "/api/materials",
                   files={"file": (f.name, f.read_bytes(), "text/markdown")},
                   data={"subject_id": sid})
        if r.status_code != 201:
            print("upload failed:", f.name, r.status_code, r.text[:200])
            return 1
        print("uploaded", f.name)

    docs = []
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        docs = s.get(a.base + "/api/materials", params={"subject_id": sid}).json()
        if docs and all(d["status"] != "indexing" for d in docs):
            break
        time.sleep(0.25)

    ok = True
    print(f"\n{'file':32} {'status':8} {'pages':>6} {'chunks':>7}")
    for d in sorted(docs, key=lambda x: x["filename"]):
        good = d["status"] == "indexed" and d["pages"] >= 1 and d["chunks"] >= 1
        ok = ok and good
        print(f"{d['filename']:32} {d['status']:8} {d['pages']:6} {d['chunks']:7}{'' if good else '   <- PROBLEM'}")

    names = {d["filename"] for d in docs}
    expected = {f.name for f in files}
    if names != expected:
        print("\ndocument set mismatch; missing:", sorted(expected - names), "extra:", sorted(names - expected))
        ok = False

    q = s.post(a.base + "/api/assistant/chat",
               json={"message": "Explain third normal form", "subject_id": sid}).json()
    cite = (q.get("citations") or [{}])[0].get("filename")
    grounded = bool(q.get("grounded")) and cite in names
    print("\nassistant grounded:", q.get("grounded"), "| first citation:", cite)
    ok = ok and grounded

    print("\nRESULT:", "all six documents indexed correctly" if ok else "ingestion verification FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
