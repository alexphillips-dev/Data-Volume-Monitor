import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const root=new URL('../source/usr/local/emhttp/plugins/dvm/',import.meta.url);
const helper=new URL('js/dvm-outcomes.js',root);
function harness(){
    const nodes=[],opened=[];let polling;
    function $(tag){
        const node={tag,children:[],value:'',props:{},handlers:{},
            text(value){node.value=String(value);return node;},
            append(child){node.children.push(child);return node;},
            empty(){node.children=[];return node;},
            attr(key,value){node.props[key]=value;return node;},
            prop(key,value){node.props[key]=value;return node;},
            on(key,fn){node.handlers[key]=fn;return node;}};
        nodes.push(node);return node;
    }
    const body=$('tbody'),status=$('status');
    const context={$,confirmResult:true,confirm(){return context.confirmResult;},openBox(...args){opened.push(args);},
        DVMPoll:{create(options){polling=options;return {start(){},stop(){}};},annotate(){}}};
    context.window=context;vm.createContext(context);
    if(fs.existsSync(helper))vm.runInContext(fs.readFileSync(helper,'utf8'),context);
    assert.ok(context.DVMOutcomes,'the settings page must provide action status and deliberate retries');
    const api=context.DVMOutcomes.create(body,status);
    const record={rule:'secondary-1',interface:'eth0',state:'exceeded',status:'failed',updated_at:'2026-11-04T12:00:00Z',attempts:1,
        components:{docker:{status:'failed',reason:'exit status 1'}},retryable:true};
    return {context,nodes,body,opened,api,polling,record,
        render(record){polling.render({outcomes:{success:true,outcomes:[record]}});polling.onState({phase:'fresh',lastSuccess:1});},
        retry(){return nodes.filter(n=>n.tag==='<button>').at(-1);}};
}
const cases={
    'rendering failed actions never automatically retries them'(){const h=harness();h.render(h.record);assert.equal(h.opened.length,0);},
    'outcome labels and reasons remain literal text'(){const h=harness();h.record.interface='<img src=x onerror=bad>';h.render(h.record);assert.ok(h.nodes.some(n=>n.value===h.record.interface));assert.ok(h.nodes.some(n=>n.value.includes('exit status 1')));},
    'only a confirmed fresh failed rule can run the fixed retry command'(){const h=harness();h.render(h.record);h.context.confirmResult=false;h.retry().handlers.click();assert.equal(h.opened.length,0);h.context.confirmResult=true;h.retry().handlers.click();assert.equal(h.opened[0][0],'/usr/local/emhttp/plugins/dvm/scripts/retry_action secondary-1');},
    'stale or unconfirmed action outcomes cannot be retried'(){const h=harness();h.render(h.record);h.polling.onState({phase:'stale',lastSuccess:1});h.retry().handlers.click();assert.equal(h.opened.length,0);assert.equal(h.retry().props.disabled,true);h.record.status='running';h.render(h.record);assert.equal(h.retry().props.disabled,true);assert.ok(h.nodes.some(n=>n.value.includes('completion unconfirmed')));},
    'malformed rule tokens never become shell arguments'(){for(const token of ['secondary-1;id','secondary-10','primary-h-rx\n','primary-h-rx\r','primary-h-rx\u2028','primary-h-rx\u2029','secondary-1 extra']){const h=harness();h.record.rule=token;h.render(h.record);h.retry().handlers.click();assert.equal(h.opened.length,0);}},
    'testing configured actions needs explicit confirmation'(){const h=harness();h.context.confirmResult=false;h.api.testActions();assert.equal(h.opened.length,0);h.context.confirmResult=true;h.api.testActions();assert.equal(h.opened[0][0],'/usr/local/emhttp/plugins/dvm/scripts/test_actions');},
    'the native settings page exposes separate diagnostic and action controls'(){const page=fs.readFileSync(new URL('DVMcontrol.page',root),'utf8');assert.match(page,/id="TESTACTIONS"[^>]+value="Test Configured Actions"/);assert.match(page,/Service Check only diagnoses/);assert.match(page,/id="dvm_outcomes_body"/);assert.match(page,/dvm-outcomes\.js/);}
};
let failed=0;for(const [name,test]of Object.entries(cases)){try{test();console.log('PASS '+name);}catch(e){failed++;console.error('FAIL '+name+': '+e.message);}}if(failed)process.exitCode=1;
