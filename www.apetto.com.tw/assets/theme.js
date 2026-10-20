(function(){
var b=document.querySelector('.burger'),mm=document.querySelector('.mobile-menu');
function openMenu(){document.body.classList.remove('menu-closing');document.body.classList.add('menu-open');if(b)b.setAttribute('aria-expanded','true');}
function closeMenu(){if(!document.body.classList.contains('menu-open'))return;document.body.classList.remove('menu-open');document.body.classList.add('menu-closing');
 if(b)b.setAttribute('aria-expanded','false');setTimeout(function(){document.body.classList.remove('menu-closing');},240);}
if(b&&mm){b.addEventListener('click',function(){if(document.body.classList.contains('menu-open'))closeMenu();else openMenu();});
 mm.querySelectorAll('.mm-close,a').forEach(function(el){el.addEventListener('click',closeMenu);});
 mm.addEventListener('click',function(e){if(e.target===mm)closeMenu();});
 document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenu();});}
/* swipe right opens the menu, swipe left closes it (phones only; horizontal thumbnail strips are left alone) */
var sx=0,sy=0,swiping=false;
document.addEventListener('touchstart',function(e){var t=e.touches[0];sx=t.clientX;sy=t.clientY;swiping=!e.target.closest('.thumbs,.lang-row,input,textarea');},{passive:true});
document.addEventListener('touchend',function(e){if(!swiping||!b||getComputedStyle(b).display==='none')return;var t=e.changedTouches[0],dx=t.clientX-sx,dy=t.clientY-sy;
 if(Math.abs(dx)<70||Math.abs(dy)>60||Math.abs(dy)>Math.abs(dx)*0.6)return;
 if(dx>0&&!document.body.classList.contains('menu-open'))openMenu();else if(dx<0)closeMenu();},{passive:true});
var hd=document.querySelector('.hd');function sh(){if(hd)hd.classList.toggle('scrolled',window.scrollY>8);}
window.addEventListener('scroll',sh,{passive:true});sh();
var main=document.getElementById('main-defer-image');
document.querySelectorAll('#image-additional a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var img=a.querySelector('img');
 if(main&&img)main.src=a.getAttribute('href')||img.src;document.querySelectorAll('#image-additional li').forEach(function(l){l.classList.remove('cur');});a.parentNode.classList.add('cur');});});
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -6% 0px'});
 document.querySelectorAll('.rv').forEach(function(el){io.observe(el);});}else{document.querySelectorAll('.rv').forEach(function(el){el.classList.add('in');});}
})();
