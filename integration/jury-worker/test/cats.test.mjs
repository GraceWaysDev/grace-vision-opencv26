import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {catInfo,catModel,CAT_MODEL,CAT_POLICY,CAT_REASONS} from '../cat-contract.mjs';
import {World} from './fakes.mjs';
import {messages} from '../public/src/i18n.mjs';
const m={width:800,height:640},d={bbox:[160,128,640,512],confidence:.9,area_fraction:.36,center_offset:0,edge_contact:false};
const base=()=>({detected:true,count:1,detections:[{...d}],...d,visibility:'HUMAN_REVIEW_REQUIRED',crop:null,crop_resolution:null,reason:'CAT_FRAME_OK',action:'ACCEPT_ORIGINAL'});
test('exact public model provenance and bounded cat metrics',()=>{assert.deepEqual(catModel(CAT_MODEL),CAT_MODEL);assert.deepEqual(catInfo(base(),m),base());});
for(const [key,value]of [['count',2],['confidence',Infinity],['bbox',[-1,0,800,640]],['reason','PRIVATE_INTERNAL_VALUE'],['visibility','FULLY_VISIBLE'],['edge_contact',true],['area_fraction',.1],['center_offset',.3],['crop',[0,0,900,640]]])test('unsafe cat field '+key+' rejected',()=>{assert.throws(()=>catInfo({...base(),[key]:value},m));});
test('wrong model and hash refused',()=>{assert.throws(()=>catModel({...CAT_MODEL,sha256:'a'.repeat(64)}));assert.throws(()=>catModel({...CAT_MODEL,private:'forbidden'}));});
for(const language of ['de','en'])for(const code of CAT_REASONS)test(language+' translates '+code,()=>{assert.equal(typeof messages[language][code],'string');assert(!messages[language][code].includes(code));});
test('cat policy present in fake AWS trace, approval explicit, four gateway calls',async()=>{const w=new World();await w.config();const r=await w.analyze(['correctable']);assert.equal(r.status,200);assert.equal(r.body.cat_policy,CAT_POLICY);assert.deepEqual(r.body.cat_model,CAT_MODEL);assert.equal(r.body.approval,null);assert(r.body.items[0].cat);assert(r.body.items[0].after_cat);assert.equal(w.consumed,3);const a=await w.decide(r.body.token,'PROPOSAL');assert.equal(a.status,200);assert.equal(a.body.published,false);assert.equal(w.consumed,4);});
test('no legacy result accepted if cat model evidence is absent',async()=>{const w=new World();const send=w.send.bind(w);w.send=async(u,o)=>{const r=await send(u,o);if(w.calls.at(-1)?.operation==='result'){const v=await r.json();delete v.result.trace.cat_policy;return new Response(JSON.stringify(v));}return r;};await w.config();const r=await w.analyze(['suitable']);assert.equal(r.status,400);assert.equal(r.body.error,'REQUEST_REJECTED');});
test('unknown or unsafe model result cannot leak through public protocol',async()=>{const w=new World();const send=w.send.bind(w);w.send=async(u,o)=>{const r=await send(u,o);if(w.calls.at(-1)?.operation==='result'){const v=await r.json();v.result.trace.items[0].cat.reason='untrusted';return new Response(JSON.stringify(v));}return r;};await w.config();assert.equal((await w.analyze(['suitable'])).status,400);});
test('CSP unchanged and no public model/real cat fixture',()=>{const headers=fs.readFileSync(new URL('../public/_headers',import.meta.url));assert.equal((awaitHash(headers)),'6210303c27c022f1be671dc0bf5bc11022066d0db4ad297dede27e781278557a');assert(!fs.existsSync(new URL('../public/model.onnx',import.meta.url)));assert(!fs.existsSync(new URL('../public/cc0-cat.jpg',import.meta.url)));});
import crypto from 'node:crypto';
function awaitHash(b){return crypto.createHash('sha256').update(b).digest('hex');}
