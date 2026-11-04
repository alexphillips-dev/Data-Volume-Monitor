<?php
/* Data Volume Monitor threshold results shared by the UI and notifier.
 * Copyright 2026 alexphillips-dev. Licensed under GPL-2.0.
 */

function dvm_threshold_decode($json, $iface, $time, $mode)
{
    $periods = ['h' => 'hour', 'd' => 'day', 'm' => 'month', 'y' => 'year'];
    if (!isset($periods[$time]) || !in_array($mode, ['rx', 'tx'], true) || !is_string($json) || strlen($json) > 1048576) {
        return 'error';
    }
    $data = json_decode($json, true, 64, JSON_BIGINT_AS_STRING);
    if (!is_array($data) || !isset($data['interfaces']) || !is_array($data['interfaces']) || count($data['interfaces']) !== 1) {
        return 'error';
    }
    $interface = $data['interfaces'][0] ?? [];
    $alert = $interface['alert'] ?? [];
    $limit = $alert['limit'] ?? [];
    if (!is_array($interface) || !is_array($alert) || !is_array($limit) ||
        ($interface['name'] ?? null) !== $iface || ($alert['type'] ?? null) !== $periods[$time] ||
        ($limit['condition'] ?? null) !== $mode || !isset($limit['exceeded']) || !is_bool($limit['exceeded'])) {
        return 'error';
    }
    foreach (['limit_bytes', 'used_bytes'] as $field) {
        $value = $limit[$field] ?? null;
        if ((!is_int($value) && !is_string($value)) || !preg_match('/^[0-9]+$/D', (string)$value)) {
            return 'error';
        }
        $digits = ltrim((string)$value, '0');
        if (strlen($digits) > 20 || (strlen($digits) === 20 && strcmp($digits, '18446744073709551615') > 0)) {
            return 'error';
        }
    }
    if (ltrim((string)$limit['limit_bytes'], '0') === '') {
        return 'error';
    }
    return $limit['exceeded'] ? 'exceeded' : 'normal';
}

function dvm_threshold_evaluate($iface, $time, $limit, $unit, $mode, $runner = null)
{
    if ((!is_string($limit) && !is_int($limit)) || !is_string($iface) || !is_string($time) || !is_string($unit) || !is_string($mode)) {
        return 'error';
    }
    $limit = trim((string)$limit);
    if ($limit === '-1') {
        return 'disabled';
    }
    if (!preg_match('/^[0-9]+$/D', $limit)) {
        return 'error';
    }
    // Canonical decimal avoids vnStat interpreting a leading zero as octal.
    $limit = ltrim($limit, '0');
    if ($limit === '' || strlen($limit) > 20 || (strlen($limit) === 20 && strcmp($limit, '18446744073709551615') > 0)) {
        return 'error';
    }
    if ($iface === '' || $iface === 'noiface' || strlen($iface) > 15 || preg_match('/[\x00-\x20\/]/', $iface) ||
        !in_array($time, ['h', 'd', 'm', 'y'], true) || !in_array($mode, ['rx', 'tx'], true) ||
        !in_array($unit, ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB'], true)) {
        return 'error';
    }
    // vnStat emits a native structured alert. Exit 0 is requested for both
    // normal and exceeded states; missing/invalid JSON is always an error.
    // Its native comparison preserves units, latest-period and boundary rules.
    $command = 'vnstat --config /etc/vnstat/vnstat.conf --json --alert 1 0 ' .
        implode(' ', array_map('escapeshellarg', [$time, $mode, $limit, $unit])) . ' -i ' . escapeshellarg($iface) . ' 2>/dev/null';
    try {
        if ($runner === null) {
            $output = [];
            $status = 1;
            exec($command, $output, $status);
            $json = implode("\n", $output);
        } else {
            list($json, $status) = $runner($command);
        }
        if ($status !== 0) {
            return 'error';
        }
        return dvm_threshold_decode($json, $iface, $time, $mode);
    } catch (\Throwable $error) {
        return 'error';
    }
}

if (PHP_SAPI === 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    $state = count($argv) === 6 ? dvm_threshold_evaluate($argv[1], $argv[2], $argv[3], $argv[4], $argv[5]) : 'error';
    echo $state . "\n";
    exit($state === 'error' ? 3 : 0);
}
