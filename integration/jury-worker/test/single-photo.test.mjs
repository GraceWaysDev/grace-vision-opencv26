import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {World,fixture,publicRoot} from './fakes.mjs';
import {sha} from '../security.mjs';
import {protocol} from '../protocol.mjs';
import {MockAdapter} from '../public/src/adapters.mjs';
import {VisionSession} from '../public/src/session.mjs';
import {messages} from '../public/src/i18n.mjs';
const file=name=>({type:'image/png',arrayBuffer:async()=>Uint8Array.from(fixture(name)).buffer});
for(const [name,decision,choice] of [['suitable','ACCEPT_ORIGINAL','ORIGINAL'],['correctable','ENHANCE','PROPOSAL'],['unusable','REQUEST_NEW_PHOTO','REQUEST_NEW_PHOTO']]){
 test('single real-protocol fake '+decision,async()=>{
  const w=new World();await w.config();const r=await w.analyze([name]);
  assert.equal(r.status,200);assert.equal(r.body.decision,decision);assert.equal(r.body.items.length,1);
  assert.equal(r.body.selected,name==='unusable'?null:0);assert.equal(r.body.opencv_version,'5.0.0');
  assert.equal(r.body.approval,null);assert.equal(r.body.published,false);assert.equal(w.consumed,3);
  assert.equal(w.calls.filter(c=>c.kind==='upload').length,1);
  assert.equal(r.body.items[0].original_sha256,await sha(fixture(name)));
  assert.equal(r.body.proposalBytes!==null,name==='correctable');
  if(name==='correctable'){assert(r.body.items[0].after);assert.equal(await sha(Buffer.from(r.body.proposalBytes.base64,'base64')),r.body.items[0].proposal_sha256);}
  const a=await w.decide(r.body.token,choice);assert.equal(a.status,200);assert.equal(a.body.published,false);assert.equal(w.consumed,4);
  const f=[...w.jobs.values()][0];assert.deepEqual(f.objects.get('originals/'+f.id+'/0.png'),fixture(name));
 });
 test('single mock '+decision+' human gate',async()=>{
  const fixtures=JSON.parse(fs.readFileSync(publicRoot+'/assets/fixtures.json','utf8'));
  const s=new VisionSession(new MockAdapter(fixtures));await s.select([file(name)]);await s.analyze({rights:true});
  assert.equal(s.trace.decision,decision);assert.equal(s.mainImage,null);assert.equal(s.photos.length,1);
  await s.decide(choice);assert.equal(s.mainImage!==null,name!=='unusable');assert.equal(s.trace.published,false);
 });
}
for(const n of [0,6])test('count '+n+' rejected in client, worker and protocol before transport',async()=>{
 const session=new VisionSession(new MockAdapter({}));await assert.rejects(session.select(Array(n).fill(file('unusable'))),/COUNT/);
 const w=new World();await w.config();assert.equal((await w.analyze(Array(n).fill('unusable'))).status,400);assert.equal(w.calls.length,0);
 let calls=0;await assert.rejects(protocol({},async()=>{calls++;}).analyze(Array(n).fill({})));assert.equal(calls,0);
});
for(const n of [1,2,3,4,5])test('client and worker permit '+n+' photos',async()=>{
 const s=new VisionSession(new MockAdapter({}));await s.select(Array(n).fill(file('unusable')));assert.equal(s.photos.length,n);
 const w=new World();await w.config();assert.equal((await w.analyze(Array(n).fill('unusable'))).status,200);assert.equal(w.calls.filter(c=>c.kind==='upload').length,n);
});
test('single image rights and Turnstile guards remain before gateway',async()=>{
 const w=new World();await w.config();assert.equal((await w.analyze(['suitable'],{rights:false})).status,400);assert.equal(w.calls.length,0);
 assert.equal((await w.analyze(['suitable'],{challenge:'synthetic-invalid'})).status,400);assert.equal(w.consumed,0);
});
test('gateway array model and DE/EN explicitly permit one photo',()=>{
 const t=JSON.parse(fs.readFileSync(new URL('../gateway.json',import.meta.url),'utf8'));
 const model=t.Resources.EventModel.Properties.Schema.oneOf.find(x=>x.properties.operation.enum.includes('create'));
 assert.equal(model.properties.uploads.minItems,1);assert.equal(model.properties.uploads.maxItems,5);
 assert.match(messages.de.photos,/1–5.*ein Foto genügt/);assert.match(messages.en.photos,/1–5.*one photo is enough/);
 assert.equal(messages.de.COUNT,'Bitte ein bis fünf Fotos auswählen.');assert.equal(messages.en.COUNT,'Please select one to five photos.');
});
