<?php
// Copyright 2026 alexphillips-dev. Licensed under GPL-2.0.

function dvm_inventory_query($command, $runner = null)
{
    if ($runner === null) {
        $runner = function ($query) {
            $lines = [];
            $status = 1;
            exec($query, $lines, $status);
            return ['status' => $status, 'lines' => $lines];
        };
    }
    $result = $runner($command);
    if (!is_array($result) || ($result['status'] ?? 1) !== 0 || !is_array($result['lines'] ?? null)) {
        return ['status' => 'error', 'items' => []];
    }
    $items = [];
    foreach ($result['lines'] as $line) {
        if (is_string($line) && $line !== '') $items[] = $line;
    }
    return ['status' => 'ok', 'items' => array_values(array_unique($items))];
}

function dvm_inventory_options($configured, $inventory, $noneValue = 'disable', $noneLabel = 'None', $prefix = '')
{
    // Existing dvm_config.php values are HTML-escaped; decode once for identity
    // comparison, then encode values and labels at this rendering boundary.
    $selected = html_entity_decode((string)$configured, ENT_QUOTES, 'UTF-8');
    $escape = function ($value) { return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8'); };
    $option = function ($value, $label) use ($selected, $escape) {
        return '<option value="'.$escape($value).'"'.($selected === $value ? ' selected' : '').'>'.$escape($label).'</option>';
    };
    $items = $inventory['items'];
    $html = $option($noneValue, $noneLabel);
    if ($selected !== '' && $selected !== $noneValue && !in_array($selected, $items, true)) {
        $reason = $inventory['status'] === 'error' ? 'inventory unavailable' : 'unavailable';
        $html .= $option($selected, $prefix.$selected.' ('.$reason.')');
    }
    foreach ($items as $item) {
        if ($item !== $noneValue) $html .= $option($item, $prefix.$item);
    }
    return $html;
}
