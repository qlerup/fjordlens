/* Geometry is normalized to the slide, so edits survive export and rotation. */
function momentResizeText(box, handle, dx, dy) {
  const b = {...box}, west=handle.includes('w'), north=handle.includes('n');
  const horizontal=/[ew]/.test(handle), vertical=/[ns]/.test(handle);
  if (horizontal && vertical) {
    const fx=1+(west?-dx:dx)/box.width, fy=1+(north?-dy:dy)/box.height;
    let factor=Math.abs(fx-1)>Math.abs(fy-1)?fx:fy;
    const maxX=(west?box.x+box.width:1-box.x)/box.width;
    const maxY=(north?box.y+box.height:1-box.y)/box.height;
    factor=Math.max(Math.max(.015/box.width,.012/box.height),Math.min(maxX,maxY,factor));
    b.width=box.width*factor; b.height=box.height*factor;
    if(west)b.x=box.x+box.width-b.width;
    if(north)b.y=box.y+box.height-b.height;
  } else {
    if(horizontal) {
      const edge=Math.max(west?0:box.x+.015,Math.min(west?box.x+box.width-.015:1,(west?box.x:box.x+box.width)+dx));
      b.x=west?edge:box.x; b.width=west?box.x+box.width-edge:edge-box.x;
    }
    if(vertical) {
      const edge=Math.max(north?0:box.y+.012,Math.min(north?box.y+box.height-.012:1,(north?box.y:box.y+box.height)+dy));
      b.y=north?edge:box.y; b.height=north?box.y+box.height-edge:edge-box.y;
    }
  }
  return b;
}

function momentTextEditor({preview, panel, getSlide, begin, changed, render}) {
  let selectedKey='heading';
  const snapLabel=document.createElement('label');
  snapLabel.className='slideshow-snap-toggle';
  snapLabel.innerHTML='<input type="checkbox" checked> Snap til midte og andre tekster';
  panel.append(snapLabel);
  const enabled=()=>snapLabel.querySelector('input').checked;
  const labels={heading:'Overskrift',eyebrow:'Sted / lille tekst',detail:'Dato / undertekst',weather:'Vejr'};
  function decorate(text) {
    if(!text)return;
    for(const line of text.querySelectorAll('[data-text-key]')) {
      const key=line.dataset.textKey;
      line.tabIndex=0; line.setAttribute('role','button');
      line.setAttribute('aria-label',`Flyt eller tilpas ${labels[key]}`);
      line.classList.toggle('text-selected',key===selectedKey);
      line.querySelectorAll('.text-resize-handle').forEach(e=>e.remove());
      if(key===selectedKey)for(const side of ['n','ne','e','se','s','sw','w','nw']) {
        const handle=document.createElement('span'); handle.dataset.textResize=side;
        handle.className=`text-resize-handle handle-${side}`; handle.setAttribute('aria-hidden','true');
        line.append(handle);
      }
    }
  }
  function capture() {
    const slide=getSlide(), stage=preview.querySelector('.cinema-slide').getBoundingClientRect();
    const elements={...slide.text_elements};
    for(const line of preview.querySelectorAll('[data-text-key]')) {
      const key=line.dataset.textKey;
      if(elements[key])continue;
      const rect=line.getBoundingClientRect();
      const width=Math.max(.015,Math.min(1,rect.width/stage.width));
      const height=Math.max(.012,Math.min(1,rect.height/stage.height));
      elements[key]={x:Math.max(0,Math.min(1-width,(rect.x-stage.x)/stage.width)),
        y:Math.max(0,Math.min(1-height,(rect.y-stage.y)/stage.height)),width,height,
        font_size:Math.max(.003,Math.min(.3,parseFloat(getComputedStyle(line).fontSize)/stage.width))};
    }
    slide.text_elements=elements; delete slide.text_position;
    return elements;
  }
  function targets(elements,key,axis) {
    const size=axis==='x'?'width':'height';
    return [0,.5,1,...Object.entries(elements).filter(([k])=>k!==key).flatMap(([,b])=>[b[axis],b[axis]+b[size]/2,b[axis]+b[size]])];
  }
  function clearGuides() { preview.querySelectorAll('.text-snap-guide').forEach(e=>e.remove()); }
  function guide(axis,value) {
    const line=document.createElement('div'); line.className=`text-snap-guide snap-${axis}`;
    line.style[axis==='x'?'left':'top']=`${value*100}%`; preview.append(line);
  }
  function snap(box,elements,key,stage,handle,original) {
    const b={...box}, matches=[];
    for(const axis of ['x','y']) {
      const size=axis==='x'?'width':'height', pixels=axis==='x'?stage.width:stage.height;
      const edge=axis==='x'?(handle?.includes('w')?0:1):(handle?.includes('n')?0:1);
      const active=!handle || (axis==='x'?/[ew]/:/[ns]/).test(handle);
      if(!active)continue;
      let best=null;
      for(const target of targets(elements,key,axis))for(const anchor of handle?[edge]:[0,.5,1]) {
        const distance=target-(b[axis]+b[size]*anchor);
        if(Math.abs(distance)*pixels<=7 && (!best||Math.abs(distance)<Math.abs(best.distance)))best={axis,target,anchor,distance};
      }
      if(best)matches.push(best);
    }
    if(handle && handle.length===2 && matches.length) {
      // Snap the closest dragged corner axis, then scale both axes together.
      matches.sort((a,b)=>Math.abs(a.distance)*(a.axis==='x'?stage.width:stage.height)-Math.abs(b.distance)*(b.axis==='x'?stage.width:stage.height));
      const hit=matches[0], size=hit.axis==='x'?'width':'height';
      const opposite=original[hit.axis]+original[size]*(1-hit.anchor);
      const factor=Math.abs(hit.target-opposite)/original[size];
      Object.assign(b,momentResizeText(original,handle,(factor-1)*original.width*(handle.includes('w')?-1:1),(factor-1)*original.height*(handle.includes('n')?-1:1)));
    } else for(const hit of matches) {
      if(!handle)b[hit.axis]+=hit.distance;
      else {
        const size=hit.axis==='x'?'width':'height';
        if(hit.anchor===0){b[hit.axis]+=hit.distance;b[size]-=hit.distance;}else b[size]+=hit.distance;
      }
    }
    b.width=Math.min(1,Math.max(.015,b.width)); b.height=Math.min(1,Math.max(.012,b.height));
    b.x=Math.max(0,Math.min(1-b.width,b.x)); b.y=Math.max(0,Math.min(1-b.height,b.y));
    for(const hit of matches) {
      const size=hit.axis==='x'?'width':'height';
      if(Math.abs(b[hit.axis]+b[size]*hit.anchor-hit.target)<.0001)guide(hit.axis,hit.target);
    }
    return b;
  }
  function paint() { const text=preview.querySelector('.cinema-type'); momentApplyTextElements(text,getSlide().text_elements); decorate(text); }
  preview.addEventListener('pointerdown',event=>{
    const line=event.target.closest('[data-text-key]');
    if(!line||event.button!==0||!event.isPrimary)return;
    event.preventDefault(); selectedKey=line.dataset.textKey;
    const handle=event.target.closest('[data-text-resize]')?.dataset.textResize;
    decorate(preview.querySelector('.cinema-type')); line.focus({preventScroll:true});
    const stage=preview.querySelector('.cinema-slide').getBoundingClientRect();
    let original=null,rollback=null;
    preview.setPointerCapture(event.pointerId);
    const move=e=>{
      if(e.pointerId!==event.pointerId)return;
      const dx=(e.clientX-event.clientX)/stage.width,dy=(e.clientY-event.clientY)/stage.height;
      if(!original && Math.hypot(dx*stage.width,dy*stage.height)<3)return;
      if(!original){rollback=begin();original={...capture()[selectedKey]};}
      clearGuides();
      let box=handle?momentResizeText(original,handle,dx,dy):{...original,x:Math.max(0,Math.min(1-original.width,original.x+dx)),y:Math.max(0,Math.min(1-original.height,original.y+dy))};
      if(enabled()&&!e.altKey)box=snap(box,getSlide().text_elements,selectedKey,stage,handle,original);
      getSlide().text_elements[selectedKey]=box;
      paint(); changed();
    };
    const finish=e=>{
      if(e.pointerId!==event.pointerId)return;
      preview.removeEventListener('pointermove',move); preview.removeEventListener('pointerup',finish);
      preview.removeEventListener('pointercancel',finish); preview.removeEventListener('lostpointercapture',finish);
      clearGuides();
      if(original){if(e.type==='pointercancel')rollback();render();preview.querySelector(`[data-text-key="${selectedKey}"]`)?.focus({preventScroll:true});}
    };
    preview.addEventListener('pointermove',move); preview.addEventListener('pointerup',finish);
    preview.addEventListener('pointercancel',finish); preview.addEventListener('lostpointercapture',finish);
  });
  preview.addEventListener('keydown',e=>{
    const line=e.target.closest('[data-text-key]'), delta={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]}[e.key];
    if(!line||!delta)return;
    e.preventDefault(); selectedKey=line.dataset.textKey; begin();
    const box=capture()[selectedKey],step=e.shiftKey?.05:.005;
    box.x=Math.max(0,Math.min(1-box.width,box.x+delta[0]*step));
    box.y=Math.max(0,Math.min(1-box.height,box.y+delta[1]*step));
    changed();render();preview.querySelector(`[data-text-key="${selectedKey}"]`)?.focus({preventScroll:true});
  });
  return {decorate};
}
