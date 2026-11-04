<?php
require __DIR__ . '/../source/usr/local/emhttp/plugins/dvm/include/dvm_config_guard.php';

function guard_check($condition, $message) {
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

$default = ";DatabaseDir \"/var/lib/vnstat\"\n;PidFile \"/var/run/vnstat/vnstat.pid\"\n";
$custom = "DatabaseDir \"/mnt/cache/traffic history\"\nPidFile \"/run/custom-vnstat.pid\"\n";
$paths = dvm_config_effective_paths('unused', function () use ($default) { return $default; });
guard_check($paths['DatabaseDir'] === '/var/lib/vnstat/', 'Effective defaults were not resolved');
$paths = dvm_config_effective_paths('unused', function () use ($custom) { return $custom; });
guard_check($paths['DatabaseDir'] === '/mnt/cache/traffic history/', 'Custom path with spaces was not preserved');
guard_check($paths['PidFile'] === '/run/custom-vnstat.pid', 'Custom PID path was not resolved');
$reader = function ($path) use ($default, $custom) { return basename($path) === 'vnstat.conf' ? $default : $custom; };
$blocked = false;
try {
    dvm_config_guard_validate('/etc/vnstat/vnstat.conf', $custom, $reader, function () { return true; });
} catch (InvalidArgumentException $expected) {
    $blocked = true;
}
guard_check($blocked, 'Changing storage/PID paths while running was allowed');
dvm_config_guard_validate('/etc/vnstat/vnstat.conf', $custom, $reader, function () { return false; });
dvm_config_guard_validate('/etc/vnstat/vnstat.conf', $custom, function ($path) use ($custom) {
    if (basename($path) === 'vnstat.conf') {
        throw new RuntimeException('Current configuration is invalid');
    }
    return $custom;
}, function () { return false; });
dvm_config_guard_validate('/etc/vnstat/vnstat.conf', $default, function () use ($default) { return $default; }, function () { return true; });
dvm_config_guard_validate('/etc/vnstat/dvm-user-actions.sh', 'anything', function () { throw new RuntimeException('Should not be called'); });
$blocked = false;
try {
    dvm_config_effective_paths('unused', function () { return 'DatabaseDir "relative/path"'; });
} catch (RuntimeException $expected) {
    $blocked = true;
}
guard_check($blocked, 'Invalid effective configuration was accepted');
echo "PASS: native effective defaults, custom paths, active-daemon guard, stopped edits, unchanged paths, non-config files, invalid output.\n";
