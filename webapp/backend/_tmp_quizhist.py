p = r'C:\Users\Go\examly-project\webapp\frontend.html'
s = open(p, encoding='utf-8').read()

# Add history button to quiz setup
old = 'box.innerHTML=\'<div class="panel quiz-setup"><div class="quiz-setup-head"><div class="quiz-setup-mark"></div><div><div class="ph2" style="margin:0"><span>New quiz</span><span>Fill-in-the-blank from your notes</span></div><div class="s" style="font-size:12.5px;color:var(--ink3);margin-top:4px">Questions are generated from the sentences in your own materials.</div></div></div><div class="frm" style="margin-top:14px"><div><label class="lbl" for="qSub">Subject</label><select class="in" id="qSub">\'+subjOptions(S.subjects[0].id)+\'</select></div><div><label class="lbl" for="qCount">Questions</label><select class="in" id="qCount"><option>5</option><option selected>10</option><option>20</option></select></div><div><label class="lbl" for="qTopic">Focus on a topic (optional)</label><input class="in" id="qTopic" placeholder="e.g. Transactions"></div><div><button class="btn p" data-act="quizStart" style="width:100%">Start quiz →</button></div></div><div class="quiz-tips"><span>Tip: focus on a weak topic to target your gaps.</span></div></div>\';'
new = 'box.innerHTML=\'<div class="panel quiz-setup"><div class="quiz-setup-head"><div class="quiz-setup-mark"></div><div><div class="ph2" style="margin:0"><span>New quiz</span><span>Fill-in-the-blank from your notes</span></div><div class="s" style="font-size:12.5px;color:var(--ink3);margin-top:4px">Questions are generated from the sentences in your own materials.</div></div></div><div class="frm" style="margin-top:14px"><div><label class="lbl" for="qSub">Subject</label><select class="in" id="qSub">\'+subjOptions(S.subjects[0].id)+\'</select></div><div><label class="lbl" for="qCount">Questions</label><select class="in" id="qCount"><option>5</option><option selected>10</option><option>20</option></select></div><div><label class="lbl" for="qTopic">Focus on a topic (optional)</label><input class="in" id="qTopic" placeholder="e.g. Transactions"></div><div><button class="btn p" data-act="quizStart" style="width:100%">Start quiz →</button></div></div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px"><div class="quiz-tips" style="margin:0;flex:1"><span>Tip: focus on a weak topic to target your gaps.</span></div><button class="btn sm" data-act="quizHistory">History</button></div></div>\';'
assert old in s
s = s.replace(old, new, 1)

# Add quizHistory function after paintQuizSetup
old2 = '''function paintQuiz(){
 const z=S.quiz,box=$("#quizBox");'''
new2 = '''async function loadQuizHistory(){
 const box=$("#quizBox");
 box.innerHTML='<div class="panel"><div class="ph2"><span>Quiz history</span><span>Past attempts</span></div><div class="empty">Loading...</div></div>';
 const r=await api("/quizzes");
 const list=r.quizzes||[];
 if(!list.length){box.innerHTML='<div class="panel"><div class="ph2"><span>Quiz history</span></div><div class="empty">No quizzes yet. Start one above.</div><button class="btn" data-act="quizNew">Back</button></div>';return;}
 box.innerHTML='<div class="panel"><div class="ph2"><span>Quiz history</span><span>'+list.length+' quiz'+(list.length===1?"":"zes")+'</span></div>'+list.map(q=>'<div class="quiz-hist-row"><div class="quiz-hist-main"><b>Quiz #'+q.id+'</b><small>'+esc(q.subject||"Subject")+' · '+esc(fmtDate(q.created_at))+' · '+q.total+' questions · '+q.answered+' answered</small></div><div class="quiz-hist-score '+(q.score===null?"":q.score>=80?"good":q.score>=50?"mid":"low")+'">'+(q.score===null?"—":Math.round(q.score)+"%")+'</div><div class="sbtns"><button class="btn sm" data-act="quizReview" data-id="'+q.id+'">Review</button></div></div>').join("")+'<div style="margin-top:12px"><button class="btn" data-act="quizNew">Back to new quiz</button></div></div>';
}
function paintQuiz(){
 const z=S.quiz,box=$("#quizBox");'''
assert old2 in s
s = s.replace(old2, new2, 1)

# Add quizReview + quizHistory actions
old3 = '  quizNew:()=>{S.quiz=null;paintQuizSetup();},'
new3 = '''  quizHistory:()=>{S.quiz=null;loadQuizHistory().catch(fail);},
  quizReview:async t=>{
   const id=+t.dataset.id;
   const q=await api("/quizzes/"+id);
   S.quiz={id:q.id,qs:q.questions,i:q.questions.length,fb:null,score:q.correct,celebrated:true,review:true};
   // show all as reviewed: set i to length (triggers result) but we want review mode
   S.quiz.i=0; S.quiz.reviewMode=true;
   paintQuiz();
  },
  quizNew:()=>{S.quiz=null;paintQuizSetup();},'''
assert old3 in s
s = s.replace(old3, new3, 1)

open(p, 'w', encoding='utf-8').write(s)
print('done')
