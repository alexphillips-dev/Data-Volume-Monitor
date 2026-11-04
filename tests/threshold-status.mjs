import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const page = fs.readFileSync(new URL('../source/usr/local/emhttp/plugins/dvm/DVMcontrol.page', import.meta.url), 'utf8');
const code = page.match(/function checkLIMITS\(\)\{[\s\S]*?(?=function Restart\()/)[0];
const inputs = [];
for (const period of ['H', 'D', 'M', 'Y']) {
    for (const direction of ['RX', 'TX']) inputs.push({id: `${direction}LIMIT${period}`});
}
for (let index = 1; index <= 6; index++) inputs.push({id: `CUSTOM${index}LIMIT`});
for (const input of inputs) {
    input.value = '-1';
    input.attributes = {'aria-describedby': 'existing-help'};
    input.statuses = [];
}
function span() {
    return {
        length: 1, attributes: {}, classes: new Set(), value: '', visible: false,
        attr(values) { Object.assign(this.attributes, values); return this; },
        addClass(value) { this.classes.add(value); return this; },
        toggleClass(value, active) { if (active) this.classes.add(value); else this.classes.delete(value); return this; },
        text(value) { if (value === undefined) return this.value; this.value = value; return this; },
        show() { this.visible = true; return this; }
    };
}
function $(node) {
    if (node === '.dvmlimit, .dvmlimit2') return {each(callback) { for (const input of inputs) callback.call(input); }};
    if (node === '<span>') return span();
    return {
        val() { return node.value; },
        siblings() { return node.statuses[0] || {length: 0}; },
        parent() { return {append(status) { node.statuses.push(status); }}; },
        attr(key, value) { if (value === undefined) return node.attributes[key]; node.attributes[key] = value; return this; }
    };
}
const context = vm.createContext({$});
vm.runInContext(code, context);
for (const [value, label, color] of [
    ['-1', 'Disabled', 'red-text'],
    ['1', 'Enabled', 'green-text'],
    [' 00042 ', 'Enabled', 'green-text'],
    ['18446744073709551615', 'Enabled', 'green-text'],
    ['18446744073709551616', 'Invalid', 'red-text'],
    ['0', 'Invalid', 'red-text'],
    ['-2', 'Invalid', 'red-text'],
    ['1.5', 'Invalid', 'red-text'],
    ['', 'Invalid', 'red-text'],
    ['-1', 'Disabled', 'red-text']
]) {
    for (const input of inputs) input.value = value;
    context.checkLIMITS();
    for (const input of inputs) {
        assert.equal(input.statuses.length, 1, `${input.id}: duplicate status`);
        const status = input.statuses[0];
        assert.equal(status.value, label, input.id);
        assert.ok(status.classes.has(color), `${input.id}: wrong color`);
        assert.ok(!status.classes.has(color === 'red-text' ? 'green-text' : 'red-text'), `${input.id}: stale color`);
        assert.equal(status.attributes.id, `${input.id}-status`);
        assert.equal(status.attributes.role, 'status');
        assert.equal(status.attributes['aria-live'], 'polite');
        assert.equal(input.attributes['aria-describedby'], `existing-help ${input.id}-status`);
        assert.ok(status.visible);
        assert.equal(input.value, value, `${input.id}: edited value changed`);
    }
}
console.log('PASS all eight primary and six secondary limits retain live status colors, boundaries, and accessible descriptions');
