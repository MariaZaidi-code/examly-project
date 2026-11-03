# Demo transcript
LLM: offline-rule-policy (deterministic stand-in, not an LLM)  |  today: 2026-11-03  |  MCP tools: ['get_weak_topics', 'record_quiz_result', 'generate_revision_plan', 'save_revision_plan', 'replan', 'mark_session_done']

## Session 1 (Monday): RAG + short-term memory (follow-up) + MCP tool + long-term writes

**You:** Explain third normal form
> tool `search_notes` via local args={"query": "Explain third normal form"}
> result: {"hits": [{"n": 1, "source": "dbms_normalization.md", "heading": "Third normal form", "chunk": 3, "score": 1.246, "text": "Database Systems: Normalization / Third normal form :: Third normal form (3NF) removes transitive dependenc...
**Agent:** From your notes: Third normal form (3NF) removes transitive dependencies so that non key attributes depend only on the primary key. [1] First normal form (1NF) requires atomic attribute values: no repeating groups and no nested relations. [2]

Sources:
[1] dbms_normalization.md / Third normal form (score 1.246)
[2] dbms_normalization.md / First normal form (score 1.108)

**You:** Give me an example of it
> tool `search_notes` via local args={"query": "Third normal form Give me an example of it"}
> result: {"hits": [{"n": 1, "source": "dbms_normalization.md", "heading": "Third normal form", "chunk": 3, "score": 1.037, "text": "Database Systems: Normalization / Third normal form :: Third normal form (3NF) removes transitive dependenc...
**Agent:** From your notes: Third normal form (3NF) removes transitive dependencies so that non key attributes depend only on the primary key. [1] First normal form (1NF) requires atomic attribute values: no repeating groups and no nested relations. [2]

Sources:
[1] dbms_normalization.md / Third normal form (score 1.037)
[2] dbms_normalization.md / First normal form (score 1.015)

**You:** Who won the football world cup?
> tool `search_notes` via local args={"query": "Who won the football world cup?"}
> result: {"hits": []}
**Agent:** I could not find this in your notes, so I will not guess. Try uploading material that covers it or rephrase the question.

**You:** My name is Ayesha
> tool `remember_fact` via local args={"kind": "profile", "content": "My name is Ayesha"}
> result: {"stored": true}
**Agent:** Noted, I will remember that in future sessions.

**You:** I struggle with deadlock handling
> tool `remember_fact` via local args={"kind": "difficulty", "content": "I struggle with deadlock handling"}
> result: {"stored": true}
> long-term memory retrieved: ['My name is Ayesha']
**Agent:** Noted, I will remember that in future sessions.

**You:** I scored 3/8 on deadlock handling
> tool `record_quiz_result` via MCP args={"user_id": "ayesha", "topic": "deadlock handling", "correct": 3, "total": 8}
> result: {"ok": true, "data": {"recorded": true, "topic": "deadlock handling", "accuracy_pct": 38, "answers": 8}}
> long-term memory retrieved: ['My name is Ayesha', 'I struggle with deadlock handling']
**Agent:** Recorded. Your accuracy on deadlock handling is now 38% over 8 answers.

**You:** I scored 5/9 on transactions
> tool `record_quiz_result` via MCP args={"user_id": "ayesha", "topic": "transactions", "correct": 5, "total": 9}
> result: {"ok": true, "data": {"recorded": true, "topic": "transactions", "accuracy_pct": 56, "answers": 9}}
> long-term memory retrieved: ['My name is Ayesha']
**Agent:** Recorded. Your accuracy on transactions is now 56% over 9 answers.

**You:** My exam is on 15 Nov
> tool `remember_fact` via local args={"kind": "exam", "content": "exam date 2026-11-15 (My exam is on 15 Nov)"}
> result: {"stored": true}
> long-term memory retrieved: ['My name is Ayesha']
**Agent:** Noted, I will remember that in future sessions.

**You:** quiz me
> tool `get_weak_topics` via MCP args={"user_id": "ayesha"}
> result: {"ok": true, "data": {"user_id": "ayesha", "weak_topics": [{"topic": "deadlock handling", "accuracy_pct": 38, "answers": 8}, {"topic": "transactions", "accuracy_pct": 56, "answers": 9}], "note": "empty list means no quiz results r...
> tool `search_notes` via local args={"query": "deadlock handling"}
> result: {"hits": [{"n": 1, "source": "os_deadlocks.md", "heading": "Coffman conditions", "chunk": 1, "score": 0.412, "text": "Operating Systems: Deadlock Handling / Coffman conditions :: Deadlock requires four conditions at once: mutual e...
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-15 (My exam is on 15 Nov)']
**Agent:** Practice question (targeting your weakest topic, deadlock handling, at 38%):
"Deadlock requires four _____ at once: mutual exclusion, hold and wait, no preemption, and circular wait."
What word fills the blank? Answer and I will check it against your notes [1].

Sources:
[1] os_deadlocks.md / Coffman conditions

## Session 2 (new session, new agent object): long-term memory retrieved; plan needs human confirmation

_short-term history at start of session 2: []_

**You:** Make me a revision plan
> tool `get_weak_topics` via MCP args={"user_id": "ayesha"}
> result: {"ok": true, "data": {"user_id": "ayesha", "weak_topics": [{"topic": "deadlock handling", "accuracy_pct": 38, "answers": 8}, {"topic": "transactions", "accuracy_pct": 56, "answers": 9}], "note": "empty list means no quiz results r...
> tool `generate_revision_plan` via MCP args={"user_id": "ayesha", "exam_date": "2026-11-15", "today": "2026-11-03"}
> result: {"ok": true, "data": {"plan_id": 1, "status": "proposed", "exam_date": "2026-11-15", "items": [{"date": "2026-11-04", "topic": "deadlock handling", "minutes": 45, "status": "planned"}, {"date": "2026-11-05", "topic": "transactions...
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-15 (My exam is on 15 Nov)']
**Agent:** Proposed plan 1 for your exam on 2026-11-15, weakest topics first:
- 2026-11-04: deadlock handling (45 min)
- 2026-11-05: transactions (45 min)
- 2026-11-06: deadlock handling (45 min)
- 2026-11-07: transactions (45 min)
- 2026-11-08: deadlock handling (45 min)
- 2026-11-09: transactions (45 min)
- 2026-11-10: deadlock handling (45 min)
- 2026-11-11: transactions (45 min)
- 2026-11-12: mixed practice and light review (45 min)
- 2026-11-13: mixed practice and light review (45 min)

Nothing is saved yet. Reply 'confirm' to save this plan, or tell me what to change.

**You:** yes confirm
> tool `save_revision_plan` via MCP args={"user_id": "ayesha", "plan_id": 1, "confirmed": true}
> result: {"ok": true, "data": {"plan_id": 1, "status": "saved", "sessions": 10}}
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-15 (My exam is on 15 Nov)']
**Agent:** Saved. Your plan (id 1) now has 10 sessions.

## Replanning after a change event: exam moved earlier

**You:** My exam has been moved to 11 Nov
> tool `replan` via MCP args={"user_id": "ayesha", "new_exam_date": "2026-11-11", "today": "2026-11-05"}
> result: {"ok": true, "data": {"plan_id": 2, "status": "proposed", "exam_date": "2026-11-11", "kept_completed_sessions": 1, "items": [{"date": "2026-11-04", "topic": "deadlock handling", "minutes": 45, "status": "done"}, {"date": "2026-11-...
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-15 (from confirmed plan)']
**Agent:** Proposed plan 2 for your exam on 2026-11-11, weakest topics first: Kept 1 completed sessions.
- 2026-11-04: deadlock handling (45 min)
- 2026-11-06: deadlock handling (45 min)
- 2026-11-07: transactions (45 min)
- 2026-11-08: mixed practice and light review (45 min)
- 2026-11-09: mixed practice and light review (45 min)

Nothing is saved yet. Reply 'confirm' to save this plan, or tell me what to change.

**You:** confirm
> tool `save_revision_plan` via MCP args={"user_id": "ayesha", "plan_id": 2, "confirmed": true}
> result: {"ok": true, "data": {"plan_id": 2, "status": "saved", "sessions": 5}}
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-15 (from confirmed plan)']
**Agent:** Saved. Your plan (id 2) now has 5 sessions.

## Error handling: invalid date

**You:** My exam has been moved to 2026-11-01
> tool `replan` via MCP args={"user_id": "ayesha", "new_exam_date": "2026-11-01", "today": "2026-11-05"}
> result: {"ok": false, "error": "Error executing tool replan: new_exam_date must be after today"}
> long-term memory retrieved: ['My name is Ayesha', 'exam date 2026-11-11 (from confirmed plan)']
**Agent:** I could not build the plan: Error executing tool replan: new_exam_date must be after today
