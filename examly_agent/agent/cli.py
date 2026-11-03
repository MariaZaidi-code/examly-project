import argparse, json
from .agent import ExamAgent
ap = argparse.ArgumentParser(); ap.add_argument("--user", default="ayesha"); ap.add_argument("--session", default="s1"); ap.add_argument("--trace", action="store_true")
a = ap.parse_args()
ag = ExamAgent(a.user).new_session(a.session)
print(f"Examly agent ({ag.llm.name}). Ctrl-D to quit.")
try:
    while True:
        r = ag.ask(input("you> "))
        if a.trace: print(json.dumps([{k: v for k, v in s.items() if k != 'result'} for s in r["trace"]["steps"]], indent=1))
        print("agent>", r["answer"])
except (EOFError, KeyboardInterrupt): pass
finally: ag.close()
