<?php
namespace ReportEscapingTest;
require_once __DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report_escape.php';
use \SimpleXMLElement;
use \DOMDocument;
use \DOMXPath;
$source = file_get_contents(__DIR__.'/../source/usr/local/emhttp/plugins/dvm/include/dvm_report.php');
$source = preg_replace('/^<\?\s*/', '', $source);
$source = preg_replace('/require_once [^;]+;/', '', $source);
$source = preg_replace('/\?>\s*$/', '', $source);
eval('namespace ReportEscapingTest; use \\SimpleXMLElement;'.$source);
$iface = "eth<&'";
$services = ['Work & <lab> "VM":A', 'literal&amp;entity'];
$commands = [];
$imageNames = [];
$xmlAvailable = true;
function shell_exec($command) {
    global $iface, $services, $commands, $xmlAvailable;
    $commands[] = $command;
    if (strpos($command, 'scripts/match_virts') !== false) return $iface.':'.$services[0]."\n".$iface.':'.$services[1]."\n";
    if (strpos($command, '--dbiflist') !== false) return 'Interfaces in database: '.$iface;
    if (strpos($command, 'find /sys/class/net/') !== false) return '/sys/class/net/'.$iface;
    if (strpos($command, '--xml') !== false) return $xmlAvailable ? '<vnstat xmlversion="2"><interface><traffic><hours><hour><rx>10</rx><tx>20</tx></hour></hours></traffic></interface></vnstat>' : '';
    return 'backend & <output>';
}
function dvm_threshold_evaluate() { return 'disabled'; }
function exec($command, &$output, &$status) {
    $output = explode("\n", shell_exec($command));
    $status = 0;
    return end($output);
}
function check($condition, $message) { if (!$condition) throw new \RuntimeException($message); }
function dom($html) {
    $document = new DOMDocument();
    @$document->loadHTML('<meta charset="UTF-8"><table>'.$html.'</table>');
    return $document;
}
$dvm_config_primary = 'eth0'; $dvm_config_vifaces = 'enable'; $dvm_config_oifaces = 'enable';
$dvm_config_match_virts = 'enable';
for ($i=1; $i<=6; $i++) $GLOBALS['dvm_config_custom'.$i.'_interface'] = 'noiface';
foreach (['h', 'd', 'm', 'y'] as $period) {
    foreach (['rx', 'tx'] as $direction) {
        $GLOBALS['dvm_config_'.$period.'limit_'.$direction] = '-1';
        $GLOBALS['dvm_config_'.$period.'unit_'.$direction] = 'B';
    }
}
$matches = dvm_getVirtualInterfaceServiceMatches();
check(strpos($matches[$iface], '&lt;lab&gt;') !== false, 'Service label was inserted as markup');
check(strpos($matches[$iface], ':A') !== false, 'Service label was truncated at a colon');
foreach (['text', 'images', 'both'] as $mode) {
    $dvm_config_report = $mode;
    $html = dvm_build_report();
    $document = dom($html);
    check($document->getElementsByTagName('lab')->length === 0, 'Service markup became an element');
    $first = $document->getElementsByTagName('td')->item(0);
    check(strpos($first->textContent, $iface) === 0, 'Interface text changed after rendering');
    $spans = (new DOMXPath($document))->query('//td[1]/span/span');
    check($spans->length === 2 && $spans->item(0)->textContent === $services[0] && $spans->item(1)->textContent === $services[1], 'Service span/filter text contract changed');
    foreach ($document->getElementsByTagName('img') as $image) {
        $url = $image->getAttribute('src');
        check(preg_match('~^/plugins/dvm/images/[a-zA-Z0-9_-]+\.png$~D', $url) === 1, 'Unsafe image URL');
        $imageNames[] = basename($url);
    }
}
foreach ([true, false] as $available) {
    $xmlAvailable = $available;
    $document = dom(dvm_build_report_light());
    check(strpos($document->getElementsByTagName('td')->item(0)->textContent, $iface) === 0, 'Light/error report interface text changed');
    check($document->getElementsByTagName('lab')->length === 0, 'Light report service markup became an element');
}
$xmlAvailable = true;
$dvm_config_custom1_interface = $iface;
$dvm_config_custom1_time = 'h'; $dvm_config_custom1_mode = 'rx';
$dvm_config_custom1_limit = '-1'; $dvm_config_custom1_unit = 'B';
check(strpos(dom(dvm_build_report_light())->getElementsByTagName('td')->item(0)->textContent, $iface) === 0, 'Custom threshold interface text changed');
$iface = 'eth0'; $dvm_config_primary = 'eth0';
$document = dom(dvm_build_report_light());
check((new DOMXPath($document))->query('//td[1]/span/span')->item(0)->textContent === $services[0], 'Primary branch service label changed');
$dvm_config_primary = 'eth&amp;1'; $dvm_config_footerformat = 'd';
check(strpos(dvm_build_dashboard_mini(), 'eth&amp;1 /') === 0, 'Already encoded configured interface was double escaped');
check(count(explode(';', dvm_build_dashboard())) === 10, 'Dashboard metric protocol changed');
$generatedNames = [];
foreach ($commands as $command) {
    if (strpos($command, 'vnstati ') !== 0) continue;
    check(preg_match('~-o [\'"]?/usr/local/emhttp/plugins/dvm/images/([a-zA-Z0-9_-]+\.png)[\'"]? -i ~', $command, $match) === 1, 'Image output path was not confined to safe filenames');
    $generatedNames[] = $match[1];
}
sort($imageNames); sort($generatedNames);
check($imageNames === $generatedNames, 'Rendered image URLs do not match generated filenames');
check(dvm_report_image_name('../escape<"&', 'h') !== dvm_report_image_name('other', 'h'), 'Distinct interface images collided');
check(strpos(dvm_report_image_name('../escape<"&', 'h'), '/') === false, 'Image name contains a path separator');
check(json_encode(dvm_report_html("invalid\xFF")) !== false, 'Malformed UTF-8 broke JSON output');
echo "PASS: escaped report labels, complete service names, nested filtering spans, and image URL boundaries\n";
