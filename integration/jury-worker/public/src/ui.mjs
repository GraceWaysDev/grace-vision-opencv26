import {MockAdapter,AwsAdapter,sha256,DemoError,verifyProposal,releaseTrace} from './adapters.mjs';
import {VisionSession} from './session.mjs';
import {translateText,statusText} from './i18n.mjs';
const $=id=>document.getElementById(id);
const fixtures=await fetch('assets/fixtures.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('fixtures');return r.json()});
const mock=new MockAdapter(fixtures),session=new VisionSession(mock);let lang='de',statusKey='ready',isError=false,urls=[],visibilityReviewed=false;
let awsCapability=null,challenge=null,widgetId=null;
function loadChallenge(){if(!awsCapability||widgetId!==null)return;widgetId='loading';const script=document.createElement('script');script.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';script.onload=()=>{widgetId=window.turnstile.render('#turnstile',{sitekey:awsCapability.siteKey,action:'gracevision-job',callback:value=>{challenge=value;render();},'expired-callback':()=>{challenge=null;render();},'error-callback':()=>{challenge=null;status('BRIDGE_REJECTED',true);render();}});};script.onerror=()=>{challenge=null;status('BRIDGE_REJECTED',true);render();};document.head.append(script);}
const t=key=>translateText(lang,key==='metrics'&&session.trace?.mode==='aws'?'metricsAws':key);
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n};
function status(key,error=false){statusKey=key;isError=error;$('status').textContent=statusText(lang,key,$('mode').value);$('status').classList.toggle('error',error);}
function resetUrls(){releaseTrace(session.trace);for(const u of urls)URL.revokeObjectURL(u);urls=[];}
function figure(src,label,hash){const f=node('figure',undefined,'photo-card');const image=node('img');image.src=src;image.alt=label;f.append(image,node('figcaption',label),node('p','SHA-256: '+hash,'hash'));return f;}
function catTable(item){
 const section=node('section');section.append(node('h4',t('catTitle')),node('p',t(item.cat.reason)),node('p',t('catLimit')));
 const table=node('table');table.append(node('caption',t('catTitle')));const head=node('tr');for(const key of ['metrics','before',...(item.after_cat?['after']:[])])head.append(node('th',t(key)));table.append(head);
 const value=(c,key)=>{if(key==='catDetected')return t(c.detected?'catYes':'catNo');if(key==='catCount')return String(c.count);if(key==='catConfidence')return (c.confidence*100).toFixed(1)+'%';if(key==='catBbox')return c.bbox?c.bbox.join(', '):t('catUnknown');if(key==='catArea')return c.area_fraction===null?t('catUnknown'):(c.area_fraction*100).toFixed(1)+'%';if(key==='catCenter')return c.center_offset===null?t('catUnknown'):(c.center_offset*100).toFixed(1)+'%';if(key==='catEdge')return t(c.edge_contact?'catYes':'catNo');if(key==='catResolution')return c.crop_resolution?c.crop_resolution.join(' × '):t('catNotCropped');return c.crop?c.crop.join(', '):t('catNotCropped');};
 for(const key of ['catDetected','catCount','catConfidence','catBbox','catArea','catCenter','catEdge','catResolution','catCrop']){const row=node('tr');row.append(node('th',t(key)));for(const c of [item.cat,...(item.after_cat?[item.after_cat]:[])])row.append(node('td',value(c,key)));table.append(row);}const scroll=node('div',undefined,'measurement');scroll.append(table);section.append(scroll);return section;
}
function originals(){const wrap=$('originals');wrap.replaceChildren();session.photos.forEach((photo,i)=>{wrap.append(figure(urls[i],t('original')+' · '+t('photo')+' '+(i+1),photo.sha256))});}
function render(){
 document.documentElement.lang=lang;document.title=t('title');document.querySelectorAll('[data-t]').forEach(n=>n.textContent=t(n.dataset.t));
 $('run').textContent=t($('mode').value==='aws'?'awsRun':'run');$('run').disabled=session.busy||($('mode').value==='aws'&&(!awsCapability||!challenge));$('awsNotice').hidden=$('mode').value!=='aws'||!!awsCapability;
 $('turnstile').hidden=$('mode').value!=='aws';
 $('runtime').textContent=($('mode').value==='aws'?t('awsLive'):t('mock'))+' · OpenCV 5.0.0';document.querySelector('.mode-badge').textContent=$('mode').value==='aws'?t('awsLive'):t('mock');document.querySelector('.mock-note').hidden=$('mode').value==='aws';
 $('status').textContent=statusText(lang,statusKey,$('mode').value);$('status').classList.toggle('error',isError);originals();
 $('mainImage').hidden=!session.mainImage;$('mainEmpty').hidden=!!session.mainImage;$('mainHash').textContent='';
 if(session.mainImage){const m=session.mainImage,item=session.trace.items[m.index];$('mainImage').src=m.choice==='ORIGINAL'?urls[m.index]:item.proposal;$('mainImage').alt=t(m.choice==='ORIGINAL'?'original':'proposal');$('mainHash').textContent='SHA-256: '+m.sha256;}
 const trace=session.trace;$('result').hidden=!trace;if(!trace)return;
 $('decision').textContent=t(trace.decision);$('details').replaceChildren();
 for(const item of trace.items){
  const article=node('article');article.append(node('h3',t('photo')+' '+(item.index+1)+' · '+t(item.action)));
  article.append(node('p',t(item.action==='ENHANCE'?'enhanceReason':item.action==='TRY_NEXT_IMAGE'?'rejectReason':'passReason')));
  if(trace.mode==='aws'){article.lastChild.textContent=item.reasons.map(reason=>t(reason)).join(' ');}
  if(item.cat)article.append(catTable(item));
  if(item.index===trace.selected){const comparison=node('div',undefined,'comparison');comparison.append(figure(urls[item.index],t('original'),item.original_sha256));if(item.action==='ENHANCE')comparison.append(figure(item.proposal,t('proposal'),item.proposal_sha256));article.append(comparison);}
  const table=node('table');table.append(node('caption',t('metrics')));const head=node('tr');for(const key of ['metrics','before',...(item.after?['after']:[])]){const th=node('th',t(key));th.scope='col';head.append(th)}table.append(head);
  for(const key of ['resolution','sharpness','brightness','contrast','dark','over']){
   const row=node('tr');const th=node('th',t(key));th.scope='row';row.append(th);
   for(const m of [item.metrics,...(item.after?[item.after]:[])]){const value=key==='resolution'?`${m.width} × ${m.height}`:key==='dark'?(m.dark_fraction*100).toFixed(3)+'%':key==='over'?(m.overexposed_fraction*100).toFixed(3)+'%':m[key].toFixed(3);row.append(node('td',value));}table.append(row);
  }
  const scroll=node('div',undefined,'measurement');scroll.append(table);article.append(scroll);$('details').append(article);
 }
 const item=trace.items[trace.selected??0];
 const values=[`${t('brightness')}: ${item.metrics.brightness.toFixed(3)}; ${t('sharpness')}: ${item.metrics.sharpness.toFixed(3)}; ${t('contrast')}: ${item.metrics.contrast.toFixed(3)}`,t(item.action),trace.selected===null?t('noSelection'):t('photo')+' '+(trace.selected+1),t(trace.decision),trace.approval?t({ORIGINAL:'approveOriginal',PROPOSAL:'approveProposal',REJECT:'decline',REQUEST_NEW_PHOTO:'request'}[trace.approval.choice]):t('pending')];
 if(trace.cat_model){values[0]+=' · '+trace.cat_model.name+' '+trace.cat_model.version+' · '+t('catConfidence')+': '+(item.cat.confidence*100).toFixed(1)+'% · '+t('catArea')+': '+(item.cat.area_fraction===null?t('catUnknown'):(item.cat.area_fraction*100).toFixed(1)+'%');}
 $('trace').replaceChildren();['measureStep','qualityStep','selectionStep','actionStep','humanStep'].forEach((key,i)=>{const li=node('li');li.append(node('strong',t(key)),node('span',values[i]));$('trace').append(li)});
 for(const button of $('review').querySelectorAll('button'))button.disabled=!!trace.approval||session.busy;
 $('approveOriginal').disabled=!!trace.approval||trace.selected===null;
 if(trace.mode==='aws'){$('approveOriginal').disabled=!!trace.approval||trace.decision!=='ACCEPT_ORIGINAL';$('decline').disabled=true;}
 $('approveProposal').disabled=!!trace.approval||trace.selected===null||item.action!=='ENHANCE';
 let visibility=$('visibilityReview');if(trace.cat_policy){if(!visibility){visibility=node('label');visibility.id='visibilityReview';const input=node('input');input.type='checkbox';input.id='catVisibility';input.addEventListener('change',()=>{visibilityReviewed=input.checked;render();});visibility.append(input,node('span'));$('review').prepend(visibility);}visibility.hidden=false;visibility.querySelector('span').textContent=t('catReview');visibility.querySelector('input').checked=visibilityReviewed;visibility.querySelector('input').disabled=!!trace.approval;$('approveOriginal').disabled||=!visibilityReviewed;$('approveProposal').disabled||=!visibilityReviewed;}else if(visibility)visibility.hidden=true;
}
async function select(files){
 resetUrls();visibilityReviewed=false;$('rights').checked=false;
 try{await session.select(files);urls=session.photos.map(p=>URL.createObjectURL(new Blob([p.bytes],{type:p.type})));status('selected');}catch(e){status(e.code||'UNEXPECTED',true)}render();
}
$('photos').addEventListener('change',()=>select([...$('photos').files]));
for(const button of document.querySelectorAll('[data-sample]'))button.addEventListener('click',async()=>{
 try{const names={accept:['suitable','unusable'],enhance:['correctable','unusable'],reject:['unusable','unusable']}[button.dataset.sample];const files=[];for(const name of names){const r=await fetch('assets/'+name+'.png',{cache:'no-store'});if(!r.ok)throw Error();files.push(new File([await r.arrayBuffer()],name+'.png',{type:'image/png'}));}await select(files);}catch{status('UNEXPECTED',true)}
});
$('run').addEventListener('click',async()=>{
 visibilityReviewed=false;$('samples').disabled=true;$('photos').disabled=true;$('mode').disabled=true;status('working');
 try{const pending=session.analyze({rights:$('rights').checked,failure:$('failure').value});render();await pending;
  for(const item of session.trace.items)if(item.proposal){if(session.trace.mode==='aws'){await verifyProposal(item);continue;}const r=await fetch(item.proposal,{cache:'no-store'});if(!r.ok||await sha256(await r.arrayBuffer())!==item.proposal_sha256)throw new DemoError('INTEGRITY');}
  status('done');
 }catch(e){releaseTrace(session.trace);session.trace=null;session.mainImage=null;status(e.code||'UNEXPECTED',true)}
 finally{$('samples').disabled=false;$('photos').disabled=false;$('mode').disabled=false;render();if(session.trace)$('decision').focus();}
});
for(const button of $('review').querySelectorAll('button'))button.addEventListener('click',async()=>{try{if(session.trace?.cat_policy&&['ORIGINAL','PROPOSAL'].includes(button.dataset.choice)&&!visibilityReviewed)throw new DemoError('CHOICE');const result=await session.decide(button.dataset.choice);status(result.status==='APPROVED_DEMO'?'approved':'denied');}catch(e){status(e.code||'UNEXPECTED',true)}render();});
$('language').addEventListener('change',()=>{lang=$('language').value;render()});
$('mode').addEventListener('change',()=>{session.adapter=$('mode').value==='mock'?mock:new AwsAdapter(awsCapability);session.reset();visibilityReviewed=false;resetUrls();status($('mode').value==='aws'?(awsCapability?'challenge':'AWS_DISABLED'):'ready');render();if($('mode').value==='aws')loadChallenge()});
$('animal').addEventListener('click',()=>{$('vision').scrollIntoView({behavior:'smooth'});});
$('search').addEventListener('input',()=>{$('animal').hidden=!'mira demo-001'.includes($('search').value.toLowerCase());});
addEventListener('pagehide',resetUrls);render();

try{const r=await fetch('/api/config',{credentials:'same-origin',redirect:'error',signal:AbortSignal.timeout(10000)});const c=await r.json();if(c.ready===true&&typeof c.csrf==='string'&&typeof c.siteKey==='string'){awsCapability={csrf:c.csrf,siteKey:c.siteKey,takeChallenge(){const value=challenge;challenge=null;if(window.turnstile&&widgetId!==null)window.turnstile.reset(widgetId);return value;}};const option=$('mode').querySelector('[value="aws"]');option.hidden=false;option.disabled=false;render();}}catch{/* fail closed */}
