<?php
require __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_editor.php';

function check($condition, $message) {
    if (!$condition) throw new RuntimeException($message);
}
function rejected($path, $base) {
    try { dvm_editor_resolve($path, $base); return false; }
    catch (InvalidArgumentException $error) { return true; }
}
$root = sys_get_temp_dir().'/dvm-editor-'.bin2hex(random_bytes(8));
mkdir($root); mkdir($root.'/allowed'); mkdir($root.'/allowed-other');
mkdir($root.'/allowed/nested');
foreach (['allowed/vnstat.conf', 'allowed/actions.sh', 'outside.conf',
          'allowed-other/other.conf', 'allowed/nested/child.conf', 'allowed/unsafe.php'] as $file) {
    file_put_contents($root.'/'.$file, 'fixture');
}
try {
    $base = $root.'/allowed';
    check(dvm_editor_read($base.'/vnstat.conf', $base) === 'fixture', 'Valid config read failed');
    check(dvm_editor_resolve($base.'/actions.sh', $base) === realpath($base.'/actions.sh'), 'Valid script rejected');
    check(rejected($root.'/outside.conf', $base), 'Outside file was accepted');
    check(rejected($base.'/../outside.conf', $base), 'Traversal was accepted');
    check(rejected($root.'/allowed-other/other.conf', $base), 'Prefix sibling was accepted');
    check(rejected($base.'/nested/child.conf', $base), 'Nested file was accepted');
    check(rejected($base.'/unsafe.php', $base), 'Unsupported extension was accepted');
    check(rejected($base.'/missing.conf', $base), 'Missing file was accepted');
    check(rejected([], $base) && rejected(null, $base), 'Invalid request types accepted');
    if (@symlink($root.'/outside.conf', $base.'/linked.conf')) {
        check(rejected($base.'/linked.conf', $base), 'Escaping symlink was accepted');
    } else {
        echo "SKIP: symlink fixture unavailable on this host\n";
    }
    echo "PASS: editor path boundary, file types, traversal, and valid reads\n";
} finally {
    foreach (glob($root.'/allowed/*') as $file) if (!is_dir($file)) unlink($file);
    unlink($root.'/allowed/nested/child.conf'); rmdir($root.'/allowed/nested');
    unlink($root.'/allowed-other/other.conf'); rmdir($root.'/allowed-other');
    unlink($root.'/outside.conf'); rmdir($root.'/allowed'); rmdir($root);
}
