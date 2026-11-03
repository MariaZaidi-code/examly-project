p = r'C:\Users\Go\examly-project\webapp\frontend.html'
s = open(p, encoding='utf-8').read()

s = s.replace('const mark=ok?"✓":no?"✗":"";', 'const mark="";', 1)

old = '<span class="quiz-opt-mark">'+ '""' + '</span>'  # placeholder, won't match
# build the actual string
old = '<span class="quiz-opt-mark">' + '"+mark+"' + '</span>'
# The actual in file is: '<span class="quiz-opt-mark">'+mark+'</span>'
old = "<span class=\"quiz-opt-mark\">'+mark+'</span>"
assert old in s, 'mark span not found'
s = s.replace(old, '', 1)

s = s.replace('(fb.correct?"✓ Correct!":"✗ Not quite.")', '(fb.correct?"Correct":"Incorrect")', 1)
# in case the above form differs
s = s.replace('(fb.correct?"\\u2713 Correct!":"\\u2717 Not quite.")', '(fb.correct?"Correct":"Incorrect")', 1)

open(p, 'w', encoding='utf-8').write(s)
print('done')
