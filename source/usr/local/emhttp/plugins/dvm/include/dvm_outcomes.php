<?php
require_once __DIR__ . '/dvm_outcome_store.php';
header('Content-Type: application/json');
header('Cache-Control: no-store');
echo json_encode(['success' => true, 'outcomes' => dvm_outcome_list()]);
