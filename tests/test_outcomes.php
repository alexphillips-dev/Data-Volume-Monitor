<?php
// Storage failure injection uses only a disposable local runtime directory.
$root = sys_get_temp_dir() . '/dvm-outcomes-test-' . bin2hex(random_bytes(8));
mkdir($root, 0700);
$source = file_get_contents(__DIR__ . '/../source/usr/local/emhttp/plugins/dvm/include/dvm_outcome_store.php');
file_put_contents($root . '/store.php', str_replace(['/var/run/dvm/outcomes', '/var/lock/dvm-notify.lock'], [$root . '/outcomes', $root . '/notify.lock'], $source));
require $root . '/store.php';
$checks = 0;
function outcome_check($value, $message) {
    global $checks;
    $checks++;
    if (!$value) { throw new RuntimeException($message); }
}
try {
    $digest = str_repeat('a', 64);
    dvm_outcome_record('begin', 'primary-h-rx', $digest, 'exceeded', 'eth0', ['pending', 'disabled', 'pending', 'pending']);
    dvm_outcome_record('finish', 'primary-h-rx', $digest, 'exceeded', 'eth0', [1, 'disabled', 0, 0]);
    $path = $root . '/outcomes/primary-h-rx.json';
    $before = file_get_contents($path);
    $record = dvm_outcome_read('primary-h-rx');
    outcome_check($record['status'] === 'failed', 'Failed outcome readable');
    $record['attempts']++;
    $failed = false;
    try {
        dvm_outcome_write($record, function ($stream, $payload) { return fwrite($stream, substr($payload, 0, 10)); });
    } catch (RuntimeException $error) { $failed = true; }
    outcome_check($failed, 'Partial positive write must fail');
    outcome_check(file_get_contents($path) === $before, 'Partial write must preserve previous record');
    outcome_check(count(glob($root . '/outcomes/.attempt-*')) === 0, 'Failed stage must be removed');
    outcome_check(dvm_outcome_retry('primary-h-rx', $digest, 'exceeded') === [1, 'disabled', 0, 0], 'Retry only exposes recorded failed components');
    foreach (['../x', 'secondary-7', 'primary-h-rx;echo'] as $token) {
        outcome_check(dvm_outcome_read($token) === null, 'Invalid tokens rejected');
    }
    outcome_check(function_exists('dvm_outcome_clear'), 'Runtime outcome cleanup must be available');
    $heldLock = fopen($root . '/notify.lock', 'c');
    flock($heldLock, LOCK_EX);
    $refused = false;
    try { dvm_outcome_clear(); } catch (RuntimeException $error) { $refused = true; }
    outcome_check($refused && file_get_contents($path) === $before, 'Active automation prevents cleanup');
    fclose($heldLock);
    file_put_contents($root . '/outcomes/unrelated.json', 'preserve');
    dvm_outcome_clear();
    outcome_check(!file_exists($path), 'Cleanup removes owned rule records');
    outcome_check(file_get_contents($root . '/outcomes/unrelated.json') === 'preserve', 'Cleanup preserves unrelated files');
    unlink($root . '/outcomes/unrelated.json');
    dvm_outcome_clear();
    outcome_check(!is_dir($root . '/outcomes'), 'Empty owned directory can be removed');
    if (DIRECTORY_SEPARATOR === '/') {
        mkdir($root . '/other');
        file_put_contents($root . '/other/primary-h-rx.json', 'preserve');
        symlink($root . '/other', $root . '/outcomes');
        $refused = false;
        try { dvm_outcome_clear(); } catch (RuntimeException $error) { $refused = true; }
        outcome_check($refused && file_get_contents($root . '/other/primary-h-rx.json') === 'preserve', 'Linked directory cannot redirect cleanup');
        unlink($root . '/outcomes');
        unlink($root . '/other/primary-h-rx.json');
        rmdir($root . '/other');
    }
    echo "PASS: $checks outcome storage checks\n";
} finally {
    if (is_link($root . '/outcomes')) { unlink($root . '/outcomes'); }
    foreach (glob($root . '/outcomes/*') ?: [] as $file) { unlink($file); }
    foreach (glob($root . '/outcomes/.attempt-*') ?: [] as $file) { unlink($file); }
    if (is_dir($root . '/outcomes')) { rmdir($root . '/outcomes'); }
    unlink($root . '/store.php');
    if (is_file($root . '/notify.lock')) { unlink($root . '/notify.lock'); }
    rmdir($root);
}
