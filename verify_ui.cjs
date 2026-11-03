// Exercise rendered DOM bindings and switch behaviour without external browser dependencies.
const fs=require('fs'),vm=require('vm'),path=require('path');
const root=__dirname,html=fs.readFileSync(path.join(root,'maquette/dist/index.html'),'utf8');
const elements={},charts=[];
function element(){return {open:false,hidden:false,classList:{toggle(){}},setAttribute(k,v){this[k]=v},addEventListener(k,fn){this['on'+k]=fn},showModal(){this.open=true},close(){this.open=false}}}
for(const m of html.matchAll(/id="([^"]+)"/g))elements[m[1]]=element();
const buttons=(key,values)=>values.map(value=>({...element(),dataset:{[key]:value}}));
const fuels=buttons('fuel',['Gazole','SP95']),brands=buttons('brand',['Total','ENI']),scopes=buttons('totalScope',['all','traditional']);
let blob,download;
const context={console,structuredClone,Intl,Date,setTimeout,Blob,URL:{createObjectURL:b=>{blob=b;return 'blob:test'},revokeObjectURL(){}},document:{getElementById:id=>{if(!elements[id])throw Error('Missing DOM element: '+id);return elements[id]},querySelectorAll:q=>q==='[data-fuel]'?fuels:q==='[data-brand]'?brands:q==='[data-total-scope]'?scopes:[],createElement:()=>({click(){download=this.download}})},Chart:function(e,options){this.data=options.data;this.options=options.options;this.update=()=>{};charts.push(this)}};
context.window=context;vm.createContext(context);
for(const file of ['data.js','app.js'])vm.runInContext(fs.readFileSync(path.join(root,'maquette/dist',file),'utf8'),context);
const assert=(x,msg)=>{if(!x)throw Error(msg)};
async function main(){
 const data=context.C3_DATA,n=data.dates.length;
 assert(elements.date.value===data.end,'last date');assert(Number(elements['day-range'].max)===n-1,'range');
 assert(charts[0].data.datasets[0].data.length===n,'regional curve length');
 // Independent reference fixtures: Corsica +20 c/L, each other region -10 c/L.
 // The expected -10 must not be diluted by including Corsica in the mean.
 const originalRegions=structuredClone(data.fuels.Gazole.regions),baseline=data.dates.indexOf('2026-10-30');
 if(baseline>0&&baseline+1<n){
 const choose=i=>elements.date.onchange({target:{value:data.dates[i]}});
 try{
  for(const [name,values] of Object.entries(data.fuels.Gazole.regions)){
   values[baseline]=name==='Corse'?2:1.5;
   values[baseline+1]=name==='Corse'?2.2:1.4;
  }
  choose(baseline+1);
  assert(!elements['october-reference'].hidden,'reference visible for Gazole');
  assert(elements['reference-corse'].innerHTML.startsWith('+20,0 '),'Corse reference calculation');
  assert(elements['reference-corse'].className==='up','increase colour');
  assert(elements['reference-regions'].innerHTML.startsWith('−10,0 '),'equal-weight twelve-region reference');
  assert(elements['reference-regions'].className==='down','decrease colour');
  fuels[1].onclick();assert(elements['october-reference'].hidden,'reference hidden for SP95');
  fuels[0].onclick();assert(!elements['october-reference'].hidden,'reference restored for Gazole');
  choose(baseline);
  assert(elements['reference-corse'].innerHTML.startsWith('0,0 '),'reference day zero');
  assert(elements['reference-regions'].className==='flat','reference day neutral colour');
  choose(baseline-1);
  assert(elements['reference-corse'].innerHTML==='—'&&elements['reference-regions'].innerHTML==='—','before reference no misleading change');
  choose(baseline+1);
  const peer=Object.keys(data.fuels.Gazole.regions).find(name=>name!=='Corse');
  data.fuels.Gazole.regions[peer][baseline]=null;fuels[0].onclick();
  assert(elements['reference-regions'].innerHTML==='—','incomplete reference is not averaged silently');
  data.fuels.Gazole.regions[peer][baseline]=1.5;
  const savedDate=data.dates[baseline];data.dates[baseline]='2026-10-30-unavailable';
  fuels[0].onclick();assert(elements['reference-corse'].innerHTML==='—','missing reference date is safe');
  data.dates[baseline]=savedDate;
 }finally{data.fuels.Gazole.regions=originalRegions;choose(n-1);}
 assert(JSON.stringify(data.fuels.Gazole.regions)===JSON.stringify(originalRegions),'source prices unchanged');
 }else{
  assert(elements['reference-corse'].innerHTML===(baseline<0?'—':'0,0 <small>c€/L</small>'),'safe reference for historical snapshots');
 }

 assert(!elements['total-scope-controls'].hidden,'Total scopes visible');
 const legacy=JSON.stringify(data.fuels.Gazole.total);
 scopes[0].onclick();assert(scopes[0]['aria-pressed']==='true','Access pressed');
 assert(JSON.stringify(charts[2].data.datasets[0].data)===JSON.stringify(data.fuels.Gazole.total_all.map(r=>r.diagnostic)),'Access series displayed');
 assert(elements['comparison-scope'].textContent.includes('Access inclus'),'Access scope heading');
 elements.export.onclick();let accessCsv=await blob.text();
 assert(accessCsv.includes('diagnostic_Total_Access_inclus'),'Access CSV header');
 const accessRows=accessCsv.replace(/^\uFEFF/,'').split('\r\n').map(row=>row.split(';'));
 assert(accessRows.every(row=>row.length===accessRows[0].length),'Access CSV column alignment');
 assert(accessRows[1][17]===JSON.stringify(String(data.fuels.Gazole.total_all[0].diagnostic)),'Access CSV value');
 assert(download.includes('Total_Access_inclus_'),'Access CSV filename');
 brands[1].onclick();assert(elements['total-scope-controls'].hidden,'scopes hidden for Eni');assert(elements['comparison-title'].textContent.startsWith('Eni'),'ENI title');assert(charts[2].data.datasets.length===1,'ENI one line');
 elements.export.onclick();let csv=await blob.text();assert(download.endsWith(data.end+'.csv'),'CSV dates');assert(csv.split('\r\n').length===n+1,'CSV rows');assert(csv.includes('ecart_ENI_traditionnel'),'ENI CSV');
 const eniRows=csv.replace(/^\uFEFF/,'').split('\r\n').map(row=>row.split(';'));
 assert(eniRows.every(row=>row.length===eniRows[0].length),'ENI CSV column alignment');
 assert(eniRows[1][17]===JSON.stringify(String(data.fuels.Gazole.eni[0].gap)),'ENI CSV first gap');
 // A missing hidden Total/SP95 diagnostic must not break the E10 comparison.
 delete data.fuels.SP95.total;
 fuels[1].onclick();assert(charts[2].data.datasets.length===2,'SP95/E10 two lines');assert(elements['brand-selector'].hidden,'brand selector hidden for SP95');assert(!elements['sp95-context'].hidden,'SP95 note');assert(elements['total-scope-controls'].hidden,'scopes hidden for SP95');
 assert(charts[2].options.scales.y.title.text==='c€/L hors TVA','gap unit');
 elements.export.onclick();csv=await blob.text();assert(csv.includes('ecart_SP95_Corse_E10'),'E10 CSV');assert(!csv.includes('diagnostic_Total_identifie'),'No hidden Total SP95 diagnostic in CSV');
 const e10Rows=csv.replace(/^\uFEFF/,'').split('\r\n').map(row=>row.split(';'));
 assert(e10Rows.every(row=>row.length===e10Rows[0].length),'E10 CSV column alignment');
 assert(e10Rows[1][17]===JSON.stringify(String(data.fuels.SP95.e10_gaps.all[0])),'E10 CSV first gap');
 elements.date.onchange({target:{value:data.start}});assert(elements.date.value===data.start,'date selection');elements['open-history'].onclick();assert(elements['history-head'].innerHTML.match(/<th/g).length===n+1,'history dates');
 fuels[0].onclick();brands[0].onclick();assert(elements['comparison-title'].textContent.startsWith('Total'),'Total restored');assert(!elements['brand-selector'].hidden,'brand selector restored');
 assert(scopes[0]['aria-pressed']==='true','scope selection preserved');
 scopes[1].onclick();assert(scopes[1]['aria-pressed']==='true','Hors Access pressed');
 assert(JSON.stringify(charts[2].data.datasets[0].data)===JSON.stringify(data.fuels.Gazole.total.map(r=>r.diagnostic)),'Hors Access series restored');
 assert(JSON.stringify(data.fuels.Gazole.total)===legacy,'legacy Total data unchanged');
 elements.export.onclick();csv=await blob.text();
 assert(csv.includes('diagnostic_Total_identifie'),'Total CSV selected');
 assert(!csv.includes('ecart_ENI_traditionnel'),'No ENI field in Total export');
 assert(!elements['source-c1']&&!elements['source-c2'],'No obsolete public source links');
 console.log('UI bindings, date range, Total Access scopes/ENI, SP95/E10, history table and Total, ENI and SP95/E10 CSV exports verified.');
}
main().catch(e=>{console.error(e);process.exitCode=1});
