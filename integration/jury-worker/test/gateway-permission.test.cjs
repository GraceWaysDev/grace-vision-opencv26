'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const t=JSON.parse(fs.readFileSync(path.join(__dirname,'../gateway.json'),'utf8'));
const r=t.Resources;
const p=r.InvokePermission.Properties;
test('no integration credential or execution IAM role remains',()=>{
  assert.equal(Object.hasOwn(r.InvokeMethod.Properties.Integration,'Credentials'),false);
  assert.equal(Object.values(r).some(x=>x.Type.startsWith('AWS::IAM::')),false);
  assert.equal(JSON.stringify(t).includes('InvokeRole'),false);
});
test('exactly one resource permission and no alternate resource policy',()=>{
  assert.equal(Object.values(r).filter(x=>x.Type==='AWS::Lambda::Permission').length,1);
  assert.equal(Object.values(r).some(x=>x.Type==='AWS::Lambda::ResourcePolicy'),false);
  assert.deepEqual(Object.keys(p).sort(),['Action','FunctionName','Principal','SourceAccount','SourceArn']);
});
test('only API Gateway may invoke the existing function in this account',()=>{
  assert.equal(p.Action,'lambda:InvokeFunction');
  assert.equal(p.Principal,'apigateway.amazonaws.com');
  assert.deepEqual(p.FunctionName,{Ref:'ExistingFunctionName'});
  assert.deepEqual(p.SourceAccount,{Ref:'AWS::AccountId'});
});
test('source is the exact API stage method and path with no wildcard',()=>{
  assert.equal(r.Stage.Properties.StageName,'jury');
  assert.equal(r.InvokeMethod.Properties.HttpMethod,'POST');
  assert.equal(r.InvokeResource.Properties.PathPart,'invoke');
  const source=p.SourceArn['Fn::Sub'];
  const expected='arn:${AWS::Partition}:execute-api:${AWS::Region}:${AWS::AccountId}:${Gateway}/jury/POST/invoke';
  assert.equal(source===expected,true,'Source scope must be exact');
  assert.equal(source.includes('*'),false);
});
test('deployment waits for method and permission without a stage cycle',()=>{
  assert.deepEqual(r.DeploymentSinglePhoto.DependsOn,['InvokeMethod','InvokePermission']);
  assert.deepEqual(r.Stage.Properties.DeploymentId,{Ref:'DeploymentSinglePhoto'});
  assert.equal(JSON.stringify(r.InvokePermission).includes('${Stage}'),false);
  assert.equal(JSON.stringify(r.InvokePermission).includes('"Ref":"Stage"'),false);
  const edges={};
  for(const [id,res]of Object.entries(r)){
    const deps=new Set([].concat(res.DependsOn||[]));
    function visit(v){if(!v||typeof v!=='object')return;
      if(typeof v.Ref==='string'&&r[v.Ref])deps.add(v.Ref);
      if(Array.isArray(v['Fn::GetAtt']))deps.add(v['Fn::GetAtt'][0]);
      if(typeof v['Fn::Sub']==='string')for(const m of v['Fn::Sub'].matchAll(/\$\{([^}.]+)(?:\.[^}]+)?\}/g))if(r[m[1]])deps.add(m[1]);
      for(const child of Object.values(v))visit(child);
    }
    visit(res.Properties);edges[id]=[...deps];
  }
  function walk(id,active=new Set()){assert.equal(active.has(id),false,'Dependency cycle');for(const dep of edges[id]||[])walk(dep,new Set([...active,id]));}
  for(const id of Object.keys(edges))walk(id);
});
test('API key and request validation remain required',()=>{
  assert.equal(r.InvokeMethod.Properties.ApiKeyRequired,true);
  assert.deepEqual(r.InvokeMethod.Properties.RequestValidatorId,{Ref:'EventValidator'});
  assert.equal(r.GatewayKey.Properties.Enabled,true);
  assert.deepEqual(r.UsagePlanKey.Properties,{KeyId:{Ref:'GatewayKey'},KeyType:'API_KEY',UsagePlanId:{Ref:'UsagePlan'}});
});
test('daily quota and both throttling controls remain unchanged',()=>{
  assert.deepEqual(r.UsagePlan.Properties.Quota,{Limit:40,Period:'DAY'});
  assert.deepEqual(r.UsagePlan.Properties.Throttle,{RateLimit:2,BurstLimit:2});
  assert.equal(r.Stage.Properties.MethodSettings[0].ThrottlingRateLimit,2);
  assert.equal(r.Stage.Properties.MethodSettings[0].ThrottlingBurstLimit,2);
});
test('regional endpoint and project tags preserved',()=>{
  assert.deepEqual(r.Gateway.Properties.EndpointConfiguration,{Types:['REGIONAL']});
  const tags=[{Key:'Project',Value:'GraceVision'},{Key:'Competition',Value:'OpenCV-AI-Competition-2026'},{Key:'Environment',Value:'competition-demo'},{Key:'ManagedBy',Value:'CloudFormation'}];
  for(const id of ['Gateway','Stage','GatewayKey','UsagePlan'])assert.deepEqual(r[id].Properties.Tags,tags);
});
test('no additional storage function image or domain resources',()=>{
  assert.deepEqual(Object.keys(r).sort(),['DeploymentSinglePhoto','EventModel','EventValidator','Gateway','GatewayKey','InvokeMethod','InvokePermission','InvokeResource','Stage','UsagePlan','UsagePlanKey']);
  assert.equal(Object.values(r).some(x=>/^AWS::(?:S3|ECR|IAM)::/.test(x.Type)||x.Type==='AWS::Lambda::Function'||x.Type.includes('Domain')),false);
  assert.deepEqual(Object.keys(t.Parameters),['ExistingFunctionName']);
  assert.equal(t.Parameters.ExistingFunctionName.NoEcho,true);
});
test('function integration is still direct and references only existing input',()=>{
  assert.equal(r.InvokeMethod.Properties.Integration.Type,'AWS');
  assert.equal(r.InvokeMethod.Properties.Integration.IntegrationHttpMethod,'POST');
  assert.equal(r.InvokeMethod.Properties.Integration.Uri['Fn::Sub'].endsWith(':function:${ExistingFunctionName}/invocations'),true);
  assert.equal(r.InvokeMethod.Properties.Integration.RequestTemplates['application/json'],"$input.json('$')");
});
test('template contains no literal account secret or function value',()=>{
  assert.equal(Object.hasOwn(t.Parameters.ExistingFunctionName,'Default'),false);
  const text=JSON.stringify(t);
  assert.equal(/\b\d{12}\b|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|X-Amz-Signature|https:\/\/[^\s"]+\.amazonaws\.com/i.test(text),false);
});
