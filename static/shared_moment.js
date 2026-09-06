const state = { momentPlayer: null };
const els = Object.fromEntries(['momentPlayerOverlay','momentPlayerProgress','momentPlayerCloseBtn','momentPlayerStage','momentPlayerPrevZone','momentPlayerNextZone','momentPlayerFooterTitle'].map(id => [id,document.getElementById(id)]));
function tr(value) { return value; }
document.addEventListener('DOMContentLoaded', () => {
  let item;
  function play() {
    if (!item) return;
    state.momentPlayer = {...item,index:0,timer:null};
    _momentPlayerOpen();
  }
  document.getElementById('replayMoment').onclick = play;
  fetch(document.getElementById('shareBootstrap').dataset.url,{cache:'no-store'})
    .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
    .then(data => { item=data.item; document.getElementById('shareStatus').textContent=''; play(); })
    .catch(() => { document.getElementById('shareStatus').textContent='Linket er ikke længere tilgængeligt.'; });
});
