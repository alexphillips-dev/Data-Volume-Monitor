import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const page = fs.readFileSync(new URL('../source/usr/local/emhttp/plugins/dvm/DVMeditor.page', import.meta.url), 'utf8');
const script = page.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1]
    .replace(/<\?[\s\S]*?\?>/g, 'default');

function harness() {
    const fields = {editfile: '', editdata: ''};
    const handlers = {}, props = {}, texts = {}, requests = [], messages = [], events = {};
    let value = '';
    const editor = {
        setSize() {}, setOption() {}, on() {}, setValue(next) { value = next; },
        getValue() { return value; }, save() { fields.editdata = value; }
    };
    function $(arg) {
        if (typeof arg === 'function') return arg();
        const name = arg.replace(/^#/, '');
        const element = {
            0: {}, click(fn) { handlers[name + '.click'] = fn; return element; },
            on(event, fn) { handlers[name + '.' + event] = fn; return element; },
            val(next) { if (arguments.length) fields[name] = next; return fields[name]; },
            prop(key, next) { if (arguments.length > 1) props[name + '.' + key] = next; return element; },
            text(next) { texts[name] = next; return element; },
            fileTreeAttach() {},
            serializeArray() { return Object.entries(fields).map(([name, value]) => ({name, value})); }
        };
        return element;
    }
    function request(url, data, callback) {
        const item = {url, data: structuredClone(data), resolve: callback};
        const api = {
            fail(fn) { item.reject = fn; return api; },
            always(fn) { item.settle = fn; return api; }
        };
        requests.push(item);
        return api;
    }
    $.getJSON = request;
    $.post = request;
    const context = {$, CodeMirror: {fromTextArea: () => editor}, swal: message => messages.push(message),
        confirmResult:true, confirm() {return context.confirmResult;}, location:'',
        addEventListener(name, fn) {events[name]=fn;}};
    context.window=context;
    vm.runInNewContext(script, context);
    return {fields, handlers, props, texts, requests, messages, editor, context,
        choose(path) { fields.editfile = path; handlers['editfile.change'](); },
        save() { handlers['btnSubmit.click'](); },
        resolve(index, value) { requests[index].resolve(value); requests[index].settle?.(); },
        reject(index, error = 'fixture read failed') { requests[index].reject?.({responseJSON: {error}}); requests[index].settle?.(); },
        wouldWarnOnLeave() {let prevented=false;events.beforeunload?.({preventDefault(){prevented=true;},returnValue:null});return prevented;}
    };
}

const cases = {
    'Save before the initial load does not write an empty file'() {
        const h = harness(); h.save();
        assert.equal(h.requests.filter(r => r.url.endsWith('dvm_save.php')).length, 0);
    },
    'A late previous-file response cannot replace current-file contents'() {
        const h = harness(); h.choose('/etc/vnstat/dvm-user-actions.sh');
        h.resolve(1, '# action script'); h.resolve(0, '# old vnstat config'); h.save();
        const payload = Object.fromEntries(h.requests.at(-1).data.map(({name, value}) => [name, value]));
        assert.equal(payload.editfile, '/etc/vnstat/dvm-user-actions.sh');
        assert.equal(payload.editdata, '# action script');
    },
    'Changing files blocks Save until the selected file loads'() {
        const h = harness(); h.resolve(0, 'original'); h.choose('/etc/vnstat/dvm-user-actions.sh'); h.save();
        assert.equal(h.requests.length, 2);
        assert.equal(h.props['btnSubmit.disabled'], true);
    },
    'A failed load cannot save prior contents into the selected file'() {
        const h = harness(); h.resolve(0, 'original'); h.choose('/etc/vnstat/dvm-user-actions.sh'); h.reject(1); h.save();
        assert.equal(h.requests.length, 2);
        assert.equal(h.props['btnSubmit.disabled'], true);
    },
    'Empty files remain editable and duplicate pending saves are blocked'() {
        const h = harness(); h.resolve(0, ''); h.save(); h.save();
        assert.equal(h.requests.length, 2);
        h.reject(1);
        assert.equal(h.props['btnSubmit.disabled'], false);
    },
    'Malformed load responses never become editable content'() {
        const h = harness(); h.resolve(0, {error: 'fixture'}); h.save();
        assert.equal(h.requests.length, 1);
    },
    'A completed prior save cannot enable Save during the next file load'() {
        const h = harness(); h.resolve(0, 'first'); h.save();
        h.choose('/etc/vnstat/dvm-user-actions.sh');
        h.resolve(1, {success:true, saved:'/etc/vnstat/vnstat.conf'});
        assert.equal(h.props['btnSubmit.disabled'], true);
        h.resolve(2, 'second');
        assert.equal(h.props['btnSubmit.disabled'], false);
        assert.equal(h.editor.getValue(), 'second');
    },
    'Stale failures do not invalidate a successfully loaded current file'() {
        const h = harness(); h.choose('/etc/vnstat/dvm-user-actions.sh');
        h.resolve(1, 'second'); h.reject(0);
        assert.equal(h.props['btnSubmit.disabled'], false);
        assert.equal(h.editor.getValue(), 'second');
    },
    'backend save errors retain actionable details as plain text'() {
        const h=harness();h.resolve(0,'original');h.save();
        const detail='Recovery copy: /boot/config/plugins/dvm/.dvm-stage-123 <example>';
        h.reject(1,detail);
        assert.ok(h.messages.at(-1).text.includes(detail));
        assert.equal(h.messages.at(-1).html,false);
    },
    'backend load errors are shown as plain status text'() {
        const h=harness();h.reject(0,'Select an allowed .conf file.');
        assert.ok(h.texts.editstatus.includes('Select an allowed .conf file.'));
    },
    'declining to discard edits keeps the original file and content'() {
        const h=harness();h.resolve(0,'original');h.editor.setValue('unsaved');h.context.confirmResult=false;
        h.choose('/etc/vnstat/dvm-user-actions.sh');
        assert.equal(h.fields.editfile,'/etc/vnstat/vnstat.conf');
        assert.equal(h.editor.getValue(),'unsaved');assert.equal(h.requests.length,1);
    },
    'Cancel and browser navigation warn about unsaved edits'() {
        const h=harness();h.resolve(0,'original');h.editor.setValue('unsaved');h.context.confirmResult=false;
        h.handlers['btnCancel.click']();assert.equal(h.context.location,'');
        assert.equal(h.wouldWarnOnLeave(),true);
    },
    'acknowledged saves clear only the snapshot that was actually saved'() {
        const h=harness();h.resolve(0,'original');h.editor.setValue('saved snapshot');h.save();
        h.editor.setValue('newer unsaved edits');h.resolve(1,{success:true,saved:'/etc/vnstat/vnstat.conf'});
        assert.equal(h.wouldWarnOnLeave(),true);
        h.save();h.resolve(2,{success:true,saved:'/etc/vnstat/vnstat.conf'});
        assert.equal(h.wouldWarnOnLeave(),false);
    }
};
let failed = 0;
for (const [name, test] of Object.entries(cases)) {
    try { test(); console.log(`PASS ${name}`); }
    catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`); }
}
if (failed) process.exitCode = 1;
