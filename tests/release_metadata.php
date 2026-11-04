<?php
// Exercise installed release metadata and the actual settings display in isolation.
$root = __DIR__ . '/../source/usr/local/emhttp/plugins/dvm';
$helper = $root . '/include/dvm_release.php';
if (is_file($helper)) require_once $helper;
function release_check($condition, $message) {
    if (!$condition) throw new RuntimeException($message);
}
$directory = sys_get_temp_dir() . '/dvm-release-fixture-' . bin2hex(random_bytes(8));
mkdir($directory, 0700);
$path = $directory . '/release.json';
$checks = 0;
function check_summary($path, $contents, $expected) {
    global $checks;
    file_put_contents($path, $contents);
    release_check(dvm_release_summary($path) === $expected, 'Unexpected release summary for ' . $contents);
    $checks++;
}
try {
    release_check(function_exists('dvm_release_read') && function_exists('dvm_release_summary'), 'Installed release metadata helper is missing');
    foreach (['dev' => 'Development', 'main' => 'Stable'] as $channel => $label) {
        $metadata = ['schema' => 1, 'channel' => $channel, 'version' => '2026.11.04.09',
            'plugin_url' => 'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/' . $channel . '/plugin/dvm.plg'];
        check_summary($path, json_encode($metadata), '2026.11.04.09 (' . $label . ')');
        release_check(dvm_release_read($path) === $metadata, 'Valid metadata changed during reading');
    }
    $metadata = ['schema' => 1, 'channel' => 'dev', 'version' => '2026.11.04.09',
        'plugin_url' => 'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/dev/plugin/dvm.plg'];
    $invalid = ['not json', 'null', '[]', str_repeat('x', 4097)];
    foreach (['schema' => 2, 'channel' => 'release', 'version' => '<script>bad()</script>',
              'plugin_url' => 'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/main/plugin/dvm.plg'] as $key => $value) {
        $changed = $metadata; $changed[$key] = $value; $invalid[] = json_encode($changed);
    }
    foreach (['schema', 'channel', 'version', 'plugin_url'] as $key) {
        $changed = $metadata; unset($changed[$key]); $invalid[] = json_encode($changed);
    }
    foreach ($invalid as $contents) {
        check_summary($path, $contents, 'Unknown (channel unavailable)');
        release_check(dvm_release_read($path) === null, 'Invalid metadata was accepted');
    }
    unlink($path);
    release_check(dvm_release_summary($path) === 'Unknown (channel unavailable)', 'Missing metadata must remain readable');
    $checks++;
    if (DIRECTORY_SEPARATOR === '/') {
        file_put_contents($directory . '/outside.json', json_encode($metadata));
        symlink($directory . '/outside.json', $path);
        release_check(dvm_release_summary($path) === 'Unknown (channel unavailable)', 'Linked release metadata was accepted');
        unlink($path); unlink($directory . '/outside.json'); $checks++;
    }
    $page = file_get_contents($root . '/DVMcontrol.page');
    release_check(strpos($page, "require_once '/usr/local/emhttp/plugins/dvm/include/dvm_release.php';") !== false, 'Settings page does not load installed release helper');
    release_check(preg_match('~<dl>\s*<dt>DVM Version / Channel:</dt>[\s\S]*?</dl>~', $page, $match) === 1, 'Settings version/channel row is missing');
    $row = str_replace('dvm_release_summary()', 'dvm_release_summary($path)', $match[0]);
    file_put_contents($path, json_encode($metadata));
    ob_start(); eval('?>' . $row); $html = ob_get_clean();
    release_check(strpos($html, '2026.11.04.09 (Development)') !== false, 'Actual settings row does not display release/channel');
    file_put_contents($path, json_encode(array_replace($metadata, ['version' => '<img src=x onerror=bad()>'])));
    ob_start(); eval('?>' . $row); $html = ob_get_clean();
    release_check(strpos($html, 'Unknown (channel unavailable)') !== false && strpos($html, '<img') === false, 'Actual settings row accepts unsafe release metadata');
    $checks += 2;
    $readme = file_get_contents($root . '/README.md');
    release_check(strpos($readme, '/tree/main') !== false && strpos($readme, '/tree/dev') !== false, 'Installed documentation must link both channels');
    $checks++;
    echo 'PASS: ' . $checks . " release metadata and settings display checks\n";
} finally {
    if (is_file($path) || is_link($path)) unlink($path);
    rmdir($directory);
}
