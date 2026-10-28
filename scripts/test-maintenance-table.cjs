// Optional offline panel test using @grafana/data 13.2.4 and rxjs 7.8.2.
// Pass a directory where these dependencies are installed as the first argument.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const moduleRoot = path.resolve(process.argv[2] || process.cwd());
const d = require(require.resolve('@grafana/data', {paths:[moduleRoot]}));
const { lastValueFrom } = require(require.resolve('rxjs', {paths:[moduleRoot]}));
const definitions = JSON.parse(readFileSync(path.join(__dirname,
  '../grafana/host-maintenance-panels.json'), 'utf8'));
const panel = definitions.panels.find(p=>p.id===13);
global.window = {};
for (const info of Object.values(d.standardTransformers)) {
  if (!d.standardTransformersRegistry.getIfExists(info.id))
    d.standardTransformersRegistry.register({...info, transformation: () => info});
}
const now = Date.UTC(2026,9,27,12);
const rows = Array.from({length:10}, (_,i)=>({value:now,
  labels:{host:`test-${String(i).padStart(2,'0')}`,os:'Ubuntu 24.04.5 LTS',
    architecture:'x86_64',runtime:'VM / own kernel',kernel:'test',
    reboot_required:i<2?'Yes':'No',collection_status:'OK',
    last_successful_update_ms:String(now-86400000),
    last_package_upgrade_ms:String(now-172800000),update_source:'Test fixture'}}));
function frame(row) {
  return {refId:'A',length:1,fields:[
    {name:'Time',type:'time',config:{},values:[now]},
    {name:'Value',type:'number',config:{displayNameFromDS:JSON.stringify(row.labels)},
      labels:row.labels,values:[row.value]}]};
}
async function transform(input) {
  const out=await lastValueFrom(d.transformDataFrame(panel.transformations,input.map(frame)));
  assert.equal(out.length,1,'Table must have one merged frame');
  const names=out[0].fields.map(f=>d.getFieldDisplayName(f,out[0],out));
  return Array.from({length:out[0].length},(_,i)=>Object.fromEntries(
    out[0].fields.map((f,j)=>[names[j],f.values[i]])));
}
(async()=>{
  const old={...rows[0],value:now-1000,labels:{...rows[0].labels,os:'OLD VERSION'}};
  const result=await transform([...rows,old]);
  assert.equal(result.length,10);
  assert.equal(new Set(result.map(r=>r.Host)).size,10);
  assert.ok(result.every(r=>r['Operating system']==='Ubuntu 24.04.5 LTS'));
  assert.ok(result.every(r=>typeof r['Last successful update check']==='number'));
  assert.ok(result.every(r=>typeof r['Last checked']==='number'));
  assert.equal(result.filter(r=>r['Reboot needed']==='Yes').length,2);
  const bad={...rows[0],value:now+1000,labels:{...rows[0].labels,os:'Unknown',
    reboot_required:'Unknown',collection_status:'Unreachable / collection failed'}};
  delete bad.labels.last_package_upgrade_ms;
  const unknown=(await transform([...rows,bad])).find(r=>r.Host===bad.labels.host);
  assert.equal(unknown['Reboot needed'],'Unknown');
  assert.equal(unknown['Last package upgrade'],null);
  console.log('PASS: 10 rows, latest reading wins, numeric dates, failures replace old healthy state');
})().catch(e=>{console.error(e);process.exitCode=1});
