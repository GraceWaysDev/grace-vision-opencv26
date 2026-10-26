import {DemoError,sha256,releaseTrace} from './adapters.mjs';
export class VisionSession {
 constructor(adapter){this.adapter=adapter;this.reset();}
 reset(){releaseTrace(this.trace);this.photos=[];this.trace=null;this.mainImage=null;this.busy=false;this.generation=(this.generation||0)+1;}
 async select(files){
  this.reset();const generation=this.generation;
  if(files.length<1||files.length>5)throw new DemoError('COUNT');
  const photos=[];
  for(const file of files){const bytes=(await file.arrayBuffer()).slice(0);if(bytes.byteLength>12*1024*1024||!['image/png','image/jpeg'].includes(file.type))throw new DemoError('FORMAT');photos.push({bytes,type:file.type,sha256:await sha256(bytes)});}
  if(generation!==this.generation)return;
  this.photos=photos;
 }
 async analyze(options){
  releaseTrace(this.trace);this.trace=null;this.mainImage=null;this.busy=true;const generation=this.generation;
  try{const trace=await this.adapter.analyze(this.photos,options);if(generation===this.generation)this.trace=trace;else releaseTrace(trace);return trace;}finally{this.busy=false;}
 }
 async decide(choice){
  if(!this.trace||this.busy)throw new DemoError('NO_SELECTION');
  for(const photo of this.photos)if(await sha256(photo.bytes)!==photo.sha256)throw new DemoError('INTEGRITY');
  const approval=await this.adapter.decide(this.trace,choice);this.trace.approval=approval;
  if(approval.status==='APPROVED_DEMO')this.mainImage={sha256:approval.sha256,choice,index:this.trace.selected};
  return approval;
 }
}
