import assert from 'node:assert/strict';
import fs from 'node:fs';

const source = fs.readFileSync(new URL('../source/usr/local/emhttp/plugins/dvm/DVMfooter.page', import.meta.url), 'utf8');
const blocks = [...source.matchAll(/if\(data\.success\.response\.includes\("red-text"\)\)[\s\S]*?(?=\n        })/g)].map(match => match[0]);
assert.equal(blocks.length, 2, 'Exercise both host dashboard branches');
let failures = 0;
for (const [index, block] of blocks.entries()) {
    for (const [name, response, expected] of [
        ['unknown plus valid green', 'dvm-threshold-error green-text', 'Threshold status unavailable'],
        ['unknown alone', 'dvm-threshold-error', 'Threshold status unavailable'],
        ['confirmed exceeded plus unknown', 'red-text dvm-threshold-error', 'Monitored - Limits Exceeded'],
        ['confirmed normal', 'green-text', 'Monitored - Limits Not Exceeded'],
        ['no thresholds', 'plain volume data', 'Monitored - No Limits']
    ]) {
        try {
            const attributes = {};
            const $ = () => ({attr(key, value) { attributes[key] = value; }});
            new Function('$', 'data', block)($, {success: {response}});
            assert.equal(attributes.title, expected);
            if (expected === 'Threshold status unavailable') assert.match(attributes.class, /fa-exclamation-triangle/);
            console.log(`PASS dashboard ${index}: ${name}`);
        } catch (error) {
            failures++; console.error(`FAIL dashboard ${index}: ${name}: ${error.message}`);
        }
    }
}
if (failures) process.exitCode = 1;
