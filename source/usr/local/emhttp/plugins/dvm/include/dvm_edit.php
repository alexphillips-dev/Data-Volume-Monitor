<?
/* Copyright Derek Macias (parts of code from NUT package)
 * Copyright macester (parts of code from NUT package)
 * Copyright gfjardim (parts of code from NUT package)
 * Copyright SimonF (parts of code from NUT package)
 * Copyright Mohamed Emad (icon from vnstat-client package)
 * Copyright desertwitch
 * Modified 2026-11-04: restrict configuration editor file access.
 *
 * Copyright Dan Landon
 * Copyright Bergware International
 * Copyright Lime Technology
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License 2
 * as published by the Free Software Foundation.
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 */
require_once __DIR__.'/dvm_editor.php';
header('Content-Type: application/json; charset=utf-8');
try {
    echo json_encode(dvm_editor_read($_GET['editfile'] ?? null, '/etc/vnstat/'));
} catch (InvalidArgumentException $error) {
    http_response_code(400);
    echo json_encode(['error' => $error->getMessage()]);
} catch (RuntimeException $error) {
    http_response_code(500);
    echo json_encode(['error' => $error->getMessage()]);
}
?>
