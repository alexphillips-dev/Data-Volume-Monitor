<?
/* Copyright Derek Macias (parts of code from NUT package)
 * Copyright macester (parts of code from NUT package)
 * Copyright gfjardim (parts of code from NUT package)
 * Copyright SimonF (parts of code from NUT package)
 * Copyright Mohamed Emad (icon from vnstat-client package)
 * Copyright desertwitch
 * Modified 2026-11-04: Data Volume Monitor naming and repository transition.
 * Modified 2026-11-04: validate paths and preserve configuration on save failure.
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
    $path = dvm_editor_save(
        $_POST['editfile'] ?? null,
        $_POST['editdata'] ?? null,
        '/etc/vnstat/',
        '/boot/config/plugins/dvm/vnstat/'
    );
    echo json_encode(['success' => true, 'saved' => $path]);
} catch (InvalidArgumentException $error) {
    http_response_code(400);
    echo json_encode(['error' => $error->getMessage()]);
} catch (RuntimeException $error) {
    http_response_code(500);
    echo json_encode(['error' => $error->getMessage()]);
}
?>
