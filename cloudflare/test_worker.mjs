import assert from 'node:assert/strict';
import worker,{targetDate,actionForTime,dispatchIfNeeded,REPOSITORY,WORKFLOW,PAGES_WORKFLOW,PUBLIC_MANIFEST} from './worker.mjs';
const env={C3_ENABLED:'true',C3_GH_DISPATCH_TOKEN:'test-only'};
const slot='2026-11-01T06:37:00Z';
assert.equal(targetDate(slot),'2026-10-31');
assert.equal(targetDate('2027-01-01T06:37:00Z'),'2026-12-31');
assert.equal(actionForTime('2026-10-24T05:37:00Z'),'C3_UPDATE'); // summer time
assert.equal(actionForTime('2026-10-25T06:37:00Z'),'C3_UPDATE'); // winter time
assert.equal(actionForTime('2026-10-25T05:37:00Z'),'NOTHING');
assert.equal(actionForTime('2026-11-01T09:37:00Z'),'C3_UPDATE');
let calls=[];
function mock({last='2026-10-30', daily=[], pages=[], publicDate='2026-10-31', publicStatus=200}={}) {
  return async(url,opts={})=>{
    calls.push({url,opts});
    if(url.startsWith(PUBLIC_MANIFEST)) {
      assert.equal(opts.headers?.Authorization,undefined,'Never send the GitHub token to the public site');
      return publicStatus===200 ? Response.json({schema_version:1,last_date:publicDate}) : new Response(null,{status:publicStatus});
    }
    assert.ok(url.startsWith(`https://api.github.com/repos/${REPOSITORY}/`));
    assert.equal(opts.headers.Authorization,'Bearer test-only');
    if(url.includes('/contents/'))return Response.json({encoding:'base64',content:btoa(JSON.stringify({end:last}))});
    if(url.endsWith('/dispatches'))return new Response(null,{status:204});
    if(url.includes(`/workflows/${WORKFLOW}/runs`))return Response.json({workflow_runs:daily});
    if(url.includes(`/workflows/${PAGES_WORKFLOW}/runs`))return Response.json({workflow_runs:pages});
    throw Error('Unexpected request: '+url);
  };
}
assert.equal((await dispatchIfNeeded(slot,{},mock())).status,'disabled');
assert.equal(calls.length,0);
assert.equal((await dispatchIfNeeded('2026-11-01T08:00:00Z',env,mock())).status,'outside_slot');
assert.equal(calls.length,0);
assert.equal((await dispatchIfNeeded(slot,env,mock({last:'2026-10-31'}))).status,'already_current');
assert.equal((await dispatchIfNeeded(slot,env,mock({daily:[{status:'queued'}]}))).status,'already_running');
calls=[];
assert.equal((await dispatchIfNeeded(slot,env,mock())).status,'dispatch_accepted');
let post=calls.find(c=>c.opts.method==='POST');
assert.ok(post.url.includes(`/workflows/${WORKFLOW}/dispatches`));
assert.equal(JSON.parse(post.opts.body).inputs.target_date,'2026-10-31');
assert.equal(JSON.parse(post.opts.body).inputs.apply,true);

// Data already committed, but Pages failed, is old, or has no manifest: repair only Pages.
for(const config of [
  {last:'2026-10-31',publicDate:'2026-10-30'},
  {last:'2026-10-31',publicStatus:404},
  {last:'2026-10-31',pages:[{status:'completed',conclusion:'failure'}]}
]) {
  calls=[];
  assert.equal((await dispatchIfNeeded(slot,env,mock(config))).status,'publication_dispatch_accepted');
  post=calls.find(c=>c.opts.method==='POST');
  assert.ok(post.url.includes(`/workflows/${PAGES_WORKFLOW}/dispatches`));
  assert.deepEqual(JSON.parse(post.opts.body),{ref:'main'});
  assert.equal(calls.filter(c=>c.opts.method==='POST').length,1);
}
calls=[];
assert.equal((await dispatchIfNeeded(slot,env,mock({last:'2026-10-31',publicDate:'2026-10-30',pages:[{status:'in_progress'}]}))).status,'publication_already_running');
assert.equal(calls.filter(c=>c.opts.method==='POST').length,0);
await assert.rejects(dispatchIfNeeded(slot,env,async()=>new Response(null,{status:503})),/HTTP 503/);
await assert.rejects(dispatchIfNeeded(slot,env,mock({last:'2026-10-31',publicStatus:503})),/public check failed: HTTP 503/);
const response=await worker.fetch(new Request('https://example.test/'),{});
assert.equal((await response.json()).http_dispatch,false);
console.log('C3 Worker: read-only HTTP, C3-only token/dispatch, DST, dates, duplicate prevention, API errors and Pages recovery checks passed.');
