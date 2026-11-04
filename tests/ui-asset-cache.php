<?php
// Evaluate the actual asset tags with isolated equal-mtime files, as installed
// by the deterministic package builder. Native autov uses filemtime.
$fixture = tempnam(sys_get_temp_dir(), 'dvm-ui-cache-');
function autov($path) { global $fixture; return $path . '?v=' . filemtime($fixture); }
$failures = 0;
try {
    foreach (['DVMfooter.page' => ['dvm-poll.js'], 'DVMsettings.page' => ['dvm-poll.js'],
              'DVMcontrol.page' => ['dvm-poll.js', 'dvm-outcomes.js']] as $page => $assets) {
        $source = file_get_contents(__DIR__ . '/../source/usr/local/emhttp/plugins/dvm/' . $page);
        foreach ($assets as $asset) {
            $lines = array_values(array_filter(explode("\n", $source), function ($line) use ($asset) {
                return strpos($line, '<script src=') !== false && strpos($line, $asset) !== false;
            }));
            if (count($lines) !== 1) { throw new RuntimeException('Expected one asset tag'); }
            $tag = str_replace('/usr/local/emhttp/plugins/dvm/js/' . $asset, str_replace('\\', '/', $fixture), $lines[0]);
            $rendered = [];
            foreach (['first bytes', 'changed bytes'] as $bytes) {
                file_put_contents($fixture, $bytes);
                touch($fixture, 0);
                clearstatcache(true, $fixture);
                ob_start(); eval('?>' . $tag); $rendered[] = ob_get_clean();
            }
            if ($rendered[0] === $rendered[1]) {
                $failures++;
                echo "FAIL $page $asset: changed bytes retain the same cache URL\n";
            } else { echo "PASS $page $asset: content changes invalidate equal-mtime cache\n"; }
        }
    }
} finally { unlink($fixture); }
exit($failures ? 1 : 0);
