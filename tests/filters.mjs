import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';

const root = new URL('../source/usr/local/emhttp/plugins/dvm/', import.meta.url);
const page = fs.readFileSync(new URL('DVMsettings.page', root), 'utf8');
const helper = page.match(/function dvmMatchesFilter\([\s\S]*?\n}/)?.[0] ?? '';
const blocks = [...page.matchAll(/let rowMatches[\s\S]*?(?=if \(!rowMatches\))/g)].map(match => match[0]);
assert.equal(blocks.length, 2, 'Exercise both full and light report filtering');
let failed = 0;
function test(name, run) {
    try { run(); console.log(`PASS ${name}`); }
    catch (error) { failed++; console.error(`FAIL ${name}: ${error.message}`); }
}
for (const [index, block] of blocks.entries()) {
    const matches = new Function('filterArray', 'spanTexts', 'tdText', helper + '\n' + block + '\nreturn rowMatches;');
    test(`report ${index}: combined inclusion with no exclusion`, () => assert.equal(matches(['A+B'], ['A','B'], 'br0'), true));
    test(`report ${index}: missing included service is rejected`, () => assert.equal(matches(['A+B'], ['A'], 'br0'), false));
    test(`report ${index}: exclusion is honored`, () => {
        assert.equal(matches(['A!B'], ['A','B'], 'br0'), false);
        assert.equal(matches(['A!B'], ['A'], 'br0'), true);
        assert.equal(matches(['!B'], ['A'], 'br0'), true);
        assert.equal(matches(['!B'], ['B'], 'br0'), false);
    });
    test(`report ${index}: existing literal interface/service and OR filters`, () => {
        assert.equal(matches(['br0'], [], 'br0'), true);
        assert.equal(matches(['other', 'A'], ['A'], 'br0'), true);
        assert.equal(matches(['a'], ['A'], 'br0'), false);
    });
}

const config = fs.readFileSync(new URL('include/dvm_config.php', root), 'utf8');
const assignment = config.split('\n').find(line => line.startsWith('$dvm_config_filters '));
const javascript = page.split('\n').find(line => line.includes('let filters ='));
for (const value of ['trailing\\', 'A&B', 'quoted"name', '</script><script>bad</script>', 'name\nnext']) {
    test(`PHP to JavaScript preserves ${JSON.stringify(value)}`, () => {
        const encoded = Buffer.from(JSON.stringify({FILTERS: value})).toString('base64');
        const php = `<?php $dvm_config_cfg = json_decode(base64_decode('${encoded}'), true); ${assignment} ?>${javascript}`;
        const rendered = spawnSync('php', {input: php, encoding:'utf8'});
        assert.equal(rendered.status, 0, rendered.stderr);
        assert.equal(new Function(rendered.stdout + '\nreturn filters;')(), value);
        assert.equal(rendered.stdout.toLowerCase().includes('</script>'), false);
    });
}
if (failed) process.exitCode = 1;
