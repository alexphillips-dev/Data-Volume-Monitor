<?php
require __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_editor.php';
function check($condition, $message) {
    if (!$condition) throw new RuntimeException($message);
}
function failure($operation) {
    try { $operation(); return false; }
    catch (RuntimeException $error) { return true; }
}
$root = sys_get_temp_dir().'/dvm-save-'.bin2hex(random_bytes(8));
mkdir($root); mkdir($root.'/runtime'); mkdir($root.'/flash');
$file = $root.'/runtime/actions.sh'; $backup = $root.'/flash/actions.sh';
file_put_contents($file, 'original-runtime'); file_put_contents($backup, 'original-flash');
file_put_contents($root.'/blocked-directory', 'blocker');
try {
    check(failure(function () use ($file, $root) {
        dvm_editor_save($file, 'new-data', $root.'/runtime', $root.'/blocked-directory');
    }), 'Failed persistent write reported success');
    check(file_get_contents($file) === 'original-runtime', 'Runtime changed after persistence failure');
    dvm_editor_save($file, '', $root.'/runtime', $root.'/flash');
    check(file_get_contents($file) === '' && file_get_contents($backup) === '', 'Empty save did not commit both copies');
    file_put_contents($file, 'runtime-before'); file_put_contents($backup, 'flash-before');
    $replace = function ($from, $to) use ($file) {
        if ($to === realpath($file)) return false;
        return rename($from, $to);
    };
    check(failure(function () use ($file, $root, $replace) {
        dvm_editor_save($file, 'rejected-update', $root.'/runtime', $root.'/flash', $replace);
    }), 'Failed runtime replacement reported success');
    check(file_get_contents($file) === 'runtime-before', 'Runtime original lost');
    check(file_get_contents($backup) === 'flash-before', 'Persistent original was not rolled back');
    check(failure(function () use ($file, $root) {
        dvm_editor_save($file, 'rejected-flash-update', $root.'/runtime', $root.'/flash', function () { return false; });
    }), 'Failed flash replacement reported success');
    check(file_get_contents($file) === 'runtime-before' && file_get_contents($backup) === 'flash-before', 'Flash replacement failure changed files');
    unlink($backup);
    check(failure(function () use ($file, $root, $replace) {
        dvm_editor_save($file, 'rejected-new-backup', $root.'/runtime', $root.'/flash', $replace);
    }), 'Failed runtime save with new backup reported success');
    check(!file_exists($backup), 'New persistent copy remained after failed runtime save');
    dvm_editor_save($file, "line1\r\nline2\n", $root.'/runtime', $root.'/flash');
    check(file_get_contents($file) === "line1\nline2\n", 'Line endings not normalized');
    check(file_get_contents($file) === file_get_contents($backup), 'Saved copies differ');
    check(glob($root.'/runtime/.dvm-stage-*') === [] && glob($root.'/flash/.dvm-stage-*') === [], 'Staged files leaked');
    echo "PASS: persistence failure, empty save, rollback, line endings, and successful paired save\n";
} finally {
    foreach ([$root.'/runtime', $root.'/flash'] as $dir) {
        foreach (new FilesystemIterator($dir) as $entry) unlink($entry->getPathname());
        rmdir($dir);
    }
    unlink($root.'/blocked-directory'); rmdir($root);
}
