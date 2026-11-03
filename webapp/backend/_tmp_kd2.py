p = r'C:\Users\Go\examly-project\webapp\frontend.html'
s = open(p, encoding='utf-8').read()
needle = 'document.addEventListener("keydown",e=>{'
i = s.find(needle)
print(repr(s[i:i+400]))
open(r'C:\Users\Go\examly-project\webapp\backend\_kd.txt','w').write(repr(s[i:i+400]))
