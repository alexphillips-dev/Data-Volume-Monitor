<?php
// Copyright 2026 alexphillips-dev. Licensed under GPL-2.0.
require_once __DIR__.'/dvm_config_guard.php';

function dvm_editor_resolve($requested, $base)
{
    if (!is_string($requested) || $requested === '' || strpos($requested, "\0") !== false) {
        throw new InvalidArgumentException('Invalid configuration file.');
    }
    $root = realpath($base);
    $path = realpath($requested);
    // Files are persisted by basename, so only direct regular children are supported.
    if (!$root || !$path || !is_file($path) || is_link($requested)
        || dirname($path) !== $root
        || !in_array(pathinfo($path, PATHINFO_EXTENSION), ['conf', 'sh'], true)) {
        throw new InvalidArgumentException('Select a .conf or .sh file directly inside the configuration directory.');
    }
    return $path;
}

function dvm_editor_read($requested, $base)
{
    $path = dvm_editor_resolve($requested, $base);
    if (!$path || !is_file($path)) {
        throw new InvalidArgumentException('Invalid configuration file.');
    }
    $contents = @file_get_contents($path);
    if ($contents === false) {
        throw new RuntimeException('Unable to read the configuration file.');
    }
    return $contents;
}

function dvm_editor_save($requested, $contents, $base, $persistent, $replace = null)
{
    if (!is_string($contents)) {
        throw new InvalidArgumentException('Configuration content must be a string.');
    }
    $path = dvm_editor_resolve($requested, $base);
    $contents = str_replace("\r", '', $contents);
    $replace = $replace ?? function ($from, $to) { return @rename($from, $to); };
    $lock = @fopen(dirname($path).'/.dvm-editor.lock', 'c');
    if (!$lock || !flock($lock, LOCK_EX)) {
        if ($lock) fclose($lock);
        throw new RuntimeException('Unable to lock the configuration for saving.');
    }
    $staged = [];
    try {
        $path = dvm_editor_resolve($requested, $base);
        dvm_config_guard_validate($path, $contents);
        if (is_link($persistent) || (!is_dir($persistent) && !@mkdir($persistent, 0755, true))) {
            throw new RuntimeException('Persistent configuration directory is unavailable; no files were changed.');
        }
        $persistent = realpath($persistent);
        $backup = $persistent.DIRECTORY_SEPARATOR.basename($path);
        if (is_link($backup) || (file_exists($backup) && !is_file($backup))) {
            throw new RuntimeException('Invalid persistent configuration file; no files were changed.');
        }
        $mode = fileperms($path) & 0777;
        $runtimeStage = dvm_editor_stage(dirname($path), $contents, $mode);
        $staged[] = $runtimeStage;
        $flashStage = dvm_editor_stage($persistent, $contents, $mode);
        $staged[] = $flashStage;
        $rollback = null;
        if (is_file($backup)) {
            $previous = @file_get_contents($backup);
            if ($previous === false) throw new RuntimeException('Unable to preserve the persistent configuration.');
            $rollback = dvm_editor_stage($persistent, $previous, fileperms($backup) & 0777);
            $staged[] = $rollback;
        }
        if (!$replace($flashStage, $backup)) {
            throw new RuntimeException('Unable to replace the persistent configuration; no files were changed.');
        }
        if (!$replace($runtimeStage, $path)) {
            $restored = $rollback ? $replace($rollback, $backup) : @unlink($backup);
            if (!$restored) {
                // Keep the recovery copy if the filesystem also rejects rollback.
                $staged = array_values(array_diff($staged, [$rollback]));
                throw new RuntimeException('Runtime save and persistent rollback failed. Runtime is unchanged; persistent recovery copy: '.($rollback ?? 'none (file was newly created)'));
            }
            throw new RuntimeException('Runtime save failed; the previous persistent configuration was restored.');
        }
        return $path;
    } finally {
        foreach ($staged as $temporary) if (is_file($temporary)) @unlink($temporary);
        flock($lock, LOCK_UN);
        fclose($lock);
    }
}

function dvm_editor_stage($directory, $contents, $mode)
{
    $temporary = @tempnam($directory, '.dvm-stage-');
    if ($temporary === false || realpath(dirname($temporary)) !== realpath($directory)) {
        if ($temporary !== false) @unlink($temporary);
        throw new RuntimeException('Unable to stage the configuration; no files were changed.');
    }
    $stream = @fopen($temporary, 'wb');
    try {
        if (!$stream || @fwrite($stream, $contents) !== strlen($contents) || !@fflush($stream)
            || (function_exists('fsync') && !@fsync($stream)) || !@chmod($temporary, $mode)) {
            throw new RuntimeException('Unable to stage the complete configuration; no files were changed.');
        }
    } catch (Throwable $error) {
        if ($stream) fclose($stream);
        @unlink($temporary);
        throw $error;
    }
    fclose($stream);
    return $temporary;
}
