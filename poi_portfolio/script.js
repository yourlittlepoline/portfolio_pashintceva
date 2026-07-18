const screens=[...document.querySelectorAll('.screen')];
function showScreen(id){screens.forEach(s=>s.classList.toggle('active',s.id===id));window.scrollTo({top:0,behavior:'smooth'});history.replaceState(null,'',id==='intro'?'#':'#'+id)}
document.addEventListener('click',e=>{const nav=e.target.closest('[data-target]');if(nav)showScreen(nav.dataset.target)});
const hash=location.hash.replace('#','');if(hash&&document.getElementById(hash))showScreen(hash);
const dialog=document.getElementById('lightbox'),dialogImg=document.getElementById('lightbox-img');document.querySelectorAll('figure img').forEach(img=>img.addEventListener('click',()=>{dialogImg.src=img.src;dialogImg.alt=img.alt;dialog.showModal()}));document.getElementById('lightbox-close').addEventListener('click',()=>dialog.close());dialog.addEventListener('click',e=>{if(e.target===dialog)dialog.close()});
