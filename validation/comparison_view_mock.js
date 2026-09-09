// Independent mocked DOM/canvas behavior checks; no real browser or user data.
const assert=require('node:assert/strict'),vm=require('node:vm');
const source=require('node:fs').readFileSync(0,'utf8');
const calls=[],saved={};
function canvas(){return {hidden:false,style:{},getContext(){return {drawImage(...x){calls.push(x)},fillRect(){},strokeRect(){}}},setAttribute(){},focus(){},setPointerCapture(){},getBoundingClientRect(){return {left:0,top:0}}};}
const img=(w,h,src)=>({naturalWidth:w,naturalHeight:h,getAttribute:()=>src,addEventListener(){}});
const d=img(500,1000,'design.png'),v=img(1000,2000,'dev.png');
const svg={viewBox:{baseVal:{width:1000,height:2000}}};
let glass,tools,dialog;
const host={style:{},clientWidth:500,clientHeight:1000,append(x){glass=x},querySelector(){return svg}};v.parentElement=host;
const modes=['side','over','crop'].map(mode=>({dataset:{mode},setAttribute(){}}));
const label={},reset={},slider={value:'50'},help={};
const outputs=[canvas(),canvas()];
const pair={querySelectorAll(){return [ {querySelector:()=>d},{querySelector:()=>v}]},closest(){return null},before(x){tools=x},classList:{toggle(){}}};
const document={querySelector(){return pair},body:{append(x){dialog=x}},getElementById(){return {querySelector(){return {getAttribute(k){return {x:100,y:200,width:50,height:60}[k]}}}}},createElement(type){
 if(type==='canvas')return canvas();
 if(type==='dialog')return {querySelector(){return {}},querySelectorAll(){return outputs},showModal(){this.open=true},close(){this.open=false}};
 return {querySelector(q){return {'.cv-help':help,input:slider,label,'[data-reset]':reset}[q]},querySelectorAll(){return modes}};
}};
const ctx={document,window:{},location:{pathname:'/screen/a',search:''},localStorage:{getItem(){return null},setItem(k,v){saved[k]=v}},requestAnimationFrame(fn){fn()},ResizeObserver:class{observe(){}},console};
vm.runInNewContext(source,ctx);
assert.equal(glass.hidden,true);
modes[1].onclick();assert.equal(glass.hidden,false);assert.equal(label.hidden,false);
glass.onpointerdown({button:0,pointerId:1,clientX:0,clientY:0});
glass.onpointermove({clientX:10,clientY:20});glass.onpointerup({clientX:10,clientY:20});
assert.deepEqual(JSON.parse(Object.values(saved)[0]),{x:20,y:40});
modes[2].onclick();calls.length=0;
glass.onpointerdown({button:0,pointerId:1,clientX:100,clientY:200});glass.onpointerup({clientX:200,clientY:300});
assert.equal(dialog.open,true);
assert.deepEqual(calls[0].slice(1,5),[90,180,100,100]);
assert.deepEqual(calls[1].slice(1,5),[200,400,200,200]);
calls.length=0;ctx.window.qaCompareIssue('abc');
assert.deepEqual(calls[0].slice(1,5),[30,70,45,50]);
assert.deepEqual(calls[1].slice(1,5),[80,180,90,100]);
modes[1].onclick();glass.onkeydown({key:'ArrowRight',shiftKey:true,preventDefault(){}});
assert.deepEqual(JSON.parse(Object.values(saved)[0]),{x:30,y:40});
reset.onclick();assert.deepEqual(JSON.parse(Object.values(saved)[0]),{x:0,y:0});
console.log('Mocked JS: mode, drag/save, crop scale, pin coordinates, keyboard/reset passed.');
assert.equal(host.style.position,'relative');
modes[2].onclick();
glass.onpointerdown({button:0,pointerId:2,clientX:0,clientY:0});glass.onpointerup({clientX:2,clientY:1000});
for(const output of outputs){assert.ok(output.width<=1400);assert.ok(output.height<=1400);assert.ok(output.width>=1);}
