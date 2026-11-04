<?php
// Copyright 2026 alexphillips-dev. Licensed under GPL-2.0.
// Installed builds carry their release channel; a host checkout is not required.
function dvm_release_read($path = null)
{
    $path = $path ?? __DIR__ . '/../release.json';
    if (!is_file($path) || is_link($path) || !is_readable($path)) return null;
    $contents = @file_get_contents($path, false, null, 0, 4097);
    if ($contents === false || strlen($contents) > 4096) return null;
    $metadata = json_decode($contents, true, 8);
    if (!is_array($metadata) || count($metadata) !== 4 || ($metadata['schema'] ?? null) !== 1
        || !is_string($metadata['channel'] ?? null)
        || !in_array($metadata['channel'], ['dev', 'main'], true)
        || !is_string($metadata['version'] ?? null) || strlen($metadata['version']) > 64
        || !preg_match('/^[0-9]+(?:\.[0-9]+)+$/D', $metadata['version'])) return null;
    $expected = 'https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/'
        . $metadata['channel'] . '/plugin/dvm.plg';
    if (($metadata['plugin_url'] ?? null) !== $expected) return null;
    return $metadata;
}

function dvm_release_summary($path = null)
{
    $metadata = dvm_release_read($path);
    if ($metadata === null) return 'Unknown (channel unavailable)';
    $channel = $metadata['channel'] === 'main' ? 'Stable' : 'Development';
    return $metadata['version'] . ' (' . $channel . ')';
}
