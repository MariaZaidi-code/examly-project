p = r'C:\Users\Go\examly-project\webapp\frontend.html'
s = open(p, encoding='utf-8').read()

# Replace the quizReview action with a render function call
old = '''  quizReview:async t=>{
   const id=+t.dataset.id;
   const q=await api("/quizzes/"+id);
   S.quiz={id:q.id,qs:q.questions,i:q.questions.length,fb:null,score:q.correct,celebrated:true,review:true};
   // show all as reviewed: set i to length (triggers result) but we want review mode
   S.quiz.i=0; S.quiz.reviewMode=true;
   paintQuiz();
  },'''
new = '''  quizReview:async t=>{
   const id=+t.dataset.id;
   const q=await api("/quizzes/"+id);
   const box=$("#quizBox");
   const qs=q.questions||[];
   const score=q.total?Math.round((q.correct||0)/q.total*100):0;
   box.innerHTML='<div class="panel"><div class="ph2"><span>Review · Quiz #'+q.id+'</span><span>'+esc(q.correct||0)+'/'+q.total+' correct ('+score+'%)</span></div>'+
     qs.map((qq,i)=>'<div class="quiz-review-q"><div class="quiz-review-num">Q'+(i+1)+'</div><div class="quiz-review-body"><div class="quiz-review-prompt">'+esc(qq.prompt)+'</div><div class="quiz-review-opts">'+(qq.options||[]).map((o,k)=>'<div class="quiz-review-opt '+(k===qq.correct_index?"correct":"")+(k===qq.chosen&&k!==qq.correct_index?"wrong":"")+'">'+esc(o)+(k===qq.correct_index?" ✓":"")+'</div>').join("")+(qq.explanation?'<div class="quiz-review-exp">'+esc(qq.explanation)+'</div>':'')+(qq.source?'<div class="quiz-review-src">Source: '+esc(qq.source.file)+', p. '+qq.source.page+'</div>':'')+'</div></div>').join("")+
     '<div style="margin-top:12px"><button class="btn" data-act="quizNew">Back to new quiz</button><button class="btn sm" data-act="quizHistory" style="margin-left:8px">History</button></div></div>';
  },'''
assert old in s
s = s.replace(old, new, 1)

open(p, 'w', encoding='utf-8').write(s)
print('done')
