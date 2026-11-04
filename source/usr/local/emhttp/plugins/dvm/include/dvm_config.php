<?
/* Copyright Derek Macias (parts of code from NUT package)
 * Copyright macester (parts of code from NUT package)
 * Copyright gfjardim (parts of code from NUT package)
 * Copyright SimonF (parts of code from NUT package)
 * Copyright Mohamed Emad (icon from vnstat-client package)
 * Copyright desertwitch
 * Modified 2026-11-04: Data Volume Monitor naming and repository transition.
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
$dvm_config_cfg                = parse_ini_file("/boot/config/plugins/dvm/dvm.cfg");

$dvm_config_service            = trim(isset($dvm_config_cfg['SERVICE'])           ? htmlspecialchars($dvm_config_cfg['SERVICE'])       : 'disable');
$dvm_config_backupdb           = trim(isset($dvm_config_cfg['BACKUPDB'])          ? htmlspecialchars($dvm_config_cfg['BACKUPDB'])      : 'enable');
$dvm_config_report             = trim(isset($dvm_config_cfg['REPORT'])            ? htmlspecialchars($dvm_config_cfg['REPORT'])        : 'text');
$dvm_config_vifaces            = trim(isset($dvm_config_cfg['VIFACES'])           ? htmlspecialchars($dvm_config_cfg['VIFACES'])       : 'enable');
$dvm_config_match_virts        = trim(isset($dvm_config_cfg['MATCHVIRTS'])        ? htmlspecialchars($dvm_config_cfg['MATCHVIRTS'])    : 'disable');
$dvm_config_oifaces            = trim(isset($dvm_config_cfg['OIFACES'])           ? htmlspecialchars($dvm_config_cfg['OIFACES'])       : 'disable');
$dvm_config_autopurge          = trim(isset($dvm_config_cfg['AUTOPURGE'])         ? htmlspecialchars($dvm_config_cfg['AUTOPURGE'])     : 'disable');
$dvm_config_cronint            = trim(isset($dvm_config_cfg['CRONINT'])           ? htmlspecialchars($dvm_config_cfg['CRONINT'])       : 'disable');
$dvm_config_dashb              = trim(isset($dvm_config_cfg['DASHB'])             ? htmlspecialchars($dvm_config_cfg['DASHB'])         : 'enable');
$dvm_config_footer             = trim(isset($dvm_config_cfg['FOOTER'])            ? htmlspecialchars($dvm_config_cfg['FOOTER'])        : 'enable');
$dvm_config_footerformat       = trim(isset($dvm_config_cfg['FOOTERFORMAT'])      ? htmlspecialchars($dvm_config_cfg['FOOTERFORMAT'])  : 'd');
$dvm_config_primary            = trim(isset($dvm_config_cfg['PRIMARY'])           ? htmlspecialchars($dvm_config_cfg['PRIMARY'])       : 'eth0');
$dvm_config_filters            = trim(isset($dvm_config_cfg['FILTERS'])           ? (string)$dvm_config_cfg['FILTERS']       : '');

$dvm_config_good_notify        = trim(isset($dvm_config_cfg['GOODNOTIFY'])        ? htmlspecialchars($dvm_config_cfg['GOODNOTIFY'])  : 'disable');
$dvm_config_bad_notify         = trim(isset($dvm_config_cfg['BADNOTIFY'])         ? htmlspecialchars($dvm_config_cfg['BADNOTIFY']) : 'disable');

$dvm_config_good_actions       = trim(isset($dvm_config_cfg['GOODACTIONS'])       ? htmlspecialchars($dvm_config_cfg['GOODACTIONS'])  : 'disable');
$dvm_config_bad_actions        = trim(isset($dvm_config_cfg['BADACTIONS'])        ? htmlspecialchars($dvm_config_cfg['BADACTIONS']) : 'disable');

$dvm_config_hlimit_rx          = trim(isset($dvm_config_cfg['RXLIMITH'])          ? htmlspecialchars($dvm_config_cfg['RXLIMITH'])  : '-1');
$dvm_config_hlimit_tx          = trim(isset($dvm_config_cfg['TXLIMITH'])          ? htmlspecialchars($dvm_config_cfg['TXLIMITH'])  : '-1');
$dvm_config_hunit_rx           = trim(isset($dvm_config_cfg['RXUNITH'])           ? htmlspecialchars($dvm_config_cfg['RXUNITH'])   : 'GB');
$dvm_config_hunit_tx           = trim(isset($dvm_config_cfg['TXUNITH'])           ? htmlspecialchars($dvm_config_cfg['TXUNITH'])   : 'GB');
$dvm_config_hdocker_rx_start   = trim(isset($dvm_config_cfg['RXDOCKERHSTART'])    ? htmlspecialchars($dvm_config_cfg['RXDOCKERHSTART'])   : 'disable');
$dvm_config_hdocker_rx_stop    = trim(isset($dvm_config_cfg['RXDOCKERHSTOP'])     ? htmlspecialchars($dvm_config_cfg['RXDOCKERHSTOP'])   : 'disable');
$dvm_config_hdocker_tx_start   = trim(isset($dvm_config_cfg['TXDOCKERHSTART'])    ? htmlspecialchars($dvm_config_cfg['TXDOCKERHSTART'])   : 'disable');
$dvm_config_hdocker_tx_stop    = trim(isset($dvm_config_cfg['TXDOCKERHSTOP'])     ? htmlspecialchars($dvm_config_cfg['TXDOCKERHSTOP'])   : 'disable');
$dvm_config_hvm_rx_start       = trim(isset($dvm_config_cfg['RXVMHSTART'])        ? htmlspecialchars($dvm_config_cfg['RXVMHSTART'])   : 'disable');
$dvm_config_hvm_rx_stop        = trim(isset($dvm_config_cfg['RXVMHSTOP'])         ? htmlspecialchars($dvm_config_cfg['RXVMHSTOP'])   : 'disable');
$dvm_config_hvm_tx_start       = trim(isset($dvm_config_cfg['TXVMHSTART'])        ? htmlspecialchars($dvm_config_cfg['TXVMHSTART'])   : 'disable');
$dvm_config_hvm_tx_stop        = trim(isset($dvm_config_cfg['TXVMHSTOP'])         ? htmlspecialchars($dvm_config_cfg['TXVMHSTOP'])   : 'disable');

$dvm_config_dlimit_rx          = trim(isset($dvm_config_cfg['RXLIMITD'])          ? htmlspecialchars($dvm_config_cfg['RXLIMITD'])  : '-1');
$dvm_config_dlimit_tx          = trim(isset($dvm_config_cfg['TXLIMITD'])          ? htmlspecialchars($dvm_config_cfg['TXLIMITD'])  : '-1');
$dvm_config_dunit_rx           = trim(isset($dvm_config_cfg['RXUNITD'])           ? htmlspecialchars($dvm_config_cfg['RXUNITD'])   : 'GB');
$dvm_config_dunit_tx           = trim(isset($dvm_config_cfg['TXUNITD'])           ? htmlspecialchars($dvm_config_cfg['TXUNITD'])   : 'GB');
$dvm_config_ddocker_rx_start   = trim(isset($dvm_config_cfg['RXDOCKERDSTART'])    ? htmlspecialchars($dvm_config_cfg['RXDOCKERDSTART'])   : 'disable');
$dvm_config_ddocker_rx_stop    = trim(isset($dvm_config_cfg['RXDOCKERDSTOP'])     ? htmlspecialchars($dvm_config_cfg['RXDOCKERDSTOP'])   : 'disable');
$dvm_config_ddocker_tx_start   = trim(isset($dvm_config_cfg['TXDOCKERDSTART'])    ? htmlspecialchars($dvm_config_cfg['TXDOCKERDSTART'])   : 'disable');
$dvm_config_ddocker_tx_stop    = trim(isset($dvm_config_cfg['TXDOCKERDSTOP'])     ? htmlspecialchars($dvm_config_cfg['TXDOCKERDSTOP'])   : 'disable');
$dvm_config_dvm_rx_start       = trim(isset($dvm_config_cfg['RXVMDSTART'])        ? htmlspecialchars($dvm_config_cfg['RXVMDSTART'])   : 'disable');
$dvm_config_dvm_rx_stop        = trim(isset($dvm_config_cfg['RXVMDSTOP'])         ? htmlspecialchars($dvm_config_cfg['RXVMDSTOP'])   : 'disable');
$dvm_config_dvm_tx_start       = trim(isset($dvm_config_cfg['TXVMDSTART'])        ? htmlspecialchars($dvm_config_cfg['TXVMDSTART'])   : 'disable');
$dvm_config_dvm_tx_stop        = trim(isset($dvm_config_cfg['TXVMDSTOP'])         ? htmlspecialchars($dvm_config_cfg['TXVMDSTOP'])   : 'disable');

$dvm_config_mlimit_rx          = trim(isset($dvm_config_cfg['RXLIMITM'])          ? htmlspecialchars($dvm_config_cfg['RXLIMITM'])  : '-1');
$dvm_config_mlimit_tx          = trim(isset($dvm_config_cfg['TXLIMITM'])          ? htmlspecialchars($dvm_config_cfg['TXLIMITM'])  : '-1');
$dvm_config_munit_rx           = trim(isset($dvm_config_cfg['RXUNITM'])           ? htmlspecialchars($dvm_config_cfg['RXUNITM'])   : 'GB');
$dvm_config_munit_tx           = trim(isset($dvm_config_cfg['TXUNITM'])           ? htmlspecialchars($dvm_config_cfg['TXUNITM'])   : 'GB');
$dvm_config_mdocker_rx_start   = trim(isset($dvm_config_cfg['RXDOCKERMSTART'])    ? htmlspecialchars($dvm_config_cfg['RXDOCKERMSTART'])   : 'disable');
$dvm_config_mdocker_rx_stop    = trim(isset($dvm_config_cfg['RXDOCKERMSTOP'])     ? htmlspecialchars($dvm_config_cfg['RXDOCKERMSTOP'])   : 'disable');
$dvm_config_mdocker_tx_start   = trim(isset($dvm_config_cfg['TXDOCKERMSTART'])    ? htmlspecialchars($dvm_config_cfg['TXDOCKERMSTART'])   : 'disable');
$dvm_config_mdocker_tx_stop    = trim(isset($dvm_config_cfg['TXDOCKERMSTOP'])     ? htmlspecialchars($dvm_config_cfg['TXDOCKERMSTOP'])   : 'disable');
$dvm_config_mvm_rx_start       = trim(isset($dvm_config_cfg['RXVMMSTART'])        ? htmlspecialchars($dvm_config_cfg['RXVMMSTART'])   : 'disable');
$dvm_config_mvm_rx_stop        = trim(isset($dvm_config_cfg['RXVMMSTOP'])         ? htmlspecialchars($dvm_config_cfg['RXVMMSTOP'])   : 'disable');
$dvm_config_mvm_tx_start       = trim(isset($dvm_config_cfg['TXVMMSTART'])        ? htmlspecialchars($dvm_config_cfg['TXVMMSTART'])   : 'disable');
$dvm_config_mvm_tx_stop        = trim(isset($dvm_config_cfg['TXVMMSTOP'])         ? htmlspecialchars($dvm_config_cfg['TXVMMSTOP'])   : 'disable');

$dvm_config_ylimit_rx          = trim(isset($dvm_config_cfg['RXLIMITY'])          ? htmlspecialchars($dvm_config_cfg['RXLIMITY'])  : '-1');
$dvm_config_ylimit_tx          = trim(isset($dvm_config_cfg['TXLIMITY'])          ? htmlspecialchars($dvm_config_cfg['TXLIMITY'])  : '-1');
$dvm_config_yunit_rx           = trim(isset($dvm_config_cfg['RXUNITY'])           ? htmlspecialchars($dvm_config_cfg['RXUNITY'])   : 'GB');
$dvm_config_yunit_tx           = trim(isset($dvm_config_cfg['TXUNITY'])           ? htmlspecialchars($dvm_config_cfg['TXUNITY'])   : 'GB');
$dvm_config_ydocker_rx_start   = trim(isset($dvm_config_cfg['RXDOCKERYSTART'])    ? htmlspecialchars($dvm_config_cfg['RXDOCKERYSTART'])   : 'disable');
$dvm_config_ydocker_rx_stop    = trim(isset($dvm_config_cfg['RXDOCKERYSTOP'])     ? htmlspecialchars($dvm_config_cfg['RXDOCKERYSTOP'])   : 'disable');
$dvm_config_ydocker_tx_start   = trim(isset($dvm_config_cfg['TXDOCKERYSTART'])    ? htmlspecialchars($dvm_config_cfg['TXDOCKERYSTART'])   : 'disable');
$dvm_config_ydocker_tx_stop    = trim(isset($dvm_config_cfg['TXDOCKERYSTOP'])     ? htmlspecialchars($dvm_config_cfg['TXDOCKERYSTOP'])   : 'disable');
$dvm_config_yvm_rx_start       = trim(isset($dvm_config_cfg['RXVMYSTART'])        ? htmlspecialchars($dvm_config_cfg['RXVMYSTART'])   : 'disable');
$dvm_config_yvm_rx_stop        = trim(isset($dvm_config_cfg['RXVMYSTOP'])         ? htmlspecialchars($dvm_config_cfg['RXVMYSTOP'])   : 'disable');
$dvm_config_yvm_tx_start       = trim(isset($dvm_config_cfg['TXVMYSTART'])        ? htmlspecialchars($dvm_config_cfg['TXVMYSTART'])   : 'disable');
$dvm_config_yvm_tx_stop        = trim(isset($dvm_config_cfg['TXVMYSTOP'])         ? htmlspecialchars($dvm_config_cfg['TXVMYSTOP'])   : 'disable');

$dvm_config_custom1_interface  = trim(isset($dvm_config_cfg['CUSTOM1INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM1INTERFACE'])  : 'noiface');
$dvm_config_custom1_mode       = trim(isset($dvm_config_cfg['CUSTOM1MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM1MODE'])       : 'rx');
$dvm_config_custom1_time       = trim(isset($dvm_config_cfg['CUSTOM1TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM1TIME'])       : 'h');
$dvm_config_custom1_limit      = trim(isset($dvm_config_cfg['CUSTOM1LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM1LIMIT'])      : '-1');
$dvm_config_custom1_unit       = trim(isset($dvm_config_cfg['CUSTOM1UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM1UNIT'])       : 'GB');
$dvm_config_custom1_stop       = trim(isset($dvm_config_cfg['CUSTOM1STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM1STOP'])       : 'disable');
$dvm_config_custom1_start      = trim(isset($dvm_config_cfg['CUSTOM1START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM1START'])      : 'disable');
$dvm_config_custom1_vmstop     = trim(isset($dvm_config_cfg['CUSTOM1VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM1VMSTOP'])     : 'disable');
$dvm_config_custom1_vmstart    = trim(isset($dvm_config_cfg['CUSTOM1VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM1VMSTART'])    : 'disable');

$dvm_config_custom2_interface  = trim(isset($dvm_config_cfg['CUSTOM2INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM2INTERFACE'])  : 'noiface');
$dvm_config_custom2_mode       = trim(isset($dvm_config_cfg['CUSTOM2MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM2MODE'])       : 'rx');
$dvm_config_custom2_time       = trim(isset($dvm_config_cfg['CUSTOM2TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM2TIME'])       : 'h');
$dvm_config_custom2_limit      = trim(isset($dvm_config_cfg['CUSTOM2LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM2LIMIT'])      : '-1');
$dvm_config_custom2_unit       = trim(isset($dvm_config_cfg['CUSTOM2UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM2UNIT'])       : 'GB');
$dvm_config_custom2_stop       = trim(isset($dvm_config_cfg['CUSTOM2STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM2STOP'])       : 'disable');
$dvm_config_custom2_start      = trim(isset($dvm_config_cfg['CUSTOM2START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM2START'])      : 'disable');
$dvm_config_custom2_vmstop     = trim(isset($dvm_config_cfg['CUSTOM2VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM2VMSTOP'])     : 'disable');
$dvm_config_custom2_vmstart    = trim(isset($dvm_config_cfg['CUSTOM2VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM2VMSTART'])    : 'disable');

$dvm_config_custom3_interface  = trim(isset($dvm_config_cfg['CUSTOM3INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM3INTERFACE'])  : 'noiface');
$dvm_config_custom3_mode       = trim(isset($dvm_config_cfg['CUSTOM3MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM3MODE'])       : 'rx');
$dvm_config_custom3_time       = trim(isset($dvm_config_cfg['CUSTOM3TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM3TIME'])       : 'h');
$dvm_config_custom3_limit      = trim(isset($dvm_config_cfg['CUSTOM3LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM3LIMIT'])      : '-1');
$dvm_config_custom3_unit       = trim(isset($dvm_config_cfg['CUSTOM3UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM3UNIT'])       : 'GB');
$dvm_config_custom3_stop       = trim(isset($dvm_config_cfg['CUSTOM3STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM3STOP'])       : 'disable');
$dvm_config_custom3_start      = trim(isset($dvm_config_cfg['CUSTOM3START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM3START'])      : 'disable');
$dvm_config_custom3_vmstop     = trim(isset($dvm_config_cfg['CUSTOM3VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM3VMSTOP'])     : 'disable');
$dvm_config_custom3_vmstart    = trim(isset($dvm_config_cfg['CUSTOM3VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM3VMSTART'])    : 'disable');

$dvm_config_custom4_interface  = trim(isset($dvm_config_cfg['CUSTOM4INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM4INTERFACE'])  : 'noiface');
$dvm_config_custom4_mode       = trim(isset($dvm_config_cfg['CUSTOM4MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM4MODE'])       : 'rx');
$dvm_config_custom4_time       = trim(isset($dvm_config_cfg['CUSTOM4TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM4TIME'])       : 'h');
$dvm_config_custom4_limit      = trim(isset($dvm_config_cfg['CUSTOM4LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM4LIMIT'])      : '-1');
$dvm_config_custom4_unit       = trim(isset($dvm_config_cfg['CUSTOM4UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM4UNIT'])       : 'GB');
$dvm_config_custom4_stop       = trim(isset($dvm_config_cfg['CUSTOM4STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM4STOP'])       : 'disable');
$dvm_config_custom4_start      = trim(isset($dvm_config_cfg['CUSTOM4START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM4START'])      : 'disable');
$dvm_config_custom4_vmstop     = trim(isset($dvm_config_cfg['CUSTOM4VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM4VMSTOP'])     : 'disable');
$dvm_config_custom4_vmstart    = trim(isset($dvm_config_cfg['CUSTOM4VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM4VMSTART'])    : 'disable');

$dvm_config_custom5_interface  = trim(isset($dvm_config_cfg['CUSTOM5INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM5INTERFACE'])  : 'noiface');
$dvm_config_custom5_mode       = trim(isset($dvm_config_cfg['CUSTOM5MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM5MODE'])       : 'rx');
$dvm_config_custom5_time       = trim(isset($dvm_config_cfg['CUSTOM5TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM5TIME'])       : 'h');
$dvm_config_custom5_limit      = trim(isset($dvm_config_cfg['CUSTOM5LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM5LIMIT'])      : '-1');
$dvm_config_custom5_unit       = trim(isset($dvm_config_cfg['CUSTOM5UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM5UNIT'])       : 'GB');
$dvm_config_custom5_stop       = trim(isset($dvm_config_cfg['CUSTOM5STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM5STOP'])       : 'disable');
$dvm_config_custom5_start      = trim(isset($dvm_config_cfg['CUSTOM5START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM5START'])      : 'disable');
$dvm_config_custom5_vmstop     = trim(isset($dvm_config_cfg['CUSTOM5VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM5VMSTOP'])     : 'disable');
$dvm_config_custom5_vmstart    = trim(isset($dvm_config_cfg['CUSTOM5VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM5VMSTART'])    : 'disable');

$dvm_config_custom6_interface  = trim(isset($dvm_config_cfg['CUSTOM6INTERFACE'])  ? htmlspecialchars($dvm_config_cfg['CUSTOM6INTERFACE'])  : 'noiface');
$dvm_config_custom6_mode       = trim(isset($dvm_config_cfg['CUSTOM6MODE'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM6MODE'])       : 'rx');
$dvm_config_custom6_time       = trim(isset($dvm_config_cfg['CUSTOM6TIME'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM6TIME'])       : 'h');
$dvm_config_custom6_limit      = trim(isset($dvm_config_cfg['CUSTOM6LIMIT'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM6LIMIT'])      : '-1');
$dvm_config_custom6_unit       = trim(isset($dvm_config_cfg['CUSTOM6UNIT'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM6UNIT'])       : 'GB');
$dvm_config_custom6_stop       = trim(isset($dvm_config_cfg['CUSTOM6STOP'])       ? htmlspecialchars($dvm_config_cfg['CUSTOM6STOP'])       : 'disable');
$dvm_config_custom6_start      = trim(isset($dvm_config_cfg['CUSTOM6START'])      ? htmlspecialchars($dvm_config_cfg['CUSTOM6START'])      : 'disable');
$dvm_config_custom6_vmstop     = trim(isset($dvm_config_cfg['CUSTOM6VMSTOP'])     ? htmlspecialchars($dvm_config_cfg['CUSTOM6VMSTOP'])     : 'disable');
$dvm_config_custom6_vmstart    = trim(isset($dvm_config_cfg['CUSTOM6VMSTART'])    ? htmlspecialchars($dvm_config_cfg['CUSTOM6VMSTART'])    : 'disable');

$dvm_config_running = trim((string)shell_exec('/etc/rc.d/rc.vnstat status >/dev/null 2>&1; echo $?')) === '0';
$dvm_config_installed_backend = htmlspecialchars(trim(shell_exec("find /var/log/packages/ -type f -iname 'vnstat*' -printf '%f\n' 2> /dev/null")));

?>
