(() => {
'use strict';
const D=window.C3_DATA, $=id=>document.getElementById(id);
let brand='Total';
let fuel='Gazole', selected=D.dates.length-1;
const nf=(v,d=2)=>new Intl.NumberFormat('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d}).format(v);
const sign=(v,d=2)=>(v>0?'+':v<0?'−':'')+nf(Math.abs(v),d);
const dayLabel=(s,long=false)=>new Date(s+'T12:00:00').toLocaleDateString('fr-FR',{day:'numeric',month:long?'long':'short',...(long?{year:'numeric'}:{})});
const movement=v=>v>0?'up':v<0?'down':'flat';
const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const baseOptions={responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:'index',intersect:false},plugins:{legend:{display:false},tooltip:{backgroundColor:'#183c3a',padding:12,titleFont:{size:11},bodyFont:{size:11},displayColors:true}},layout:{padding:{right:8,top:8}},scales:{x:{grid:{display:false},border:{display:false},ticks:{maxTicksLimit:6,maxRotation:0,color:'#72817a',font:{size:10},callback:function(value){return dayLabel(D.dates[value]);}}},y:{border:{display:false},grid:{color:'#e6e6dd'},ticks:{color:'#72817a',font:{size:10}}}}};
const cursor={id:'selectedDay',afterDatasetsDraw(chart){const {ctx,chartArea,scales}=chart;if(!chartArea)return;const x=scales.x.getPixelForValue(selected);ctx.save();ctx.setLineDash([3,5]);ctx.strokeStyle='#8c9c88';ctx.beginPath();ctx.moveTo(x,chartArea.top);ctx.lineTo(x,chartArea.bottom);ctx.stroke();ctx.restore();}};
function makeChart(id, datasets, unit, provisional=false){const options=structuredClone(baseOptions);options.scales.x.ticks.callback=function(value){return dayLabel(D.dates[value]);};options.scales.y.title={display:true,text:unit==='€'?'€/L TTC':'c€/L hors TVA',color:'#183c3a',font:{size:12,weight:'bold'}};options.scales.y.ticks.maxTicksLimit=6;options.scales.y.ticks.callback=v=>nf(v,unit==='€'?3:2)+(unit==='€'?' €':'');options.plugins.tooltip.callbacks={title:items=>dayLabel(D.dates[items[0].dataIndex],true),label:ctx=>`${ctx.dataset.label} : ${nf(ctx.parsed.y,unit==='€'?3:2)} ${unit==='€'?'€/L TTC':'c€/L hors TVA'}${provisional?' · diagnostic':''}`};options.onClick=(event,elements,chart)=>{let i=elements[0]?.index;if(i===undefined){const rect=chart.canvas.getBoundingClientRect();const e=event.native;if(e)i=Math.round(chart.scales.x.getValueForPixel(e.clientX-rect.left));}if(Number.isInteger(i)&&i>=0&&i<D.dates.length)setDay(i);};return new Chart($(id),{type:'line',data:{labels:D.dates,datasets},options,plugins:[cursor]});}
function line(label,color,dashed=false){return {label,data:[],borderColor:color,backgroundColor:color,borderWidth:2,pointRadius:0,pointHoverRadius:4,pointHitRadius:14,tension:.15,borderDash:dashed?[5,4]:[],spanGaps:false};}
// Functions cannot be structured-cloned. Keep cloning to serializable options and restore callbacks.
delete baseOptions.scales.x.ticks.callback;
const charts={corse:makeChart('corse-chart',[line('Corse','#245d55')],'€'),gaps:makeChart('gap-chart',[line('Toutes stations Bouches-du-Rhône','#ae6b57'),line('Réseau traditionnel Bouches-du-Rhône','#245d55')],'c'),total:makeChart('total-chart',[line('Sous-ensemble Total identifié','#aa7835',true)],'c',true)};
function setDay(index){selected=Math.max(0,Math.min(D.dates.length-1,index));render();}
function render(){
 const current=D.fuels[fuel], ds=D.dates[selected], prices=current.regions.Corse, start=prices[0], total=current.total[selected];
 $('sp95-context').hidden=fuel!=='SP95';
 $('date').min=D.start;$('date').max=D.end;$('day-range').max=D.dates.length-1;
 $('date').value=ds;$('day-range').value=selected;$('prev').disabled=selected===0;$('next').disabled=selected===D.dates.length-1;
 document.querySelectorAll('[data-fuel]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.fuel===fuel)));
 document.querySelectorAll('.fuel-name').forEach(e=>e.textContent=fuel==='Gazole'?'gazole':'SP95');
 $('metric-price').innerHTML=`${nf(prices[selected],3)} <small>€/L</small>`;
 $('metric-price-date').textContent=dayLabel(ds,true);
 const delta=Math.round((prices[selected]-start)*100000)/1000;
 $('metric-change').innerHTML=`${sign(delta,1)} <small>c€/L</small>`;$('metric-change').className=movement(delta);
 $('metric-gap').innerHTML=`${sign(current.gaps.reseau[selected])} <small>c€/L</small>`;
 const sorted=Object.entries(current.regions).sort((a,b)=>b[1][selected]-a[1][selected]||a[0].localeCompare(b[0],'fr'));
 $('ranking-date').textContent=dayLabel(ds,true);
 $('ranking-body').innerHTML=sorted.map(([region,series],i)=>{const r=1+sorted.filter(([,values])=>values[selected]>series[selected]).length;const d=selected?Math.round((series[selected]-series[selected-1])*100000)/1000:null;return `<tr class="${region==='Corse'?'corse-row':''}"><td>${r}</td><td><span class="region-name"><i class="region-color" style="background:${D.colors[region]}"></i>${escape(region)}</span></td><td class="${d===null?'flat':movement(d)}" title="${d===null?'Pas de journée précédente dans la période':sign(d,1)+' c€/L depuis la veille'}">${d===null?'—':(d>0?'↗ ':d<0?'↘ ':'→ ')+sign(d,1)}</td><td>${nf(series[selected],3)}</td></tr>`;}).join('');
 $('corse-values').innerHTML=D.dates.map((d,i)=>`<tr class="${i===selected?'selected-row':''}"><td>${dayLabel(d)}</td><td>${nf(prices[i],3)} €</td><td>${i?sign((prices[i]-prices[i-1])*100,1)+' c€':'—'}</td></tr>`).join('');
 $('gap-values').innerHTML=D.dates.map((d,i)=>`<tr class="${i===selected?'selected-row':''}"><td>${dayLabel(d)}</td><td>${sign(current.gaps.all[i])}</td><td>${sign(current.gaps.reseau[i])}</td></tr>`).join('');
 $('small-sample').hidden=total.n_bdr>=5;
 $('small-sample').textContent=`Échantillon restreint : peu de stations Total traditionnelles disposent d’un prix retenu pour le ${fuel} dans les Bouches-du-Rhône ce jour-là. La comparaison doit être interprétée avec prudence.`;
 charts.corse.data.datasets[0].data=prices;
 charts.gaps.data.datasets[0].data=current.gaps.all;charts.gaps.data.datasets[1].data=current.gaps.reseau;
 const e10=fuel==='SP95', isEni=brand==='ENI';
 const kicker=$('comparison-kicker');if(kicker)kicker.textContent=e10?'04 / COMPARAISON SP95 / E10':'04 / À ENSEIGNE COMPARABLE';
 $('brand-selector').hidden=e10;
 $('vito-note').hidden=e10;
 document.querySelectorAll('[data-brand]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.brand===brand))); 
 $('comparison-title').textContent=e10?'SP95 en Corse − E10 dans les Bouches-du-Rhône':`${brand} traditionnel : Corse − Bouches-du-Rhône`;
 $('comparison-subtitle').textContent=e10?'Écart hors TVA · toutes enseignes · deux carburants différents':isEni?'Stations traditionnelles sous enseigne ENI · hors autoroutes':'Total / TotalEnergies et Contact · sans Access, low cost ni Élan';
 $('comparison-panel').classList.toggle('provisional-panel',!e10);

 for(const id of ['e10-note','e10-legend','e10-details'])$(id).hidden=!e10;
 $('small-sample').hidden=e10||isEni||total.n_bdr>=5;
 $('comparison-source').textContent=e10?'Écarts issus des déclarations officielles · SP95 Corse / E10 Bouches-du-Rhône · hors TVA':`Écart ${brand} traditionnel · c€/L hors TVA · stations retenues selon les critères de fiabilité`;
 $('total-chart').setAttribute('aria-label',e10?'Écarts hors TVA entre le SP95 en Corse et l’E10 dans les Bouches-du-Rhône':`Écart ${brand} traditionnel hors TVA`);
 charts.total.options.plugins.tooltip.callbacks.label=ctx=>`${ctx.dataset.label} : ${nf(ctx.parsed.y,2)} c€/L hors TVA${!e10&&!isEni?' · diagnostic':''}`;
 if(e10){
  charts.total.data.datasets=[line('SP95 Corse − E10 Bouches-du-Rhône · toutes stations','#ae6b57'),line('SP95 Corse − E10 Bouches-du-Rhône · réseau traditionnel','#245d55')];
  charts.total.data.datasets[0].data=current.e10_gaps.all;charts.total.data.datasets[1].data=current.e10_gaps.reseau;
  $('e10-values').innerHTML=D.dates.map((d,i)=>`<tr class="${i===selected?'selected-row':''}"><td>${dayLabel(d)}</td><td style="font-size:15px;font-weight:600">${sign(current.e10_gaps.all[i])}</td><td style="font-size:15px;font-weight:600">${sign(current.e10_gaps.reseau[i])}</td></tr>`).join('');
 }else if(isEni){charts.total.data.datasets=[line('ENI traditionnel Corse − Bouches-du-Rhône','#245d55')];charts.total.data.datasets[0].data=current.eni.map(r=>r.gap);}else{charts.total.data.datasets=[line('Total traditionnel Corse − Bouches-du-Rhône','#aa7835',true)];charts.total.data.datasets[0].data=current.total.map(r=>r.diagnostic);}

 Object.values(charts).forEach(chart=>{chart.data.datasets.forEach(s=>{s.pointRadius=D.dates.map((_,i)=>i===selected?4:0);s.pointBackgroundColor=s.borderColor;s.pointBorderColor='#fffefa';s.pointBorderWidth=2;});chart.update('none');});
 $('source-c1').href=D.provenance.c1_url;$('source-c2').href=D.provenance.c2_url;
 if($('history-dialog').open)renderHistory();
}
function renderHistory(){const current=D.fuels[fuel];$('history-caption').textContent=`${fuel} · prix moyens régionaux TTC · du ${dayLabel(D.dates[0],true)} au ${dayLabel(D.end,true)}.`;$('history-head').innerHTML='<tr><th>Région</th>'+D.dates.map((d,i)=>`<th class="${i===selected?'selected-col':''}">${dayLabel(d)}</th>`).join('')+'</tr>';$('history-body').innerHTML=Object.entries(current.regions).sort(([a],[b])=>a==='Corse'?-1:b==='Corse'?1:a.localeCompare(b,'fr')).map(([name,series])=>`<tr class="${name==='Corse'?'history-corse':''}"><td>${escape(name)}</td>${series.map((v,i)=>`<td class="${i===selected?'selected-col':''}">${nf(v,3)}</td>`).join('')}</tr>`).join('');}
function exportCsv(){const current=D.fuels[fuel],regions=Object.keys(current.regions).sort((a,b)=>a.localeCompare(b,'fr'));const header=['date','carburant',...regions.map(r=>r+'_TTC_EUR_L'),'ecart_Corse_Bouches-du-Rhône_toutes_hors_TVA_c_L','ecart_Corse_Bouches-du-Rhône_traditionnel_hors_TVA_c_L','diagnostic_Total_identifie_hors_TVA_c_L_NON_VALIDE','Total_Corse_effectif_identifie','Total_Bouches-du-Rhône_effectif_identifie','identites_historiques_manquantes'];const rows=D.dates.map((d,i)=>[d,fuel,...regions.map(r=>current.regions[r][i]),current.gaps.all[i],current.gaps.reseau[i],current.total[i].diagnostic,current.total[i].n_corse,current.total[i].n_bdr,current.total[i].unresolved_ids.join(',')]);if(fuel==='Gazole'&&brand==='ENI'){header.splice(17,5,'ecart_ENI_traditionnel_Corse_Bouches_du_Rhone_hors_TVA_c_L','ENI_Corse_effectif','ENI_Bouches_du_Rhone_effectif');rows.forEach((row,i)=>row.splice(17,5,current.eni[i].gap,current.eni[i].n_corse,current.eni[i].n_bdr));}if(fuel==='SP95'){header.splice(17,5,'ecart_SP95_Corse_E10_Bouches_du_Rhone_toutes_hors_TVA_c_L','ecart_SP95_Corse_E10_Bouches_du_Rhone_traditionnel_hors_TVA_c_L');rows.forEach((row,i)=>row.splice(17,5,current.e10_gaps.all[i],current.e10_gaps.reseau[i]));}const quote=v=>'"'+String(v).replaceAll('"','""')+'"';const csv='\ufeff'+[header,...rows].map(row=>row.map(quote).join(';')).join('\r\n');const url=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`C3_${fuel}_${D.start}_${D.end}.csv`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
document.querySelectorAll('[data-fuel]').forEach(b=>b.addEventListener('click',()=>{fuel=b.dataset.fuel;render();}));
document.querySelectorAll('[data-brand]').forEach(b=>b.addEventListener('click',()=>{brand=b.dataset.brand;render();}));
$('date').addEventListener('change',e=>{const index=D.dates.indexOf(e.target.value);if(index>=0)setDay(index);else e.target.value=D.dates[selected];});
$('day-range').addEventListener('input',e=>setDay(Number(e.target.value)));
$('prev').addEventListener('click',()=>setDay(selected-1));$('next').addEventListener('click',()=>setDay(selected+1));$('export').addEventListener('click',exportCsv);
$('open-history').addEventListener('click',()=>{renderHistory();$('history-dialog').showModal();});$('close-history').addEventListener('click',()=>$('history-dialog').close());
$('history-dialog').addEventListener('click',e=>{if(e.target===$('history-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
render();
})();

