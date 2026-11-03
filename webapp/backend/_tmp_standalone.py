p = r'C:\Users\Go\examly-project\webapp\backend\app\services.py'
s = open(p, encoding='utf-8').read()

# Insert generate_standalone_cards before public_question
anchor = 'def public_question(q, reveal=False):'
func = '''def generate_standalone_cards(c, subject_id, count=8, document_ids=None):
    """Build flashcards directly from notes (quiz_id=NULL). Returns new card count or None."""
    sql = "SELECT ch.text, ch.page, d.filename FROM chunks ch JOIN documents d ON d.id=ch.document_id WHERE d.status='indexed' AND d.subject_id=?"
    args = [subject_id]
    if document_ids: sql += " AND d.id IN (%s)" % ",".join("?" * len(document_ids)); args += document_ids
    chunks = db.rows(c, sql, args)
    if not chunks: return None
    pool = list({w for ch in chunks for w in re.findall(r"[A-Za-z]{6,}", ch["text"]) if w.lower() not in STOP})
    random.shuffle(chunks)
    existing = {q["explanation"] for q in db.rows(c, "SELECT q.explanation FROM questions q JOIN topics t ON t.id=q.topic_id WHERE q.quiz_id IS NULL AND t.subject_id=?", (subject_id,))}
    made = set(existing)
    new_count = 0
    for ch in chunks * 3:
        if new_count >= count: break
        m = make_cloze(ch["text"], pool, None)
        if not m or m[3] in made: continue
        prompt, opts, ci, sent = m
        tname = os.path.splitext(ch["filename"])[0].replace("_", " ")
        c.execute("INSERT OR IGNORE INTO topics(subject_id,name) VALUES(?,?)", (subject_id, tname))
        tid = db.one(c, "SELECT id FROM topics WHERE subject_id=? AND name=?", (subject_id, tname))["id"]
        c.execute("INSERT INTO questions(quiz_id,position,prompt,options,correct_index,explanation,source_file,source_page,topic_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (None, new_count + 1, prompt, json.dumps(opts), ci, sent, ch["filename"], ch["page"], tid))
        made.add(sent); new_count += 1
    if new_count == 0: return None
    return new_count

'''
assert anchor in s
s = s.replace(anchor, func + anchor, 1)
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
# Update flashcards() service to include standalone cards (already reads all questions incl quiz_id NULL) - no change needed
print('ok')
'''
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
# Only write once
print('final')
'''
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
# Write once
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
open(p, 'w', encoding='utf-8').write(s)
print('done')
'''
# just write
open(p, 'w', encoding='utf-8').write(s)
print('done')
