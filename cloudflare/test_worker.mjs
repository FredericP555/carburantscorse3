import assert from 'node:assert/strict';
import worker,{targetDate,actionForTime,dispatchIfNeeded,REPOSITORY} from './worker.mjs';
const env={C3_ENABLED:'true',C3_GH_DISPATCH_TOKEN:'test-only'};
assert.equal(targetDate('2026-11-01T06:37:00Z'),'2026-10-31');
assert.equal(targetDate('2027-01-01T06:37:00Z'),'2026-12-31');
assert.equal(actionForTime('2026-10-24T05:37:00Z'),'C3_UPDATE'); // summer time
assert.equal(actionForTime('2026-10-25T06:37:00Z'),'C3_UPDATE'); // winter time
assert.equal(actionForTime('2026-10-25T05:37:00Z'),'NOTHING');
assert.equal(actionForTime('2026-11-01T09:37:00Z'),'C3_UPDATE');
let calls=[];
function mock(last,statuses=[]) {return async(url,opts)=>{
  calls.push({url,opts});assert.ok(url.startsWith(`https://api.github.com/repos/${REPOSITORY}/`));
  if(url.includes('/contents/'))return Response.json({encoding:'base64',content:btoa(JSON.stringify({end:last}))});
  if(url.endsWith('/dispatches'))return new Response(null,{status:204});
  return Response.json({workflow_runs:statuses.map(status=>({status}))});
}}
assert.equal((await dispatchIfNeeded('2026-11-01T06:37:00Z',{},mock('2026-10-30'))).status,'disabled');assert.equal(calls.length,0);
assert.equal((await dispatchIfNeeded('2026-11-01T06:37:00Z',env,mock('2026-10-31'))).status,'already_current');
assert.equal((await dispatchIfNeeded('2026-11-01T06:37:00Z',env,mock('2026-10-30',['queued']))).status,'already_running');
calls=[];assert.equal((await dispatchIfNeeded('2026-11-01T06:37:00Z',env,mock('2026-10-30',['completed']))).status,'dispatch_accepted');
const post=calls.find(c=>c.opts.method==='POST');assert.equal(JSON.parse(post.opts.body).inputs.target_date,'2026-10-31');
await assert.rejects(dispatchIfNeeded('2026-11-01T06:37:00Z',env,async()=>new Response('',{status:503})),/HTTP 503/);
const response=await worker.fetch(new Request('https://example.test/'),{});assert.equal((await response.json()).http_dispatch,false);
console.log('C3 Worker: disabled mode, DST, month/year boundary, retry gates, active run, API error and read-only HTTP checks passed.');
