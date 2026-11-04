(function(){
  var root=document.documentElement;
  var tb=document.getElementById('theme');
  if(tb)tb.onclick=function(){
    var cur=root.dataset.theme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    var next=cur==='dark'?'light':'dark';root.dataset.theme=next;
    try{localStorage.setItem('theme',next)}catch(e){}
  };
  var mb=document.getElementById('menu'),nav=document.getElementById('nav');
  if(mb)mb.onclick=function(){nav.classList.toggle('open')};

  // نرمال‌سازی متن فارسی برای جستجو
  function norm(s){return (s||'').toLowerCase().replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[‌ً-ْ]/g,' ').replace(/[۰-۹]/g,function(d){return '۰۱۲۳۴۵۶۷۸۹'.indexOf(d)})}

  // جستجوی کل سایت
  var q=document.getElementById('q');
  if(q){
    var data=[],box=document.getElementById('results');
    function esc(s){return s.replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
    function run(){
      var words=norm(q.value).split(/\s+/).filter(Boolean);
      if(!words.length){box.innerHTML='';return}
      var res=data.map(function(d){
        var hay=norm(d.t+' '+d.d+' '+d.g+' '+d.c+' '+d.x),score=0;
        for(var i=0;i<words.length;i++){if(hay.indexOf(words[i])<0)return null;score+=norm(d.t).indexOf(words[i])>=0?5:1}
        return {d:d,s:score}}).filter(Boolean).sort(function(a,b){return b.s-a.s});
      box.innerHTML=res.length?res.map(function(r){return '<div class="r"><a href="'+r.d.u+'"><b>'+esc(r.d.t)+'</b></a><small>'+esc(r.d.c)+'</small><div>'+esc(r.d.d)+'</div></div>'}).join(''):'<p class="empty">نتیجه‌ای پیدا نشد.</p>';
    }
    fetch('/search-index.json').then(function(r){return r.json()}).then(function(j){
      data=j;var p=new URLSearchParams(location.search).get('q');if(p)q.value=p;run()});
    q.addEventListener('input',run);
  }

  // فیلتر کتابخانه
  var lib=document.getElementById('lib');
  if(lib){
    var lq=document.getElementById('lq'),lc=document.getElementById('lcat'),lt=document.getElementById('ltype'),
        items=[].slice.call(lib.children),em=document.getElementById('lib-empty');
    function f(){
      var w=norm(lq.value).split(/\s+/).filter(Boolean),n=0;
      items.forEach(function(el){
        var ok=(!lc.value||el.dataset.cat===lc.value)&&(!lt.value||el.dataset.type===lt.value)&&w.every(function(x){return norm(el.dataset.text).indexOf(x)>=0});
        el.hidden=!ok;if(ok)n++});
      em.hidden=n>0;
    }
    [lq,lc,lt].forEach(function(e){e.addEventListener('input',f)});
  }
})();
