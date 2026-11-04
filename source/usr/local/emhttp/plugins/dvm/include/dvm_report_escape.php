<?php
// Copyright 2026 alexphillips-dev. Licensed under GPL-2.0.

// Only raw backend labels/text enter this helper; generated report markup does not.
function dvm_report_html($text)
{
    return htmlspecialchars((string)$text, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

function dvm_report_image_name($iface, $period)
{
    if (!in_array($period, ['s', '5', 'h', 'd', 'm', 'y'], true)) {
        throw new InvalidArgumentException('Invalid report image period.');
    }
    // A safe filename keeps arbitrary backend identifiers out of filesystem paths
    // and URLs. The original interface is still passed separately to vnStat.
    return 'dvm-'.hash('sha256', (string)$iface).'_'.$period.'.png';
}

function dvm_report_image_path($iface, $period)
{
    return '/usr/local/emhttp/plugins/dvm/images/'.dvm_report_image_name($iface, $period);
}

function dvm_report_image_url($iface, $period)
{
    return '/plugins/dvm/images/'.dvm_report_image_name($iface, $period);
}
