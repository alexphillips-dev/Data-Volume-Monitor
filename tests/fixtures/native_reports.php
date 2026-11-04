<?php
// Actual report/evaluator code with every backend command redirected to the
// isolated package executables and temporary config/image paths supplied by Python.
namespace NativeReports;
use SimpleXMLElement;
require __DIR__ . '/../../source/usr/local/emhttp/plugins/dvm/include/dvm_report_escape.php';
$root = dirname(__DIR__, 2) . '/source/usr/local/emhttp/plugins/dvm/include/';
$threshold = file_get_contents($root . 'dvm_threshold.php');
$threshold = preg_replace('/^<\?php\s*/', '', $threshold);
$threshold = substr($threshold, 0, strpos($threshold, "if (PHP_SAPI === 'cli'"));
eval('namespace NativeReports;' . $threshold);
$report = file_get_contents($root . 'dvm_report.php');
$report = preg_replace('/^<\?\s*/', '', $report);
$report = preg_replace('/require_once [^;]+;/', '', $report);
$report = preg_replace('/\?>\s*$/', '', $report);
eval('namespace NativeReports; use \\SimpleXMLElement;' . substr($report, 0, strpos($report, 'if(!empty($_GET["mode"]))')));
function exec($command, &$output, &$status) {
    global $argv;
    if (!preg_match('/^(vnstat|vnstati) --config \/etc\/vnstat\/vnstat\.conf /', $command, $match)) {
        throw new \RuntimeException('Unexpected fixture command: ' . $command);
    }
    $command = preg_replace('/^(vnstat|vnstati) --config \/etc\/vnstat\/vnstat\.conf /',
        escapeshellarg($argv[1] . '/' . $match[1]) . ' --config ' . escapeshellarg($argv[2]) . ' ', $command);
    $command = str_replace('/usr/local/emhttp/plugins/dvm/images/', $argv[3] . '/', $command);
    return \exec($command, $output, $status);
}
function shell_exec($command) {
    if ($command === 'find /sys/class/net/ -type l 2>/dev/null') return '/sys/class/net/lo';
    throw new \RuntimeException('Unexpected fixture shell query: ' . $command);
}
$dvm_config_primary = 'lo'; $dvm_config_vifaces = 'enable'; $dvm_config_oifaces = 'enable';
$dvm_config_match_virts = 'disable'; $dvm_config_footerformat = 'h';
foreach (['h', 'd', 'm', 'y'] as $period) foreach (['rx', 'tx'] as $direction) {
    $GLOBALS['dvm_config_'.$period.'limit_'.$direction] = '1';
    $GLOBALS['dvm_config_'.$period.'unit_'.$direction] = 'B';
}
for ($slot = 1; $slot <= 6; $slot++) $GLOBALS['dvm_config_custom'.$slot.'_interface'] = 'noiface';
$results = [];
foreach (['text', 'images', 'both'] as $format) {
    $dvm_config_report = $format;
    foreach (['report' => 'dvm_build_report', 'lightreport' => 'dvm_build_report_light',
              'dashboard' => 'dvm_build_dashboard', 'dashboardmini' => 'dvm_build_dashboard_mini',
              'footer' => 'dvm_build_footer'] as $mode => $function) {
        $dvm_report_data_available = true;
        $callable = __NAMESPACE__ . '\\' . $function;
        $results[$format][$mode] = ['available' => null, 'response' => $callable()];
        $results[$format][$mode]['available'] = $dvm_report_data_available;
    }
}
echo json_encode($results, JSON_THROW_ON_ERROR);
