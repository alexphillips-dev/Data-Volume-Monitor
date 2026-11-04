import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import {spawnSync} from 'node:child_process';

const root = new URL('../source/usr/local/emhttp/plugins/dvm/', import.meta.url);
const footer = fs.readFileSync(new URL('DVMfooter.page', root), 'utf8').replace(/\r\n/g, '\n');
const inline = footer.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1]
    .split('$(function()')[0].replace(/<\?[\s\S]*?\?>/g, '30000');
const helperPath = new URL('js/dvm-poll.js', root);

function harness(script = inline, entry = 'getDVMFooter') {
    let clock = 1000, nextTimer = 1;
    const scheduled = new Map(), requests = [], elements = {}, events = {};
    function $(selector) {
        if (typeof selector === 'function') return selector();
        const item = elements[selector] ??= {attrs:{}, content:'', label:''};
        const api = {length:1,
            html(value) { if (arguments.length) { item.content=value; return api; } return item.content; },
            text(value) { item.label=value; return api; },
            attr(name,value) { if (arguments.length===1) return item.attrs[name]; item.attrs[name]=value; return api; },
            toggleClass() { return api; }, removeClass() { return api; }, addClass() { return api; },
            append() { return api; }, remove() { return api; }
        };
        return api;
    }
    function request(options, success) {
        const item = {options, success, fail:null, always:null, aborted:false};
        const api = {done(fn) {item.success=fn;return api;}, fail(fn) {item.fail=fn;return api;}, always(fn) {item.always=fn;return api;},
            abort() {item.aborted=true;item.fail?.({},'abort');item.always?.();}};
        requests.push(item);return api;
    }
    $.get=(url,data,success)=>request({url,data},success);
    $.ajax=options=>request(options);
    class ClockDate extends Date { constructor(...args) {super(...(args.length?args:[clock]));} static now(){return clock;} }
    const context={$,Date:ClockDate,timers:{},console,
        setTimeout(fn,delay) {const id=nextTimer++;scheduled.set(id,{fn,delay});return id;},
        clearTimeout(id) {scheduled.delete(id);},
        addEventListener(name,fn) {(events[name]??=[]).push(fn);},
        removeEventListener() {}
    };
    context.window=context;vm.createContext(context);
    if (fs.existsSync(helperPath)) vm.runInContext(fs.readFileSync(helperPath,'utf8'),context);
    vm.runInContext(script,context);
    context[entry]();
    return {context,requests,elements,scheduled,
        tick() {const next=scheduled.entries().next().value;if(!next)return;scheduled.delete(next[0]);clock+=next[1].delay;next[1].fn();},
        resolve(index,body) {requests[index].success?.(body);requests[index].always?.();},
        fail(index) {requests[index].fail?.({},'timeout');requests[index].always?.();},
        leave() {(events.pagehide??[]).forEach(fn=>fn());},
        restore() {(events.pageshow??[]).forEach(fn=>fn({persisted:true}));}
    };
}

const cases={
    'a pending request does not overlap the next refresh'() {
        const h=harness();h.tick();assert.equal(h.requests.length,1);
    },
    'requests have a finite timeout'() {
        const h=harness();assert.ok(h.requests[0].options.timeout>0 && h.requests[0].options.timeout<=30000);
    },
    'failed initial loads have an explicit unavailable state'() {
        const h=harness();h.fail(0);assert.equal(h.elements['#dvm_footer'].attrs['data-dvm-state'],'stale');
    },
    'failure preserves last-success data and recovery clears stale state'() {
        const h=harness();h.resolve(0,{success:{dataAvailable:true,response:'first'}});
        const target=h.elements['#dvm_footer'];
        const timestamp=target.attrs['data-dvm-last-success'];assert.ok(timestamp);
        h.tick();h.fail(1);
        assert.equal(target.content,'first');assert.equal(target.attrs['data-dvm-state'],'stale');
        assert.equal(target.attrs['data-dvm-last-success'],timestamp);
        h.tick();h.resolve(2,{success:{dataAvailable:true,response:'new'}});
        assert.equal(target.content,'new');assert.equal(target.attrs['data-dvm-state'],'fresh');
    },
    'late responses after leaving the page cannot update the display'() {
        const h=harness();h.leave();h.resolve(0,{success:{dataAvailable:true,response:'late'}});
        assert.notEqual(h.elements['#dvm_footer']?.content,'late');
    },
    'invalid backend responses retain prior values and mark them stale'() {
        const h=harness();h.resolve(0,{success:{dataAvailable:true,response:'first'}});h.tick();
        h.resolve(1,{error:{response:'fixture failure'}});
        assert.equal(h.elements['#dvm_footer'].content,'first');
        assert.equal(h.elements['#dvm_footer'].attrs['data-dvm-state'],'stale');
    },
    'metric query failure preserves last valid measurement while threshold-only errors remain fresh'() {
        const h=harness();h.resolve(0,{success:{dataAvailable:true,response:'first'}});
        const target=h.elements['#dvm_footer'], timestamp=target.attrs['data-dvm-last-success'];
        h.tick();h.resolve(1,{success:{dataAvailable:false,response:'backend error icons'}});
        assert.equal(target.content,'first');assert.equal(target.attrs['data-dvm-state'],'stale');
        assert.equal(target.attrs['data-dvm-last-success'],timestamp);
        h.tick();h.resolve(2,{success:{dataAvailable:true,response:'valid metrics with dvm-threshold-error'}});
        assert.equal(target.attrs['data-dvm-state'],'fresh');
        assert.equal(target.content,'valid metrics with dvm-threshold-error');
    },
    'each dashboard branch waits for a complete valid batch'() {
        const functions=[...footer.matchAll(/var dvmDashboardPoll = null;[\s\S]*?\n}\n(?=\$\(function|function addDVMDashboard)/g)];
        assert.equal(functions.length,2);
        for (const [source] of functions) {
            const h=harness(source.replace(/<\?[\s\S]*?\?>/g,'30000'),'getDVMDashboard');
            h.resolve(0,{success:{dataAvailable:true,response:'first mini'}});
            assert.notEqual(h.elements['.dvm_mini_dash'].content,'first mini');
            assert.equal(h.scheduled.size,0);
            h.resolve(1,{success:{dataAvailable:true,response:Array(10).fill('green-text').join(';')}});
            assert.equal(h.elements['.dvm_mini_dash'].content,'first mini');
            h.tick();h.resolve(2,{success:{dataAvailable:true,response:'partial new mini'}});h.fail(3);
            assert.equal(h.elements['.dvm_mini_dash'].content,'first mini');
            assert.equal(h.elements['.dvm_mini_dash'].attrs['data-dvm-state'],'stale');
            h.tick();h.resolve(4,{success:{dataAvailable:true,response:'invalid batch mini'}});h.resolve(5,{success:{dataAvailable:true,response:'too;few'}});
            assert.equal(h.elements['.dvm_mini_dash'].content,'first mini');
            assert.equal(h.elements['.dvm_mini_dash'].attrs['data-dvm-state'],'stale');
        }
    },
    'both report tables retain the last complete batch after a partial failure'() {
        const settings=fs.readFileSync(new URL('DVMsettings.page',root),'utf8');
        const script=settings.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1]
            .split('$(function()')[0].replace(/let filters = <\?[\s\S]*?\?>;/,'let filters = "";')
            .replace(/<\?[\s\S]*?\?>/g,'');
        const normalized=script.replace(/interval:\s*,/,'interval:30000,');
        const h=harness(normalized,'getDVMReports');
        h.resolve(0,{success:{dataAvailable:true,response:'full first'}});h.resolve(1,{success:{dataAvailable:true,response:'light first'}});
        assert.equal(h.elements['.dvm_report'].content,'full first');
        assert.equal(h.elements['.dvm_lightreport'].content,'light first');
        h.tick();h.resolve(2,{success:{dataAvailable:true,response:'partial newer'}});h.fail(3);
        assert.equal(h.elements['.dvm_report'].content,'full first');
        assert.equal(h.elements['.dvm_lightreport'].content,'light first');
        assert.match(h.elements['#dvm_reports_status'].label,/stale/);
    },
    'back-forward cache restoration resumes polling with old requests fenced out'() {
        const h=harness();h.leave();h.restore();
        assert.equal(h.requests.length,2);
        h.resolve(1,{success:{dataAvailable:true,response:'current'}});h.resolve(0,{success:{dataAvailable:true,response:'old'}});
        assert.equal(h.elements['#dvm_footer'].content,'current');
    },
    'footer title preserves backslash sequences as plain attribute text'() {
        const line=footer.split('\n').find(line=>line.includes('var dvm_footer ='));
        const value='A\\x27 onclick=bad';
        const encoded=Buffer.from(value).toString('base64');
        const php=`<?php $dvm_config_primary=htmlspecialchars(base64_decode('${encoded}'),ENT_QUOTES,'UTF-8'); $dvm_footer_descr='Last Day'; ?>${line}`;
        const rendered=spawnSync('php',{input:php,encoding:'utf8'});
        assert.equal(rendered.status,0,rendered.stderr);
        let title;
        const $=markup=>{
            title=markup.match(/title='([^']*)'/)?.[1];
            const item={attr(name,value){if(name==='title')title=value;return item;}};
            return item;
        };
        new Function('$',rendered.stdout)($);
        assert.equal(title,value+' / Last Day');
    }
};
let failures=0;
for(const [name,test] of Object.entries(cases)) {
    try {test();console.log(`PASS ${name}`);}
    catch(error) {failures++;console.error(`FAIL ${name}: ${error.message}`);}
}
if(failures)process.exitCode=1;
