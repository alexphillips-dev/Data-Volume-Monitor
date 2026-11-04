<?php
namespace ReportThresholdTest;
$source = file_get_contents(__DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report.php');
$start = strpos($source, 'function dvm_checkAgainstLimits(');
$end = strpos($source, 'function dvm_get_primary_metrics()', $start);
eval('namespace ReportThresholdTest;'.substr($source, $start, $end - $start));
$start = strpos($source, 'function dvm_build_dashboard()');
$end = strpos($source, 'function dvm_build_footer()', $start);
eval('namespace ReportThresholdTest;'.substr($source, $start, $end - $start));
function dvm_get_primary_metrics() { return false; }
$start = strpos($source, 'function dvm_checkCustomLimits(');
$end = strpos($source, 'function dvm_build_dashboard()', $start);
eval('namespace ReportThresholdTest;'.substr($source, $start, $end - $start));
$state = 'error';
function shell_exec($command) { global $state; return $state === 'normal' ? '0' : '1'; }
function dvm_threshold_evaluate($iface, $time, $limit, $unit, $mode) {
    global $state;
    if ($limit === '-1') return 'disabled';
    if ($limit === '999') return 'error';
    return $state;
}
function check($condition, $message) { if (!$condition) throw new \RuntimeException($message); }
$result = dvm_checkAgainstLimits('eth0', 'h', '10', 'B', 'rx', '20 B');
check(strpos($result, 'dvm-threshold-error') !== false, 'Query failure was not marked unavailable');
check(strpos($result, 'red-text') === false && strpos($result, 'green-text') === false, 'Query failure was presented as a threshold decision');
$state = 'normal';
check(strpos(dvm_checkAgainstLimits('eth0', 'h', '10', 'B', 'rx', '5 B'), 'green-text') !== false, 'Normal result lost');
$state = 'exceeded';
check(strpos(dvm_checkAgainstLimits('eth0', 'h', '10', 'B', 'rx', '20 B'), 'red-text') !== false, 'Exceeded result lost');
check(dvm_checkAgainstLimits('eth0', 'h', '-1', 'B', 'rx', '20 B') === '20 B', 'Disabled result changed');
for ($i = 1; $i <= 2; $i++) {
    $GLOBALS['dvm_config_custom'.$i.'_interface'] = 'eth0';
    $GLOBALS['dvm_config_custom'.$i.'_time'] = 'h';
    $GLOBALS['dvm_config_custom'.$i.'_mode'] = 'rx';
    $GLOBALS['dvm_config_custom'.$i.'_unit'] = 'B';
    $GLOBALS['dvm_config_custom'.$i.'_limit'] = $i === 1 ? '999' : '10';
}
$state = 'normal';
check(strpos(dvm_checkCustomLimits('eth0', 'h', 'rx', '5 B'), 'dvm-threshold-error') !== false, 'Normal rule concealed unknown rule');
$state = 'exceeded';
check(strpos(dvm_checkCustomLimits('eth0', 'h', 'rx', '20 B'), 'red-text') !== false, 'Known exceeded rule concealed by unknown rule');
$dashboard = dvm_build_dashboard();
check(strpos($dashboard, 'dvm-threshold-error') !== false && strpos($dashboard, 'red-text') === false, 'Failed metrics query was presented as exceeded');
echo "PASS: unavailable/normal/exceeded/disabled reporting and duplicate-rule error precedence\n";
