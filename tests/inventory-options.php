<?php
// Render production option markup with isolated discovery fixtures.
$root = __DIR__.'/../source/usr/local/emhttp/plugins/dvm';
$page = file_get_contents($root.'/DVMcontrol.page');
if (is_file($root.'/include/dvm_inventory.php')) require $root.'/include/dvm_inventory.php';
function mk_option($selected, $value, $label) {
    return '<option value="'.htmlspecialchars($value, ENT_QUOTES, 'UTF-8').'"'.($selected === $value ? ' selected' : '').'>'.htmlspecialchars($label, ENT_QUOTES, 'UTF-8').'</option>';
}
function check($condition, $message) { if (!$condition) throw new RuntimeException($message); }
function render_choice($page, $id, $configured, $items, $status = 'ok') {
    if (!preg_match('/<select id="'.preg_quote($id, '/').'"[^>]*>[\s\S]*?<\/select>/', $page, $match)) throw new RuntimeException('Missing production selector '.$id);
    $markup = $match[0];
    preg_match_all('/\$dvm_config_\w+/', $markup, $variables);
    foreach (array_unique($variables[0]) as $variable) ${substr($variable, 1)} = htmlspecialchars($configured, ENT_QUOTES, 'UTF-8');
    $dvm_available_dockers = $items ?: false;
    $dvm_available_vms = $items ?: false;
    $dvm_available_interfacs = $items ?: false;
    $dvm_docker_inventory = $dvm_vm_inventory = $dvm_interface_inventory = ['status'=>$status, 'items'=>$items];
    ob_start(); eval('?>'.$markup); $html = ob_get_clean();
    preg_match_all('/<option([^>]*)>([\s\S]*?)<\/option>/', $html, $options, PREG_SET_ORDER);
    $selected = null; $first = null;
    foreach ($options as $option) {
        preg_match('/value=([\'"])(.*?)\1/', $option[1], $value);
        $value = html_entity_decode($value[2] ?? '', ENT_QUOTES, 'UTF-8');
        if ($first === null) $first = $value;
        if (preg_match('/\bselected\b/', $option[1])) $selected = $value;
    }
    return [$selected ?? $first, $html];
}
$failed = 0;
$cases = [
    'missing Docker target survives Apply' => function () use ($page) {
        [$selected, $html] = render_choice($page, 'RXDOCKERHSTOP', 'saved-container', ['other-container']);
        check($selected === 'saved-container', 'Browser selected '.$selected.' instead of saved-container');
        check(strpos($html, 'unavailable') !== false, 'Missing selection is not labelled unavailable');
    },
    'failed VM discovery preserves the saved target and identifies failure' => function () use ($page) {
        [$selected, $html] = render_choice($page, 'RXVMHSTOP', 'Windows 11', [], 'error');
        check($selected === 'Windows 11', 'Browser selected '.$selected.' instead of Windows 11');
        check(strpos($html, 'inventory unavailable') !== false, 'Discovery failure not distinguished');
    },
    'empty successful discovery preserves targets without claiming a command failure' => function () use ($page) {
        [$selected, $html] = render_choice($page, 'RXVMHSTOP', 'Windows 11', []);
        check($selected === 'Windows 11', 'Empty inventory lost saved VM');
        check(strpos($html, 'inventory unavailable') === false, 'Empty inventory misreported as command failure');
    },
    'existing targets and explicit None retain current behavior' => function () use ($page) {
        [$selected] = render_choice($page, 'RXDOCKERHSTOP', 'existing', ['existing']);
        check($selected === 'existing', 'Existing target lost');
        [$selected] = render_choice($page, 'RXDOCKERHSTOP', 'disable', []);
        check($selected === 'disable', 'Explicit None lost');
    },
    'names containing markup round-trip as plain option text' => function () use ($page) {
        $name = 'A&B "<test>"';
        [$selected, $html] = render_choice($page, 'RXVMHSTOP', $name, [$name]);
        check($selected === $name, 'Special-name selection changed');
        check(strpos($html, '<test>') === false, 'Markup was not escaped');
    },
    'every target selector retains an unavailable configured value' => function () use ($page) {
        preg_match_all('/<select id="([^"]+)"[^>]*>\s*<\?=dvm_inventory_options/', $page, $selectors);
        check(count($selectors[1]) === 63, 'Expected all 63 interface and workload selectors');
        foreach ($selectors[1] as $id) {
            [$selected] = render_choice($page, $id, 'saved target', [], 'error');
            check($selected === 'saved target', $id.' lost its unavailable selection');
        }
    },
    'discovery distinguishes successful emptiness from command failure' => function () {
        $empty = dvm_inventory_query('fixture', function () { return ['status'=>0, 'lines'=>[]]; });
        $failed = dvm_inventory_query('fixture', function () { return ['status'=>1, 'lines'=>[]]; });
        $values = dvm_inventory_query('fixture', function () { return ['status'=>0, 'lines'=>['Windows 11', '', 'A&B', 'Windows 11']]; });
        check($empty === ['status'=>'ok', 'items'=>[]], 'Empty inventory not preserved');
        check($failed === ['status'=>'error', 'items'=>[]], 'Failure not identified');
        check($values === ['status'=>'ok', 'items'=>['Windows 11', 'A&B']], 'Names changed during discovery');
    }
];
foreach ($cases as $name=>$test) {
    try { $test(); echo 'PASS '.$name."\n"; }
    catch (Throwable $error) { $failed++; echo 'FAIL '.$name.': '.$error->getMessage()."\n"; }
}
exit($failed ? 1 : 0);
