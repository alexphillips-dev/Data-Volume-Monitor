<?php
require __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_threshold.php';

$checks = 0;
function check($actual, $expected, $label) {
    global $checks;
    $checks++;
    if ($actual !== $expected) {
        fwrite(STDERR, "$label: expected $expected, got $actual\n");
        exit(1);
    }
}
function payload($iface = 'eth0', $period = 'hour', $mode = 'rx', $exceeded = true) {
    return json_encode(['interfaces' => [['name' => $iface, 'alert' => ['type' => $period,
        'limit' => ['exceeded' => $exceeded, 'condition' => $mode, 'limit_bytes' => '1000', 'used_bytes' => '1001']]]]]);
}
$calls = 0;
$runner = function ($command) use (&$calls) {
    $calls++;
    check(strpos($command, '--json --alert 1 0 ') !== false, true, 'structured command');
    return [payload(), 0];
};
foreach (['-2', '0', '0.5', '1e3', '', 'hello', '1;touch', '18446744073709551616'] as $limit) {
    check(dvm_threshold_evaluate('eth0', 'h', $limit, 'KB', 'rx', $runner), 'error', "invalid $limit");
}
check(dvm_threshold_evaluate('eth0', 'h', '-1', 'KB', 'rx', $runner), 'disabled', 'disabled');
check($calls, 0, 'invalid/disabled never query');
check(dvm_threshold_evaluate('eth0', 'h', '1', 'KB', 'rx', $runner), 'exceeded', 'valid exceeded');
check($calls, 1, 'one backend query');
foreach (['B', 'KB', 'MB', 'GB', 'TB', 'KiB', 'MiB', 'GiB', 'TiB'] as $unit) {
    check(dvm_threshold_evaluate('eth0', 'h', '1', $unit, 'rx', $runner), 'exceeded', "unit $unit");
}
foreach (['h' => 'hour', 'd' => 'day', 'm' => 'month', 'y' => 'year'] as $time => $period) {
    foreach (['rx', 'tx'] as $mode) {
        check(dvm_threshold_decode(payload('eth0', $period, $mode, false), 'eth0', $time, $mode), 'normal', "$time $mode normal");
    }
}
foreach (['', 'Error: backend down', '{}', '{bad', '{"interfaces":[]}'] as $json) {
    check(dvm_threshold_decode($json, 'eth0', 'h', 'rx'), 'error', 'malformed JSON');
}
check(dvm_threshold_decode(payload('eth1'), 'eth0', 'h', 'rx'), 'error', 'wrong interface');
check(dvm_threshold_decode(payload('eth0', 'day'), 'eth0', 'h', 'rx'), 'error', 'wrong period');
check(dvm_threshold_decode(payload('eth0', 'hour', 'tx'), 'eth0', 'h', 'rx'), 'error', 'wrong mode');
check(dvm_threshold_decode(payload('eth0', 'hour', 'rx', 'true'), 'eth0', 'h', 'rx'), 'error', 'boolean required');
check(dvm_threshold_evaluate('eth0', 'h', '1', 'KB', 'rx', function () {return [payload(), 1];}), 'error', 'exit failure wins over JSON');
check(dvm_threshold_evaluate('eth0', 'h', '00010', 'KB', 'rx', function ($command) {
    check(strpos($command, "'10'") !== false || strpos($command, '"10"') !== false, true, 'canonical decimal limit');
    return [payload(), 0];
}), 'exceeded', 'leading zero');
echo "PASS: $checks threshold validation/result checks\n";
