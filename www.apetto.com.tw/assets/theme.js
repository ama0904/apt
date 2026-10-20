(function(){
var b=document.querySelector('.burger'),mm=document.querySelector('.mobile-menu');
function closeMenu(){document.body.classList.remove('menu-open');if(b)b.setAttribute('aria-expanded','false');}
if(b&&mm){b.addEventListener('click',function(){var o=document.body.classList.toggle('menu-open');b.setAttribute('aria-expanded',o?'true':'false');});
 mm.querySelectorAll('.mm-close,a').forEach(function(el){el.addEventListener('click',closeMenu);});
 document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenu();});}
var hd=document.querySelector('.hd');function sh(){if(hd)hd.classList.toggle('scrolled',window.scrollY>8);}
window.addEventListener('scroll',sh,{passive:true});sh();
var main=document.getElementById('main-defer-image');
document.querySelectorAll('#image-additional a').forEach(function(a){a.addEventListener('click',function(e){e.preventDefault();var img=a.querySelector('img');
 if(main&&img)main.src=a.getAttribute('href')||img.src;document.querySelectorAll('#image-additional li').forEach(function(l){l.classList.remove('cur');});a.parentNode.classList.add('cur');});});
if('IntersectionObserver' in window){var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target);}});},{rootMargin:'0px 0px -6% 0px'});
 document.querySelectorAll('.rv').forEach(function(el){io.observe(el);});}else{document.querySelectorAll('.rv').forEach(function(el){el.classList.add('in');});}
})();
