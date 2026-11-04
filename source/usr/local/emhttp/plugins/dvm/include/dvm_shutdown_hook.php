<?php
// Only the exact plugin-owned hook is managed here; other host hooks are retained.
function dvm_shutdown_hook_block()
{
    return <<<'SH'
# BEGIN Data Volume Monitor shutdown backup
if [ -x /etc/rc.d/rc.vnstat ]; then
    if /etc/rc.d/rc.vnstat backup_db; then
        :
    else
        dvm_shutdown_backup_status=$?
        logger -t dvm "ERROR: shutdown database backup failed (exit ${dvm_shutdown_backup_status})." || :
        unset dvm_shutdown_backup_status
    fi
fi
# END Data Volume Monitor shutdown backup

SH;
}

function dvm_install_shutdown_hook($path, $validator = null, $publisher = null)
{
    dvm_update_shutdown_hook($path, false, $validator, $publisher);
}

function dvm_remove_shutdown_hook($path, $validator = null, $publisher = null)
{
    dvm_update_shutdown_hook($path, true, $validator, $publisher);
}

function dvm_update_shutdown_hook($path, $remove, $validator = null, $publisher = null)
{
    if ($remove && !file_exists($path) && !is_link($path)) {
        return;
    }
    if (!is_file($path) || is_link($path) || !is_readable($path) || !is_writable($path)) {
        throw new RuntimeException('Cannot update DVM shutdown backup hook: the host shutdown script is missing, linked, or inaccessible.');
    }
    $original = @file_get_contents($path);
    $metadata = @stat($path);
    if ($original === false || $metadata === false
        || !preg_match('~\A(#!(?:/(?:usr/)?bin/(?:ba)?sh|/usr/bin/env[ \t]+(?:ba)?sh)(?:[ \t]+[^\r\n]*)?)(\r?\n)~', $original, $header)) {
        throw new RuntimeException('Cannot update DVM shutdown backup hook: unsupported host shutdown script format.');
    }
    $newline = $header[2];
    $block = str_replace("\n", $newline, dvm_shutdown_hook_block());
    $body = substr($original, strlen($header[0]));
    $begin = '# BEGIN Data Volume Monitor shutdown backup';
    $end = '# END Data Volume Monitor shutdown backup';
    if (strpos($body, $begin) !== false || strpos($body, $end) !== false) {
        if (substr_count($body, $begin) !== 1 || substr_count($body, $end) !== 1 || substr_count($body, $block) !== 1) {
            throw new RuntimeException('Cannot update DVM shutdown backup hook: the existing managed hook was modified or duplicated.');
        }
        $body = str_replace($block, '', $body);
    }
    $legacy = '[ -x /etc/rc.d/rc.vnstat ] && /etc/rc.d/rc.vnstat backup_db | logger';
    $body = preg_replace('~^[ \t]*' . preg_quote($legacy, '~') . '[ \t]*(?:\r?\n|$)~m', '', $body);
    foreach ($remove ? [] : preg_split('/\r?\n/', $body) as $line) {
        if (preg_match('/^\s*(?:#|$)/', $line)) {
            continue;
        }
        if (strpos($line, '/etc/rc.d/rc.vnstat') !== false) {
            throw new RuntimeException('Cannot install DVM shutdown backup: an unrecognized vnStat hook requires manual review.');
        }
    }
    $candidate = $header[0] . ($remove ? '' : $block) . $body;
    if ($validator === null) {
        $validator = function ($file) {
            $output = [];
            $status = 1;
            exec('/bin/bash -n -- ' . escapeshellarg($file) . ' 2>/dev/null', $output, $status);
            return $status === 0;
        };
    }
    if (!$validator($path)) {
        throw new RuntimeException('Cannot update DVM shutdown backup hook: the existing host shutdown script does not pass shell validation.');
    }
    if ($candidate === $original) {
        return;
    }
    $stage = @tempnam(dirname($path), '.dvm-shutdown-');
    if ($stage === false || dirname($stage) !== realpath(dirname($path))) {
        if ($stage !== false) {
            @unlink($stage);
        }
        throw new RuntimeException('Cannot stage the DVM shutdown backup hook beside the host script.');
    }
    try {
        if (@file_put_contents($stage, $candidate) !== strlen($candidate)
            || !@chmod($stage, $metadata['mode'] & 0777)
            || (function_exists('posix_geteuid') && (!@chown($stage, $metadata['uid']) || !@chgrp($stage, $metadata['gid'])))
            || !$validator($stage)) {
            throw new RuntimeException('Cannot validate the staged DVM shutdown backup hook.');
        }
        if (@file_get_contents($path) !== $original) {
            throw new RuntimeException('The host shutdown script changed during hook update; retry the operation.');
        }
        if ($publisher === null) {
            $publisher = function ($from, $to) { return @rename($from, $to); };
        }
        if (!$publisher($stage, $path) || @file_get_contents($path) !== $candidate) {
            throw new RuntimeException('Unable to publish and verify the DVM shutdown backup hook.');
        }
    } finally {
        if (is_file($stage)) {
            @unlink($stage);
        }
    }
}
