p = r'C:\Users\Go\examly-project\webapp\backend\app\services.py'
s = open(p, encoding='utf-8').read()

old = 'def _build_quiz(c, subject_id, chunks, count, topic, focus=None, quiz_id=None, existing_sents=None):'
new = 'def _build_quiz(c, subject_id, chunks, count, topic, focus=None, quiz_id=None, existing_sents=None, create_quiz=True):'
assert old in s
s = s.replace(old, new, 1)

old2 = '''    made = set(existing_sents or [])
    new_count = 0
    created = False
    if quiz_id is None:
        c.execute("INSERT INTO quizzes(subject_id,created_at) VALUES(?,?)", (subject_id, db.now_iso()))
        quiz_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        created = True'''
new2 = '''    made = set(existing_sents or [])
    new_count = 0
    created = False
    if create_quiz and quiz_id is None:
        c.execute("INSERT INTO quizzes(subject_id,created_at) VALUES(?,?)", (subject_id, db.now_iso()))
        quiz_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        created = True'''
assert old2 in s
s = s.replace(old2, new2, 1)

# failure delete: only if created (quiz exists)
old3 = '''    if new_count == 0:
        if created:
            c.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,))
        return None'''
new3 = '''    if new_count == 0:
        if created and quiz_id is not None:
            c.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,))
        return None'''
assert old3 in s
s = s.replace(old3, new3, 1)

# Add generate_flashcards function after generate_quiz
old4 = '    return None\n\n\ndef public_question'
new4 = '''    return None


def generate_flashcards(c, subject_id, count=8, document_ids=None):
    """Build standalone flashcards (quiz_id=NULL) directly from notes."""
    sql = "SELECT ch.text, ch.page, d.filename FROM chunks ch JOIN documents d ON d.id=ch.document_id WHERE d.status='indexed' AND d.subject_id=?"
    args = [subject_id]
    if document_ids: sql += " AND d.id IN (%s)" % ",".join("?" * len(document_ids)); args += document_ids
    chunks = db.rows(c, sql, args)
    if not chunks: return None
    existing = {q["explanation"] for q in db.rows(c, "SELECT explanation FROM questions WHERE quiz_id IS NULL AND subject_id=?", (subject_id,))}
    # subject_id not in questions; fetch via topics? Use all standalone cards for this subject's topics
    existing = {q["explanation"] for q in db.rows(c, "SELECT q.explanation FROM questions q JOIN topics t ON t.id=q.topic_id WHERE q.quiz_id IS NULL AND t.subject_id=?", (subject_id,))}
    attempts = []
    focus = None
    attempts.append((chunks, None, None))
    for pool_chunks, foc, label in attempts:
        qid = _build_quiz(c, subject_id, list(pool_chunks), count, label, foc, quiz_id=None, existing_sents=existing, create_quiz=False)
        if qid is not None or True:
            # standalone cards have quiz_id NULL but _build_quiz returns quiz_id (None for standalone) -> None on success too!
            pass
    # _build_quiz returns quiz_id which is None for standalone; check if cards were added
    cnt = db.one(c, "SELECT COUNT(*) n FROM questions q JOIN topics t ON t.id=q.topic_id WHERE q.quiz_id IS NULL AND t.subject_id=?", (subject_id,))["n"]
    return cnt if cnt > (len(existing)) else None

def public_question'''
# This approach is messy. Let me instead refactor _build_quiz to return a sentinel.
# Rewrite more cleanly: make _build_quiz return the number of new cards when standalone.
print('placeholder')
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
# Actually, let's not do this messy approach. Revert and do cleaner.
print('aborting - reverting')
open(p, 'w', encoding='utf-8').write(s)
'''
print('done')
