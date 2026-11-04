<?php
require_once __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report_escape.php';
// Execute the actual report function with deterministic data providers, never host commands.
$source = file_get_contents(__DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report.php');
$start = strpos($source, 'function dvm_build_report_light()');
$end = strpos($source, 'function dvm_build_dashboard()', $start);
eval(substr($source, $start, $end - $start));
function dvm_getInterfaces() { return ['eth1']; }
function dvm_getXMLforInterface($iface) {
    return new SimpleXMLElement('<vnstat><interface><traffic><hours><hour><rx>10</rx><tx>100</tx></hour></hours></traffic></interface></vnstat>');
}
function dvm_isExistingInterface($iface) { return true; }
function dvm_humanFileSize($size) { return (string)$size; }
function dvm_checkAgainstLimits($iface, $time, $limit, $unit, $mode, $str) {
    if ($limit === '-1') return $str;
    return "<span class='".((int)$str > (int)$limit ? 'red-text' : 'green-text')."'>$str</span>";
}
function check($condition, $message) { if (!$condition) throw new RuntimeException($message); }
$dvm_config_vifaces = 'enable'; $dvm_config_oifaces = 'enable';
$dvm_config_match_virts = 'disable'; $dvm_config_primary = 'eth0';
for ($i = 1; $i <= 6; $i++) {
    ${'dvm_config_custom'.$i.'_interface'} = $i <= 2 ? 'eth1' : 'noiface';
    ${'dvm_config_custom'.$i.'_time'} = 'h';
    ${'dvm_config_custom'.$i.'_mode'} = $i === 2 ? 'tx' : 'rx';
    ${'dvm_config_custom'.$i.'_limit'} = '20';
    ${'dvm_config_custom'.$i.'_unit'} = 'B';
}
$html = dvm_build_report_light();
check(strpos($html, "green-text'>10") !== false, 'Normal RX rule not rendered');
check(strpos($html, "red-text'>100") !== false, 'Second TX rule was hidden');
check(strpos($html, 'Monitored - Limits Exceeded') !== false, 'Aggregate indicator did not show exceeded');
$dvm_config_custom2_mode = 'rx'; $dvm_config_custom2_limit = '1';
$html = dvm_build_report_light();
check(strpos($html, "red-text'>10") !== false, 'Stricter duplicate cell rule was hidden');
$dvm_config_custom1_limit = '-1';
check(strpos(dvm_build_report_light(), "red-text'>10") !== false, 'Disabled first rule hid later active rule');
$dvm_config_custom2_limit = '-1';
check(strpos(dvm_build_report_light(), 'Monitored - No Limits') !== false, 'All disabled rules were marked monitored');
$dvm_config_custom6_interface = 'eth1'; $dvm_config_custom6_time = 'm';
$dvm_config_custom6_mode = 'tx'; $dvm_config_custom6_limit = '1';
check(strpos(dvm_checkCustomLimits('eth1', 'm', 'tx', '10'), 'red-text') !== false, 'Sixth rule was not evaluated');
check(dvm_checkCustomLimits('eth2', 'm', 'tx', '10') === '10', 'Other interface rule leaked');
check(dvm_checkCustomLimits('eth1', 'y', 'tx', '10') === '10', 'Other period rule leaked');
echo "PASS: all matching custom rules, cell aggregation, and disabled rules\n";
