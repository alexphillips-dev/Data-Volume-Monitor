<?php
// Resolve paths from vnStat's effective configuration, including compiled defaults.
function dvm_config_effective_paths($path, $reader = null)
{
    if ($reader === null) {
        $reader = function ($configPath) {
            $lines = [];
            $status = 1;
            exec('/usr/bin/vnstat --config ' . escapeshellarg($configPath) . ' --showconfig 2>/dev/null', $lines, $status);
            if ($status !== 0) {
                throw new RuntimeException('Unable to read the effective vnStat configuration.');
            }
            return implode("\n", $lines);
        };
    }
    $output = $reader($path);
    $paths = [];
    foreach (['DatabaseDir', 'PidFile'] as $key) {
        // --showconfig prefixes effective default values with a semicolon.
        if (!preg_match('/^\h*;?' . $key . '\h+"([^"\r\n]+)"\h*$/m', $output, $match)
            || $match[1][0] !== '/' || strpos($match[1], "\0") !== false) {
            throw new RuntimeException('Unable to resolve the vnStat ' . $key . ' path.');
        }
        $paths[$key] = $key === 'DatabaseDir' ? rtrim($match[1], '/') . '/' : $match[1];
    }
    return $paths;
}

function dvm_config_guard_validate($path, $contents, $reader = null, $running = null)
{
    if (basename($path) !== 'vnstat.conf') {
        return;
    }
    $temporary = @tempnam(sys_get_temp_dir(), 'dvm-config-');
    if ($temporary === false) {
        throw new RuntimeException('Unable to validate the vnStat configuration.');
    }
    try {
        if (@file_put_contents($temporary, $contents) !== strlen($contents)) {
            throw new RuntimeException('Unable to validate the vnStat configuration.');
        }
        $proposed = dvm_config_effective_paths($temporary, $reader);
        if ($running === null) {
            $running = function () {
                $lines = [];
                $status = 1;
                exec('pgrep -x vnstatd 2>/dev/null', $lines, $status);
                if ($status > 1) {
                    throw new RuntimeException('Unable to verify that vnStat is stopped.');
                }
                return $status === 0;
            };
        }
        // A stopped service can repair a broken current configuration.
        if ($running()) {
            $current = dvm_config_effective_paths($path, $reader);
            if ($proposed !== $current) {
                throw new InvalidArgumentException('Stop Data Volume Monitor before changing DatabaseDir or PidFile.');
            }
        }
    } finally {
        @unlink($temporary);
    }
}
