// C3 only. Does not dispatch any C1/C2 workflow. HTTP requests are read-only.
export const REPOSITORY = 'FredericP555/carburantscorse3';
export const WORKFLOW = 'update-daily.yml';
export function parisParts(timestamp) {
  return Object.fromEntries(new Intl.DateTimeFormat('en-GB', {
    timeZone:'Europe/Paris',year:'numeric',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',hourCycle:'h23'
  }).formatToParts(new Date(timestamp)).map(({type,value})=>[type,value]));
}
export function targetDate(timestamp) {
  const p=parisParts(timestamp);
  return new Date(Date.UTC(+p.year,+p.month-1,+p.day)-86400000).toISOString().slice(0,10);
}
export function actionForTime(timestamp, env={}) {
  const p=parisParts(timestamp),slot=`${p.hour}:${p.minute}`;
  const slots=(env.C3_PARIS_SLOTS||'07:37,10:37,14:37').split(',').map(s=>s.trim());
  return slots.includes(slot)?'C3_UPDATE':'NOTHING';
}
async function github(path,env,options={},request=fetch) {
  const response=await request(`https://api.github.com/repos/${REPOSITORY}/${path}`,{
    ...options,headers:{Authorization:`Bearer ${env.C3_GH_DISPATCH_TOKEN}`,
      Accept:'application/vnd.github+json','Content-Type':'application/json',
      'X-GitHub-Api-Version':'2022-11-28','User-Agent':'A4C-C3-Scheduler'}
  });
  // Do not expose arbitrary response bodies or secrets in logs.
  if(!response.ok)throw Error(`C3 GitHub request failed: HTTP ${response.status}`);
  return response;
}
export async function dispatchIfNeeded(timestamp,env,request=fetch) {
  if(env.C3_ENABLED!=='true')return {status:'disabled'};
  if(actionForTime(timestamp,env)==='NOTHING')return {status:'outside_slot'};
  if(!env.C3_GH_DISPATCH_TOKEN)throw Error('Missing C3-only GitHub token');
  const target=targetDate(timestamp);
  const content=await (await github('contents/data/current.json?ref=main',env,{},request)).json();
  if(content.encoding!=='base64'||typeof content.content!=='string')throw Error('Invalid C3 data response');
  const data=JSON.parse(atob(content.content.replace(/\s/g,'')));
  if(!/^\d{4}-\d{2}-\d{2}$/.test(data.end))throw Error('Invalid C3 last date');
  if(data.end>=target)return {status:'already_current',target,last_date:data.end};
  const runs=await (await github(`actions/workflows/${WORKFLOW}/runs?branch=main&per_page=20`,env,{},request)).json();
  if(!Array.isArray(runs.workflow_runs))throw Error('Invalid workflow-runs response');
  if(runs.workflow_runs.some(r=>['queued','in_progress','requested','waiting','pending'].includes(r.status)))
    return {status:'already_running',target};
  await github(`actions/workflows/${WORKFLOW}/dispatches`,env,{
    method:'POST',body:JSON.stringify({ref:'main',inputs:{target_date:target,apply:true}})
  },request);
  return {status:'dispatch_accepted',target};
}
export default {
  async fetch(request,env) {
    const now=Date.now(),p=parisParts(now);
    return Response.json({service:'A4C C3 scheduler',enabled:env.C3_ENABLED==='true',
      paris_slot:`${p.hour}:${p.minute}`,scheduled_action:actionForTime(now,env),
      target_date:targetDate(now),repository:REPOSITORY,http_dispatch:false,
      note:'Cron configuration is managed separately; this response does not inspect it.'});
  },
  async scheduled(event,env) {
    const result=await dispatchIfNeeded(event.scheduledTime,env);
    console.log(JSON.stringify({service:'C3',...result}));
  }
};
