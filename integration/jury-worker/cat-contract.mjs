import {check} from './security.mjs';
export const CAT_POLICY='cat-frame-1';
export const CAT_MODEL={name:'OpenCV Zoo YOLOX-S COCO',version:'2022nov',sha256:'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063',revision:'48b10fa505aeb51fbd127fc60a5c660040e823b7',backend:'OpenCV DNN CPU',class:'cat'};
export const CAT_REASONS=['CAT_NOT_RELIABLE','MULTIPLE_CATS','CAT_EDGE_UNCERTAIN','CAT_FRAME_OK','CAT_CROP_RESOLUTION','CAT_MARGIN_UNCERTAIN','CAT_CROP_RECOMMENDED'];
export function catModel(v){check(v&&Object.keys(v).length===Object.keys(CAT_MODEL).length&&Object.entries(CAT_MODEL).every(([k,x])=>v[k]===x));return {...CAT_MODEL};}
export function catInfo(v,m){
 check(v&&typeof v.detected==='boolean'&&Number.isInteger(v.count)&&v.count>=0&&v.count<=20&&v.detected===(v.count>0));
 const fraction=n=>Number.isFinite(n)&&n>=0&&n<=1;
 const box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isInteger)&&b[0]>=0&&b[1]>=0&&b[2]>b[0]&&b[3]>b[1]&&b[2]<=m.width&&b[3]<=m.height;
 check(fraction(v.confidence)&&typeof v.edge_contact==='boolean'&&v.visibility==='HUMAN_REVIEW_REQUIRED'&&CAT_REASONS.includes(v.reason)&&['ACCEPT_ORIGINAL','ENHANCE','TRY_NEXT_IMAGE'].includes(v.action));
 check(Array.isArray(v.detections)&&v.detections.length===v.count);
 const detections=v.detections.map(d=>{check(box(d.bbox)&&fraction(d.confidence)&&fraction(d.area_fraction)&&fraction(d.center_offset)&&typeof d.edge_contact==='boolean');return {bbox:d.bbox,confidence:d.confidence,area_fraction:d.area_fraction,center_offset:d.center_offset,edge_contact:d.edge_contact};});
 check(v.count===1?box(v.bbox)&&fraction(v.area_fraction)&&fraction(v.center_offset):v.bbox===null&&v.area_fraction===null&&v.center_offset===null);
 if(v.crop!==null){check(box(v.crop)&&Array.isArray(v.crop_resolution)&&v.crop_resolution.length===2&&v.crop_resolution[0]===v.crop[2]-v.crop[0]&&v.crop_resolution[1]===v.crop[3]-v.crop[1]);}else check(v.crop_resolution===null);
 if(v.action==='ACCEPT_ORIGINAL')check(v.count===1&&v.confidence>=.60&&!v.edge_contact&&v.area_fraction>=.25&&v.center_offset<=.20&&v.reason==='CAT_FRAME_OK');
 if(v.action==='ENHANCE')check(v.count===1&&v.confidence>=.60&&!v.edge_contact&&v.reason==='CAT_CROP_RECOMMENDED'&&v.crop_resolution.every(n=>n>=480));
 return {detected:v.detected,count:v.count,confidence:v.confidence,bbox:v.bbox,area_fraction:v.area_fraction,center_offset:v.center_offset,edge_contact:v.edge_contact,visibility:v.visibility,crop:v.crop,crop_resolution:v.crop_resolution,reason:v.reason,action:v.action,detections};
}
