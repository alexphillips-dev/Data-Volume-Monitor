<?php
/* Data Volume Monitor automation outcomes. Copyright 2026 alexphillips-dev.
 * Licensed under GPL-2.0. Runtime records contain no user-script output.
 */
function dvm_outcome_root() { return '/var/run/dvm/outcomes'; }
function dvm_outcome_rule($rule) {
    return is_string($rule) && preg_match('/^(primary-[hdmy]-(?:rx|tx)|secondary-[1-6])$/D', $rule);
}
function dvm_outcome_rules() {
    $rules = [];
    foreach (['h', 'd', 'm', 'y'] as $time) { foreach (['rx', 'tx'] as $mode) { $rules[] = "primary-$time-$mode"; } }
    for ($slot = 1; $slot <= 6; $slot++) { $rules[] = "secondary-$slot"; }
    return $rules;
}
function dvm_outcome_digest($config, $actions) {
    if (!is_file($config) || !is_readable($config)) { throw new RuntimeException('Configuration unavailable'); }
    $configHash = hash_file('sha256', $config);
    $actionHash = is_file($actions) ? hash_file('sha256', $actions) : 'missing';
    if ($configHash === false || $actionHash === false) { throw new RuntimeException('Configuration unavailable'); }
    return hash('sha256', $configHash . ':' . $actionHash);
}
function dvm_outcome_component($name, $code) {
    if ($code === 'disabled') { return ['code' => $code, 'status' => 'disabled', 'reason' => 'Not enabled for this transition.']; }
    if ($code === 'pending') { return ['code' => $code, 'status' => 'pending', 'reason' => 'Attempt started; completion has not been recorded.']; }
    if ((!is_int($code) && !is_string($code)) || !preg_match('/^[0-9]{1,3}$/D', (string)$code) || (int)$code > 255) {
        throw new RuntimeException('Invalid component status');
    }
    $code = (int)$code;
    $labels = ['docker' => 'Docker action', 'vm' => 'VM network action', 'custom' => 'Custom script/function', 'notification' => 'Notification delivery'];
    return ['code' => $code, 'status' => $code === 0 ? 'success' : 'failed',
        'reason' => $code === 0 ? 'Completed successfully.' : $labels[$name] . ' exited with status ' . $code . '; see the system log.'];
}
function dvm_outcome_read($rule) {
    if (!dvm_outcome_rule($rule) || is_link(dvm_outcome_root())) { return null; }
    $path = dvm_outcome_root() . '/' . $rule . '.json';
    if (!is_file($path) || is_link($path)) { return null; }
    $contents = @file_get_contents($path, false, null, 0, 16385);
    if ($contents === false || strlen($contents) > 16384) { return null; }
    $record = json_decode($contents, true);
    if (!is_array($record) || ($record['schema'] ?? null) !== 1 || ($record['rule'] ?? null) !== $rule ||
        !is_string($record['fingerprint'] ?? null) || !preg_match('/^[a-f0-9]{64}$/D', $record['fingerprint']) ||
        !in_array($record['state'] ?? null, ['normal', 'exceeded'], true) || !in_array($record['phase'] ?? null, ['started', 'complete'], true) ||
        !is_string($record['interface'] ?? null) || $record['interface'] === '' || strlen($record['interface']) > 15 || preg_match('/[\x00-\x20\/]/', $record['interface']) ||
        !is_int($record['attempts'] ?? null) || $record['attempts'] < 1 || $record['attempts'] > 1000000 ||
        !is_string($record['updated_at'] ?? null) || !preg_match('/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/D', $record['updated_at'])) {
        return null;
    }
    try {
        $failed = false;
        $pending = $record['phase'] === 'started';
        $components = [];
        foreach (['docker', 'vm', 'custom', 'notification'] as $name) {
            $components[$name] = dvm_outcome_component($name, $record['components'][$name]['code'] ?? null);
            $failed = $failed || $components[$name]['status'] === 'failed';
            $pending = $pending || $components[$name]['status'] === 'pending';
        }
        $record['components'] = $components;
        $record['status'] = $pending ? 'running' : ($failed ? 'failed' : 'success');
        return array_intersect_key($record, array_flip(['schema', 'rule', 'fingerprint', 'interface', 'state', 'phase', 'updated_at', 'attempts', 'components', 'status']));
    } catch (Throwable $error) { return null; }
}
function dvm_outcome_write($record, $writer = null) {
    $directory = dvm_outcome_root();
    if (is_link($directory) || (!is_dir($directory) && !mkdir($directory, 0755, true))) {
        throw new RuntimeException('Outcome directory unavailable');
    }
    $temporary = tempnam($directory, '.attempt-');
    if ($temporary === false) { throw new RuntimeException('Outcome file unavailable'); }
    $stream = null;
    try {
        if (realpath(dirname($temporary)) !== realpath($directory) || !chmod($temporary, 0644)) {
            throw new RuntimeException('Outcome stage unavailable');
        }
        $payload = json_encode($record, JSON_UNESCAPED_SLASHES);
        if ($payload === false) { throw new RuntimeException('Outcome encoding failed'); }
        $payload .= "\n";
        $stream = fopen($temporary, 'wb');
        if ($stream === false) { throw new RuntimeException('Outcome stage unavailable'); }
        $count = $writer === null ? fwrite($stream, $payload) : $writer($stream, $payload);
        if ($count !== strlen($payload) || !fflush($stream) || (function_exists('fsync') && !fsync($stream))) {
            throw new RuntimeException('Outcome stage write incomplete');
        }
        fclose($stream);
        $stream = null;
        if (!rename($temporary, $directory . '/' . $record['rule'] . '.json')) {
            throw new RuntimeException('Outcome write failed');
        }
    } finally {
        if (is_resource($stream)) { fclose($stream); }
        if (is_file($temporary)) { unlink($temporary); }
    }
}
function dvm_outcome_record($operation, $rule, $digest, $state, $iface, $codes) {
    if (!dvm_outcome_rule($rule) || !preg_match('/^[a-f0-9]{64}$/D', $digest) || !in_array($state, ['normal', 'exceeded'], true) ||
        $iface === '' || strlen($iface) > 15 || preg_match('/[\x00-\x20\/]/', $iface) || count($codes) !== 4) {
        throw new RuntimeException('Invalid outcome');
    }
    $previous = dvm_outcome_read($rule);
    $same = $previous && hash_equals($previous['fingerprint'], $digest) && $previous['state'] === $state;
    if ($operation === 'finish' && (!$same || $previous['status'] !== 'running')) { throw new RuntimeException('No matching attempt'); }
    $record = ['schema' => 1, 'rule' => $rule, 'fingerprint' => $digest, 'interface' => $iface, 'state' => $state, 'phase' => $operation === 'begin' ? 'started' : 'complete',
        'updated_at' => gmdate('Y-m-d\TH:i:s\Z'), 'attempts' => ($same ? $previous['attempts'] : 0) + ($operation === 'begin' ? 1 : 0), 'components' => []];
    $pending = $failed = false;
    foreach (array_combine(['docker', 'vm', 'custom', 'notification'], $codes) as $name => $code) {
        $record['components'][$name] = dvm_outcome_component($name, $code);
        $pending = $pending || $record['components'][$name]['status'] === 'pending';
        $failed = $failed || $record['components'][$name]['status'] === 'failed';
    }
    // A begin with no enabled components is still a valid in-progress attempt.
    $record['status'] = $operation === 'begin' ? 'running' : ($failed ? 'failed' : 'success');
    dvm_outcome_write($record);
}
function dvm_outcome_retry($rule, $digest, $state) {
    $record = dvm_outcome_read($rule);
    if (!$record || $record['status'] !== 'failed' || !hash_equals($record['fingerprint'], $digest) || $record['state'] !== $state) {
        throw new RuntimeException('Retry rejected: no matching failure, configuration changed, or threshold state changed.');
    }
    return array_values(array_map(function ($component) { return $component['code']; }, $record['components']));
}
function dvm_outcome_list() {
    try { $digest = dvm_outcome_digest('/etc/vnstat/dvm.cfg', '/etc/vnstat/dvm-user-actions.sh'); }
    catch (Throwable $error) { $digest = null; }
    $outcomes = [];
    foreach (dvm_outcome_rules() as $rule) {
        $record = dvm_outcome_read($rule);
        if (!$record) { continue; }
        $record['retryable'] = $record['status'] === 'failed' && $digest !== null && hash_equals($record['fingerprint'], $digest);
        unset($record['fingerprint'], $record['schema']);
        $outcomes[] = $record;
    }
    return $outcomes;
}
function dvm_outcome_clear() {
    $lock = @fopen('/var/lock/dvm-notify.lock', 'c');
    if ($lock === false) { throw new RuntimeException('Automation lock unavailable; outcomes not cleared.'); }
    try {
        if (!flock($lock, LOCK_EX | LOCK_NB)) { throw new RuntimeException('Automation is active; outcomes not cleared.'); }
        $directory = dvm_outcome_root();
        if (is_link($directory)) { throw new RuntimeException('Outcome directory is a link; cleanup refused.'); }
        if (!is_dir($directory)) { return; }
        foreach (dvm_outcome_rules() as $rule) {
            $path = $directory . '/' . $rule . '.json';
            if (is_file($path) || is_link($path)) {
                if (!unlink($path)) { throw new RuntimeException('Outcome cleanup failed.'); }
            } elseif (file_exists($path)) { throw new RuntimeException('Unexpected outcome entry; cleanup refused.'); }
        }
        $entries = scandir($directory);
        if ($entries !== false && count($entries) === 2 && !rmdir($directory)) {
            throw new RuntimeException('Empty outcome directory cleanup failed.');
        }
    } finally { fclose($lock); }
}
if (PHP_SAPI === 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    try {
        $operation = $argv[1] ?? '';
        if ($operation === 'digest' && count($argv) === 4) { echo dvm_outcome_digest($argv[2], $argv[3]) . "\n"; }
        elseif (in_array($operation, ['begin', 'finish'], true) && count($argv) === 10) {
            dvm_outcome_record($operation, $argv[2], $argv[3], $argv[4], $argv[5], array_slice($argv, 6));
        } elseif ($operation === 'clear' && count($argv) === 2) { dvm_outcome_clear(); }
        elseif ($operation === 'retry' && count($argv) === 5) {
            echo implode(' ', dvm_outcome_retry($argv[2], $argv[3], $argv[4])) . "\n";
        } else { throw new RuntimeException('Invalid outcome operation'); }
    } catch (Throwable $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        exit(1);
    }
}
