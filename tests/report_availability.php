<?php
namespace ReportAvailabilityTest;
require_once __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report_escape.php';
$source = file_get_contents(__DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report.php');
$source = preg_replace('/^<\?\s*/', '', $source);
$source = preg_replace('/require_once [^;]+;/', '', $source);
$source = preg_replace('/\?>\s*$/', '', $source);
$boundary = strpos($source, 'if(!empty($_GET["mode"]))');
$definitions = substr($source, 0, $boundary);
$dispatch = substr($source, $boundary);
eval('namespace ReportAvailabilityTest; use \\SimpleXMLElement;'.$definitions);
$failure = '';
function query_result($command) {
    global $failure;
    if (strpos($command, '--dbiflist') !== false) {
        return $failure === 'interfaces' ? ['', 1] : ['Interfaces in database: eth0 eth1', 0];
    }
    if (strpos($command, '--xml') !== false) {
        if ($failure === 'xml' || ($failure === 'partial' && strpos($command, 'eth1') !== false)) return ['', 1];
        if ($failure === 'malformed') return ['not XML', 0];
        if ($failure === 'missing-traffic') return ['<vnstat xmlversion="2"><interface /></vnstat>', 0];
        return ['<vnstat xmlversion="2"><interface><traffic><hours><hour><rx>10</rx><tx>20</tx></hour></hours></traffic></interface></vnstat>', $failure === 'xml-exit-error' ? 1 : 0];
    }
    if (strpos($command, 'find /sys') !== false) return ["/sys/class/net/eth0\n/sys/class/net/eth1", 0];
    if ($failure === 'textquery' || ($failure === 'imagequery' && strpos($command, 'vnstati ') === 0)) return ['query failed', 1];
    if ($failure === 'empty-text') return ['', 0];
    return ['fixture traffic output', 0];
}
function shell_exec($command) { return query_result($command)[0]; }
function exec($command, &$output, &$status) {
    list($text, $status) = query_result($command);
    $output = explode("\n", $text);
    return end($output);
}
function dvm_threshold_evaluate() { return 'error'; }
function error_log($message) { return true; } // Expected fixture failures must not write a host log.
function check($condition, $message) { if (!$condition) throw new \RuntimeException($message); }
function response($mode) {
    global $dispatch;
    $_GET = ['mode' => $mode];
    ob_start();
    // eval inside a function needs the dispatch availability variable explicitly global.
    global $dvm_report_data_available;
    eval('namespace ReportAvailabilityTest;'.$dispatch);
    $result = json_decode(ob_get_clean(), true);
    check(is_array($result) && isset($result['success']), 'Endpoint did not return its compatible success object');
    return $result['success'];
}
$dvm_config_primary = 'eth0'; $dvm_config_vifaces = 'enable'; $dvm_config_oifaces = 'enable';
$dvm_config_match_virts = 'disable'; $dvm_config_report = 'text'; $dvm_config_footerformat = 'h';
foreach (['h', 'd', 'm', 'y'] as $period) foreach (['rx', 'tx'] as $direction) {
    $GLOBALS['dvm_config_'.$period.'limit_'.$direction] = '1';
    $GLOBALS['dvm_config_'.$period.'unit_'.$direction] = 'B';
}
for ($i=1; $i<=6; $i++) $GLOBALS['dvm_config_custom'.$i.'_interface'] = 'noiface';
$failure = 'xml';
check((response('dashboard')['dataAvailable'] ?? null) === false, 'Whole measurement failure was not typed unavailable');
foreach (['dashboard', 'dashboardmini', 'footer', 'report', 'lightreport'] as $mode) {
    $failure = '';
    $value = response($mode);
    check(($value['dataAvailable'] ?? null) === true, 'Valid measurements were rejected for '.$mode);
    if ($mode !== 'report') check(strpos($value['response'], 'dvm-threshold-error') !== false, 'Unknown threshold fixture was not exercised');
    if ($mode === 'dashboard') check(count(explode(';', $value['response'])) === 10, 'Dashboard protocol changed');
}
foreach (['report', 'lightreport'] as $mode) {
    $failure = 'interfaces';
    check(response($mode)['dataAvailable'] === false, 'Failed interface query was not observed for '.$mode);
}
$failure = 'partial';
check(response('lightreport')['dataAvailable'] === false, 'Partially failed interface measurements advanced availability');
$failure = 'malformed';
check(response('footer')['dataAvailable'] === false, 'Malformed measurement response was accepted');
$failure = 'missing-traffic';
check(response('footer')['dataAvailable'] === false, 'Missing traffic structure was accepted');
$failure = 'xml-exit-error';
check(response('footer')['dataAvailable'] === false, 'Valid-looking XML from a failed process was accepted');
$failure = 'textquery';
check(response('report')['dataAvailable'] === false, 'Failed detailed text query was not observed');
$failure = 'empty-text';
check(response('report')['dataAvailable'] === false, 'Empty detailed text query was accepted');
$failure = 'imagequery'; $dvm_config_report = 'images';
check(response('report')['dataAvailable'] === false, 'Failed image query was not observed');
$failure = '';
check(response('footer')['dataAvailable'] === true, 'Failure state leaked into the next request');
echo "PASS: endpoint availability types, all modes, partial failure, recovery, and unknown-threshold distinction\n";
