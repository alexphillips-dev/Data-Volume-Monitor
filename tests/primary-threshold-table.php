<?php
// Render only the production threshold fragment: no Unraid bootstrap or commands.
$root = __DIR__.'/../source/usr/local/emhttp/plugins/dvm';
$page = file_get_contents($root.'/DVMcontrol.page');
$config = file_get_contents($root.'/include/dvm_config.php');
require $root.'/include/dvm_inventory.php';
function mk_option($selected, $value, $label) {
    return '<option value="'.htmlspecialchars($value, ENT_QUOTES, 'UTF-8').'"'.($selected === $value ? ' selected' : '').'>'.htmlspecialchars($label, ENT_QUOTES, 'UTF-8').'</option>';
}
function check($condition, $message) {
    if (!$condition) throw new RuntimeException($message);
}
function primary_fields() {
    $rows = [];
    foreach (['H'=>'Last Hour', 'D'=>'Last Day', 'M'=>'Last Month', 'Y'=>'Last Year'] as $period=>$label) {
        foreach (['RX'=>'IN-bound', 'TX'=>'OUT-bound'] as $direction=>$directionLabel) {
            $rows[] = ['period'=>$label, 'direction'=>$directionLabel, 'fields'=>[
                $direction.'LIMIT'.$period, $direction.'UNIT'.$period,
                $direction.'DOCKER'.$period.'STOP', $direction.'DOCKER'.$period.'START',
                $direction.'VM'.$period.'STOP', $direction.'VM'.$period.'START'
            ]];
        }
    }
    return $rows;
}
function render_primary($saved) {
    global $page, $config;
    // Reuse the actual persisted-setting mappings, excluding runtime discovery.
    check(preg_match('/(\$dvm_config_service[\s\S]*?)(?=\$dvm_config_running)/', $config, $mapping) === 1, 'Missing configuration mappings');
    $dvm_config_cfg = $saved;
    eval($mapping[1]);
    $dvm_docker_inventory = ['status'=>'ok', 'items'=>['existing-container']];
    $dvm_vm_inventory = ['status'=>'error', 'items'=>[]];
    $start = strpos($page, '<span class="left"><i class="icon fa fa-bullhorn"></i> Primary Interface');
    $end = strpos($page, '<span class="left"><i class="icon fa fa-bullhorn"></i> Secondary Interface');
    check($start !== false && $end > $start, 'Missing threshold sections');
    ob_start();
    eval('?>'.substr($page, $start, $end - $start));
    $html = ob_get_clean();
    $dom = new DOMDocument();
    @$dom->loadHTML('<!doctype html><html><body><form id="fixture">'.$html.'</form></body></html>');
    return [new DOMXPath($dom), $html];
}
function posted_fields($xpath) {
    $posted = [];
    foreach ($xpath->query('//input[@name] | //select[@name]') as $control) {
        $name = $control->getAttribute('name');
        check(!isset($posted[$name]), 'Duplicate submitted field '.$name);
        check(!$control->hasAttribute('disabled'), 'Disabled submitted field '.$name);
        check($control->getAttribute('id') === $name, 'Changed field identity '.$name);
        if ($control->tagName === 'input') {
            $posted[$name] = $control->getAttribute('value');
        } else {
            $options = $xpath->query('option[@selected]', $control);
            check($options->length === 1, 'Expected one saved selection for '.$name);
            $posted[$name] = $options->item(0)->getAttribute('value');
        }
    }
    return $posted;
}
$saved = ['PRIMARY'=>'eth0'];
foreach (primary_fields() as $index=>$row) {
    foreach ($row['fields'] as $column=>$key) {
        $saved[$key] = match ($column) {
            0 => (string)(101 + $index),
            1 => ['B', 'KB', 'MB', 'GB', 'TB'][$index % 5],
            2 => 'existing-container',
            3 => 'missing-container-'.$index,
            4 => 'VM "'.$index.'" <test> & private',
            5 => 'disable',
        };
    }
}
$failed = 0;
$cases = [
    'primary thresholds render eight rows in the native table layout' => function () use ($saved) {
        [$xpath] = render_primary($saved);
        $tables = $xpath->query('//table[@id="dvm-primary-thresholds" and contains(concat(" ", normalize-space(@class), " "), " tablesorter ")]');
        check($tables->length === 1, 'Primary section still uses stacked fields instead of a table');
        $table = $tables->item(0);
        check($xpath->query('thead/tr/th[@scope="col"]', $table)->length === 9, 'Missing column headers');
        $rows = $xpath->query('tbody/tr', $table);
        check($rows->length === 8, 'Expected all eight primary rules');
        foreach (primary_fields() as $index=>$expected) {
            $row = $rows->item($index);
            check($xpath->query('td', $row)->length === 9, 'Wrong cell count');
            check(trim($xpath->query('td[1]', $row)->item(0)->textContent) === $saved['PRIMARY'], 'Wrong primary interface');
            check(trim($xpath->query('td[2]', $row)->item(0)->textContent) === $expected['direction'], 'Wrong row direction');
            check(trim($xpath->query('td[3]', $row)->item(0)->textContent) === $expected['period'], 'Wrong row timespan');
            $actual = [];
            foreach ($xpath->query('.//input | .//select', $row) as $control) {
                $actual[] = $control->getAttribute('name');
                check($control->hasAttribute('aria-label'), 'Missing accessible label');
            }
            check($actual === $expected['fields'], 'Cross-wired row controls');
        }
        check($xpath->query('//div[@role="region" and @tabindex="0" and @aria-label="Primary interface thresholds"]')->length === 1, 'Missing keyboard-accessible scroll region');
    },
    'all 48 persisted fields survive rendering and simulated Apply and reload' => function () use ($saved) {
        [$xpath, $html] = render_primary($saved);
        $posted = posted_fields($xpath);
        $expected = $saved;
        unset($expected['PRIMARY']);
        check(count($posted) === 48 && $posted === $expected, 'Saved field values changed');
        check(strpos($html, '<test>') === false, 'Saved workload markup was not escaped');
        check(strpos($html, 'unavailable') !== false, 'Missing saved workload was not retained');
        [$reloaded] = render_primary(['PRIMARY'=>$saved['PRIMARY']] + $posted);
        check(posted_fields($reloaded) === $posted, 'Simulated Apply/reload changed values');
    },
    'disabled defaults and every unit remain editable' => function () use ($root) {
        [$xpath] = render_primary(parse_ini_file($root.'/default.cfg'));
        $posted = posted_fields($xpath);
        foreach (primary_fields() as $row) {
            check($posted[$row['fields'][0]] === '-1', 'Disabled default changed');
            $unit = $xpath->query('//select[@id="'.$row['fields'][1].'"]/option');
            $values = [];
            foreach ($unit as $option) $values[] = $option->getAttribute('value');
            check($values === ['B', 'KB', 'MB', 'GB', 'TB'], 'Unit options changed');
            foreach (array_slice($row['fields'], 2) as $key) check($posted[$key] === 'disable', 'Default action changed');
        }
    },
];
foreach ($cases as $name=>$test) {
    try { $test(); echo 'PASS '.$name."\n"; }
    catch (Throwable $error) { $failed++; echo 'FAIL '.$name.': '.$error->getMessage()."\n"; }
}
exit($failed ? 1 : 0);
