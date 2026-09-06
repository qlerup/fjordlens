const state = { momentPlayer: null };
const els = Object.fromEntries(['momentPlayerOverlay','momentPlayerProgress','momentPlayerCloseBtn','momentPlayerStage','momentPlayerPrevZone','momentPlayerNextZone','momentPlayerFooterTitle'].map(id => [id,document.getElementById(id)]));
function tr(value) { return value; }
document.addEventListener('DOMContentLoaded', () => {
  let item;
  const button = document.getElementById('replayMoment');
  function play() {
    if (!item || state.momentPlayer) return;
    state.momentPlayer = {...item,index:0,timer:null};
    _momentPlayerOpen();
  }
  button.onclick = play;
  fetch(document.getElementById('shareBootstrap').dataset.url,{cache:'no-store'})
    .then(async response => { if (!response.ok) throw new Error(); return response.json(); })
    .then(data => { item=data.item; document.getElementById('shareStatus').textContent=momentIsPhone() ? 'Se momentet i bredformat. Drej telefonen, når du trykker afspil.' : 'Læn dig tilbage og se momentet med billeder, video og musik.'; button.disabled=false; })
    .catch(() => { document.getElementById('shareStatus').textContent='Linket er ikke længere tilgængeligt.'; });
});
