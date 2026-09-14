APP_HTML = r'''<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover" />
  <title>Домашние церкви Ижевска</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root{--bg:#050505;--card:#151515;--card2:#1d1d1d;--text:#fff;--muted:#aaa;--accent:#ff7a00;--line:#2a2a2a}
    *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Arial,sans-serif}
    .wrap{max-width:560px;margin:0 auto;padding:18px 16px 36px}.hero{padding:18px 0 8px}.eyebrow{font-size:12px;letter-spacing:.14em;color:#d2d2d2;text-transform:uppercase}
    h1{font-size:42px;line-height:.95;margin:12px 0 8px}.accent{color:var(--accent)} p{line-height:1.48}.muted{color:var(--muted)}
    .cta,.btn{border:0;border-radius:14px;background:var(--accent);color:#111;font-weight:800;padding:15px 16px;font-size:16px;width:100%;cursor:pointer}.btn.secondary{background:transparent;color:var(--accent);border:1px solid var(--accent)}
    .toolbar{display:flex;gap:8px;margin:14px 0}.toolbar button{flex:1;border:1px solid var(--line);background:var(--card);color:#fff;border-radius:12px;padding:11px 8px}.toolbar button.active{background:var(--accent);color:#111;border-color:var(--accent);font-weight:800}
    #map{height:300px;border-radius:18px;overflow:hidden;border:1px solid var(--line);margin-top:12px}.section-title{font-size:22px;margin:24px 0 10px}.filters{display:flex;gap:8px;overflow:auto;padding-bottom:6px}.chip{white-space:nowrap;border:1px solid var(--line);background:var(--card);color:#ddd;border-radius:999px;padding:9px 12px}.chip.active{background:var(--accent);color:#111;border-color:var(--accent)}
    .list{display:grid;gap:10px;margin-top:12px}.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:15px}.row{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}.title{font-weight:800;font-size:18px}.meta{color:#bdbdbd;font-size:14px;margin-top:6px}.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}.tag{font-size:12px;padding:6px 9px;border-radius:999px;background:#252525;color:#ddd}.linkbtn{background:none;border:0;color:var(--accent);font-weight:800;padding:8px 0;cursor:pointer}
    .detail{display:none}.detail.show{display:block}.main.hide{display:none}.back{background:none;border:0;color:#fff;padding:8px 0 16px;font-size:16px}.detail-box{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:16px;margin:12px 0}.actions{display:grid;gap:10px;margin-top:18px}.empty{padding:28px 10px;text-align:center;color:#aaa}
    .toast{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);background:#222;color:#fff;padding:11px 14px;border-radius:12px;display:none;z-index:9999}.toast.show{display:block}
  </style>
</head>
<body>
<div class="wrap">
  <div class="main" id="mainView">
    <section class="hero">
      <div class="eyebrow">Люди · Общение · Рост · Служение</div>
      <h1>ДОМАШНИЕ<br><span class="accent">ЦЕРКВИ</span></h1>
      <p class="muted">Настоящая церковь начинается не в здании, а в людях. Найдите домашнюю церковь рядом с вами.</p>
      <p class="muted">🧪 Группы с отметкой «Тестовая» содержат примерные адреса и вымышленных лидеров.</p><button class="cta" id="nearBtn">📍 Показать ближайшие ко мне</button>
    </section>

    <div class="toolbar">
      <button class="active" data-view="map">Карта</button>
      <button data-view="list">Список</button>
    </div>

    <div class="filters" id="filters"></div>
    <div id="map"></div>
    <div id="listWrap" style="display:none"><h2 class="section-title">Домашние церкви</h2><div class="list" id="churchList"></div></div>
  </div>

  <div class="detail" id="detailView">
    <button class="back" id="backBtn">← Назад</button>
    <div id="detailContent"></div>
  </div>
</div>
<div class="toast" id="toast"></div>
<script>
const tg=window.Telegram?.WebApp; if(tg){tg.ready();tg.expand();}
let churches=[];let selectedDistrict='Все районы';let map;let markers=[];let userMarker=null;let joining=false;
const byId=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function toast(msg){const el=byId('toast');el.textContent=msg;el.classList.add('show');setTimeout(()=>el.classList.remove('show'),4500)}
function hav(a,b,c,d){const R=6371,r=x=>x*Math.PI/180,da=r(c-a),db=r(d-b),q=Math.sin(da/2)**2+Math.cos(r(a))*Math.cos(r(c))*Math.sin(db/2)**2;return 2*R*Math.asin(Math.sqrt(q));}
function initMap(){if(!window.L){byId('map').textContent='Карта недоступна. Используйте список.';return}map=L.map('map').setView([56.8527,53.2115],12);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap'}).addTo(map);renderMarkers();}
function renderMarkers(items=filtered()){if(!map)return;markers.forEach(m=>map.removeLayer(m));markers=[];items.forEach(c=>{const m=L.marker([c.lat,c.lon]).addTo(map).bindPopup(`<b>${esc(c.name)}</b><br>${esc(c.district)}<br>${c.is_test?'Тестовая группа<br>':''}<button onclick="openChurch(${c.id})">Подробнее</button>`);markers.push(m)});}
function filtered(){return selectedDistrict==='Все районы'?churches:churches.filter(c=>c.district===selectedDistrict)}
function renderFilters(){const ds=['Все районы',...new Set(churches.map(c=>c.district))];byId('filters').replaceChildren();for(const d of ds){const b=document.createElement('button');b.className='chip '+(d===selectedDistrict?'active':'');b.textContent=d.replace(' район','');b.onclick=()=>{selectedDistrict=d;renderFilters();renderList();renderMarkers()};byId('filters').append(b)}}
function renderList(items=filtered()){byId('churchList').innerHTML=items.length?items.map(c=>`<div class="card"><div class="row"><div><div class="title">🏠 ${esc(c.name)}</div><div class="meta">${c.is_test?'🧪 Тестовая группа<br>':''}📍 ${esc(c.district)}<br>👤 ${esc(c.leader)}<br>🕒 ${esc(c.meeting)}<br>👥 ${c.participants} участников · ${esc(c.age)}</div></div><button class="linkbtn" onclick="openChurch(${c.id})">Подробнее →</button></div><div class="tags">${c.interests.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div></div>`).join(''):'<div class="empty">В этом районе пока нет групп.</div>'}
window.openChurch=async function(id){try{const r=await fetch('/api/churches/'+id);if(!r.ok)throw Error('Группа больше не доступна. Обновите каталог.');const c=await r.json();byId('mainView').classList.add('hide');byId('detailView').classList.add('show');const route=`https://yandex.ru/maps/?rtext=~${c.lat},${c.lon}&rtt=auto`;byId('detailContent').innerHTML=`<div class="eyebrow">${c.is_test?'🧪 Тестовая группа':'Домашняя церковь'}</div><h1 style="font-size:34px">${esc(c.name)}</h1><div class="detail-box">${c.is_test?'<p>Адрес, координаты и лидер — примеры. Реальный лидер пока не назначен.</p>':''}<p>${esc(c.description)}</p><p>👤 <b>${esc(c.leader)}</b><br>📍 ${esc(c.address)}<br>🕒 ${esc(c.meeting)}<br>👥 ${c.participants} участников<br>🎂 ${esc(c.age)}</p><div class="tags">${c.interests.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div></div><div class="actions"><button class="btn" id="joinBtn">🙋 Хочу присоединиться</button>${!c.is_test&&c.leader_username?`<a class="btn secondary" href="https://t.me/${encodeURIComponent(c.leader_username)}">💬 Связаться с лидером</a>`:''}<a class="btn secondary" href="${route}">🗺 Построить маршрут</a></div>`;byId('joinBtn').onclick=()=>joinChurch(c.id);window.scrollTo({top:0,behavior:'smooth'})}catch(e){toast(e.message)}};
window.joinChurch=async function(id){if(joining)return;if(!tg?.initData){toast('Чтобы оставить заявку, откройте каталог через Telegram-бота.');return}joining=true;const b=byId('joinBtn');if(b)b.disabled=true;try{const r=await fetch('/api/requests',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({church_id:id,init_data:tg.initData})});if(!r.ok)throw Error(r.status===401?'Откройте каталог заново через Telegram-бота.':'Не удалось сохранить заявку. Попробуйте позже.');const data=await r.json();toast((data.created?'Заявка сохранена. № ':'Заявка уже сохранена. № ')+data.id);tg.HapticFeedback?.notificationOccurred('success')}catch(e){toast(e.message)}finally{joining=false;if(b)b.disabled=false}};
byId('backBtn').onclick=()=>{byId('detailView').classList.remove('show');byId('mainView').classList.remove('hide');map?.invalidateSize()};
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-view]').forEach(x=>x.classList.remove('active'));b.classList.add('active');const isMap=b.dataset.view==='map';byId('map').style.display=isMap?'block':'none';byId('listWrap').style.display=isMap?'none':'block';if(isMap)map?.invalidateSize()}));
byId('nearBtn').onclick=()=>{if(!churches.length){toast('В каталоге пока нет групп.');return}if(!navigator.geolocation){toast('Геолокация недоступна');return}navigator.geolocation.getCurrentPosition(pos=>{const {latitude,longitude}=pos.coords;churches.forEach(c=>c.distance=hav(latitude,longitude,c.lat,c.lon));churches.sort((a,b)=>a.distance-b.distance);selectedDistrict='Все районы';renderFilters();renderList();renderMarkers();if(map){if(userMarker)map.removeLayer(userMarker);userMarker=L.circleMarker([latitude,longitude],{radius:8,color:'#2997ff',fillColor:'#2997ff',fillOpacity:1}).addTo(map).bindPopup('Вы здесь');map.setView([latitude,longitude],13)}toast(`Ближайшая: ${churches[0].name} · ${churches[0].distance.toFixed(1)} км`);},()=>toast('Разрешите доступ к геолокации'));};
fetch('/api/churches').then(r=>{if(!r.ok)throw Error();return r.json()}).then(data=>{churches=data;renderFilters();renderList();initMap()}).catch(()=>toast('Не удалось загрузить данные. Обновите страницу.'));
</script>
</body>
</html>'''
