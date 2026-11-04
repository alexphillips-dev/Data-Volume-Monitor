<?
/* Copyright Derek Macias (parts of code from NUT package)
 * Copyright macester (parts of code from NUT package)
 * Copyright gfjardim (parts of code from NUT package)
 * Copyright SimonF (parts of code from NUT package)
 * Copyright Mohamed Emad (icon from vnstat-client package)
 * Copyright desertwitch
 * Modified 2026-11-04: Data Volume Monitor naming and repository transition.
 * Modified 2026-11-04: escape report labels and isolate generated image paths.
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
require_once __DIR__.'/dvm_config.php';
require_once __DIR__.'/dvm_threshold.php';
require_once __DIR__.'/dvm_report_escape.php';

function dvm_humanFileSize($sizeObj,$unit="") {
    try {
        $size = intval($sizeObj);
        if($size) {
            if( (!$unit && $size >= 1000000000000) || $unit == "TB")
                return number_format(($size/1000000000000),2) . " TB";
            if( (!$unit && $size >= 1000000000) || $unit == "GB")
                return number_format(($size/1000000000),2) . " GB";
            if( (!$unit && $size >= 1000000) || $unit == "MB")
                return number_format(($size/1000000),2) . " MB";
            if( (!$unit && $size >= 1000) || $unit == "KB")
                return number_format(($size/1000),2) . " KB";
            return number_format($size) . " B";
        } else {
            return "-";
        }
    } catch (\Throwable $t) {
        return "-";
    } catch (\Exception $e) {
        return "-";
    }
}

function dvm_getVirtualInterfaceServiceMatches() {
    try {
        $matches_raw = shell_exec("/usr/local/emhttp/plugins/dvm/scripts/match_virts 2>/dev/null");
        if($matches_raw) {
            $returnArr = [];
            foreach(preg_split("/\r?\n/", rtrim($matches_raw, "\r\n")) as $match) {
                $submatch = explode(":", $match, 2);
                if(count($submatch) === 2 && $submatch[0] !== '' && $submatch[1] !== '') {
                    if(!empty($returnArr[$submatch[0]])) {
                        $returnArr[$submatch[0]] = $returnArr[$submatch[0]] . " <span>" . dvm_report_html($submatch[1]) . "</span>";
                    } else {
                        $returnArr[$submatch[0]] = "<span>" . dvm_report_html($submatch[1]) . "</span>";
                    }
                } else {
                    continue;
                }
            }
            return $returnArr;
        } else {
            return false;
        }
    } catch (\Throwable $t) {
        error_log($t);
        return false;
    } catch (\Exception $e) {
        error_log($e);
        return false;
    }
}

function dvm_isPhysicalInterface($string) {
    try {
        $phys_ifaces = shell_exec("find /sys/class/net/ -type l ! -lname '*/devices/virtual/net/*' 2>/dev/null");
        $existing_ifaces = shell_exec("find /sys/class/net/ -type l 2>/dev/null");

        if($phys_ifaces && $existing_ifaces) {

            $phys_ifaces_array = explode(PHP_EOL, trim($phys_ifaces));
            $existing_ifaces_array = explode(PHP_EOL, trim($existing_ifaces));

            if(substr($string, 0, 4) == "veth") { return false; }
            if(!in_array("/sys/class/net/" . $string, $existing_ifaces_array)) {
                return true; // keep removed interfaces for later removal
            }

            return in_array("/sys/class/net/" . $string, $phys_ifaces_array);
        } else {
            return true;
        }
    } catch (\Throwable $t) {
        error_log($t);
        return true;
    } catch (\Exception $e) {
        error_log($e);
        return true;
    }
}

function dvm_isExistingInterface($string) {
    try {
        $existing_ifaces = shell_exec("find /sys/class/net/ -type l 2>/dev/null");
        if($existing_ifaces) {
            $existing_ifaces_array = explode(PHP_EOL, trim($existing_ifaces));
            return in_array("/sys/class/net/" . $string, $existing_ifaces_array);
        } else {
            return true;
        }
    } catch (\Throwable $t) {
        error_log($t);
        return true;
    } catch (\Exception $e) {
        error_log($e);
        return true;
    }
}

// Availability describes the data queries in one response, independently of
// threshold decisions. A partial measurement failure makes the whole batch stale.
function dvm_report_query_failed()
{
    $GLOBALS['dvm_report_data_available'] = false;
    return false;
}

function dvm_report_read_query($command)
{
    $lines = [];
    $status = 1;
    exec($command, $lines, $status);
    if ($status !== 0) {
        throw new \RuntimeException('Network statistics query failed.');
    }
    return implode("\n", $lines);
}

function dvm_report_render_query($command, $expectsText = false)
{
    try {
        $result = dvm_report_read_query($command);
        if ($expectsText && trim($result) === '') {
            throw new \RuntimeException('Network statistics query returned no data.');
        }
        return $result;
    } catch (\Throwable $error) {
        dvm_report_query_failed();
        error_log($error->getMessage());
        return $expectsText ? 'Network statistics data is unavailable.' : '';
    }
}

function dvm_getInterfaces()
{
    global $dvm_config_vifaces;
    global $dvm_config_oifaces;

    $db_ifaces_array = "";
    try {
        $db_ifaces_raw = dvm_report_read_query("vnstat --config /etc/vnstat/vnstat.conf --dbiflist 2>/dev/null");
        if($db_ifaces_raw) {
            $db_ifaces_regex = '/Interfaces in database\: (.*)/';
            if (!preg_match($db_ifaces_regex, $db_ifaces_raw, $db_ifaces_matches)
                || trim($db_ifaces_matches[1]) === '') {
                return dvm_report_query_failed();
            }
            $db_ifaces_array = preg_split('/\s+/', trim($db_ifaces_matches[1]));
            if ($dvm_config_vifaces !== "enable") { $db_ifaces_array = array_filter($db_ifaces_array, 'dvm_isPhysicalInterface'); }
            if ($dvm_config_oifaces !== "enable") { $db_ifaces_array = array_filter($db_ifaces_array, 'dvm_isExistingInterface'); }
        } else {
            return dvm_report_query_failed();
        }
    } catch (\Throwable $t) {
        error_log($t);
        return dvm_report_query_failed();
    } catch (\Exception $e) {
        error_log($e);
        return dvm_report_query_failed();
    }
    return $db_ifaces_array;
}

function dvm_getXMLforInterface($iface)
{
    $xml = "";
    $iface = trim($iface);

    try {
        if(!empty($iface) && $iface !== "noiface") {
            $xml_raw = dvm_report_read_query("vnstat --config /etc/vnstat/vnstat.conf -i ". escapeshellarg($iface) ." --limit 1 --xml 2>/dev/null");
            if($xml_raw) {
                if(strpos($xml_raw, "xmlversion") !== false) {
                    $xml = new SimpleXMLElement($xml_raw);
                    if (!isset($xml->interface[0]->traffic[0])) {
                        return dvm_report_query_failed();
                    }
                } else {
                    return dvm_report_query_failed();
                }
            } else {
                return dvm_report_query_failed();
            }
        } else {
            return dvm_report_query_failed();
        }
    } catch (\Throwable $t) {
        error_log($t);
        return dvm_report_query_failed();
    } catch (\Exception $e) {
        error_log($e);
        return dvm_report_query_failed();
    }
    return $xml;
}

function dvm_checkAgainstLimits($iface, $time, $limit, $unit, $mode, $str)
{
    $state = dvm_threshold_evaluate($iface, $time, $limit, $unit, $mode);
    switch ($state) {
        case 'disabled':
            return $str;
        case 'exceeded':
            return "<span class='red-text'>$str</span>";
        case 'normal':
            return "<span class='green-text'>$str</span>";
        default:
            return "<span class='dvm-threshold-error' title='Threshold status unavailable'>$str <i class='fa fa-exclamation-triangle'></i></span>";
    }
}

function dvm_get_primary_metrics()
{
    global $dvm_config_primary;
    global $dvm_config_hlimit_rx;
    global $dvm_config_hunit_rx;
    global $dvm_config_dlimit_rx;
    global $dvm_config_dunit_rx;
    global $dvm_config_mlimit_rx;
    global $dvm_config_munit_rx;
    global $dvm_config_ylimit_rx;
    global $dvm_config_yunit_rx;
    global $dvm_config_hlimit_tx;
    global $dvm_config_hunit_tx;
    global $dvm_config_dlimit_tx;
    global $dvm_config_dunit_tx;
    global $dvm_config_mlimit_tx;
    global $dvm_config_munit_tx;
    global $dvm_config_ylimit_tx;
    global $dvm_config_yunit_tx;

    $trafficTotal = [];
    $xml = dvm_getXMLforInterface($dvm_config_primary);

    if($xml) {
        $trafficTotal[0][0] = dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->rx ?? 0);
        $trafficTotal[0][1] = dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->tx ?? 0);

        $trafficTotal[1][0] = dvm_checkAgainstLimits($dvm_config_primary, "h", $dvm_config_hlimit_rx, $dvm_config_hunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->rx ?? 0));
        $trafficTotal[1][1] = dvm_checkAgainstLimits($dvm_config_primary, "h", $dvm_config_hlimit_tx, $dvm_config_hunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->tx ?? 0));

        $trafficTotal[2][0] = dvm_checkAgainstLimits($dvm_config_primary, "d", $dvm_config_dlimit_rx, $dvm_config_dunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->rx ?? 0));
        $trafficTotal[2][1] = dvm_checkAgainstLimits($dvm_config_primary, "d", $dvm_config_dlimit_tx, $dvm_config_dunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->tx ?? 0));

        $trafficTotal[3][0] = dvm_checkAgainstLimits($dvm_config_primary, "m", $dvm_config_mlimit_rx, $dvm_config_munit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->rx ?? 0));
        $trafficTotal[3][1] = dvm_checkAgainstLimits($dvm_config_primary, "m", $dvm_config_mlimit_tx, $dvm_config_munit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->tx ?? 0));

        $trafficTotal[4][0] = dvm_checkAgainstLimits($dvm_config_primary, "y", $dvm_config_ylimit_rx, $dvm_config_yunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->rx ?? 0));
        $trafficTotal[4][1] = dvm_checkAgainstLimits($dvm_config_primary, "y", $dvm_config_ylimit_tx, $dvm_config_yunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->tx ?? 0));
    } else {
        return false;
    }
    return $trafficTotal;
}

function dvm_build_report()
{
    global $dvm_config_report;
    global $dvm_config_vifaces;
    global $dvm_config_primary;
    global $dvm_config_match_virts;

    $returnStr = "";
    $db_ifaces_array = dvm_getInterfaces();

    $virt_iface_matches = false;
    if($dvm_config_match_virts == "enable") {
        $virt_iface_matches = dvm_getVirtualInterfaceServiceMatches();
    }

    if($db_ifaces_array) {
        foreach($db_ifaces_array as $db_iface) {
            $matchedService = "";
            if($virt_iface_matches) {
                $matchedService = $virt_iface_matches[$db_iface] ?? false;
                if($matchedService) {
                    $matchedService = "<span style='font-size:x-small;color:gray;'> {$matchedService}</span>";
                }
            }
            if ($dvm_config_report == "both") {
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -s -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "s")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -5 -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "5")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -h -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "h")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -d -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "d")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -m -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "m")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -y -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "y")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");

                if($db_iface == $dvm_config_primary) {
                    if(count($db_ifaces_array) > 1) {
                        $returnStr .= "<tr style='border:2px solid;'>";
                    } else {
                        $returnStr .= "<tr>";
                    }
                } else {
                    $returnStr .= "<tr>";
                }
                $returnStr .= "<td>". dvm_report_html($db_iface) . $matchedService . "</td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "s")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -s -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "5")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -5 -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "h")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -h -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "d")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -d -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "m")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -m -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "y")) ."'><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -y -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "</tr>";
            } else if ($dvm_config_report == "images") {
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -s -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "s")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -5 -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "5")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -h -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "h")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -d -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "d")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -m -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "m")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");
                dvm_report_render_query("vnstati --config /etc/vnstat/vnstat.conf -y -c 1 -o ". escapeshellarg(dvm_report_image_path($db_iface, "y")) ." -i ". escapeshellarg($db_iface) ." 2>/dev/null");

                if($db_iface == $dvm_config_primary) {
                    if(count($db_ifaces_array) > 1) {
                        $returnStr .= "<tr style='border:2px solid;'>";
                    } else {
                        $returnStr .= "<tr>";
                    }
                } else {
                    $returnStr .= "<tr>";
                }
                $returnStr .= "<td>". dvm_report_html($db_iface) . $matchedService . "</td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "s")) ."'></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "5")) ."'></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "h")) ."'></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "d")) ."'></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "m")) ."'></details></td>";
                $returnStr .= "<td><details><summary>...</summary><img src='". dvm_report_html(dvm_report_image_url($db_iface, "y")) ."'></details></td>";
                $returnStr .= "</tr>";
            } else {
                if($db_iface == $dvm_config_primary) {
                    if(count($db_ifaces_array) > 1) {
                        $returnStr .= "<tr style='border:2px solid;'>";
                    } else {
                        $returnStr .= "<tr>";
                    }
                } else {
                    $returnStr .= "<tr>";
                }
                $returnStr .= "<td>". dvm_report_html($db_iface) . $matchedService . "</td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -s -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -5 -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -h -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -d -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -m -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "<td><details><summary>...</summary><pre style='font-size:x-small;'>".dvm_report_html(dvm_report_render_query("vnstat --config /etc/vnstat/vnstat.conf -y -i ". escapeshellarg($db_iface) ." 2>/dev/null", true))."</pre></details></td>";
                $returnStr .= "</tr>";
            }
        }
    } else {
        $returnStr .= "<tr>";
        $returnStr .= "<td colspan='7'><em>Error Occured While Querying Network Interfaces</em></td>";
        $returnStr .= "</tr>";
    }
    return $returnStr;
}

function dvm_build_report_light()
{
    global $dvm_config_hlimit_rx;
    global $dvm_config_hunit_rx;
    global $dvm_config_dlimit_rx;
    global $dvm_config_dunit_rx;
    global $dvm_config_mlimit_rx;
    global $dvm_config_munit_rx;
    global $dvm_config_ylimit_rx;
    global $dvm_config_yunit_rx;
    global $dvm_config_hlimit_tx;
    global $dvm_config_hunit_tx;
    global $dvm_config_dlimit_tx;
    global $dvm_config_dunit_tx;
    global $dvm_config_mlimit_tx;
    global $dvm_config_munit_tx;
    global $dvm_config_ylimit_tx;
    global $dvm_config_yunit_tx;
    global $dvm_config_primary;

    global $dvm_config_custom1_interface;
    global $dvm_config_custom1_mode;
    global $dvm_config_custom1_time;
    global $dvm_config_custom1_limit;
    global $dvm_config_custom1_unit;
    global $dvm_config_custom2_interface;
    global $dvm_config_custom2_mode;
    global $dvm_config_custom2_time;
    global $dvm_config_custom2_limit;
    global $dvm_config_custom2_unit;
    global $dvm_config_custom3_interface;
    global $dvm_config_custom3_mode;
    global $dvm_config_custom3_time;
    global $dvm_config_custom3_limit;
    global $dvm_config_custom3_unit;
    global $dvm_config_custom4_interface;
    global $dvm_config_custom4_mode;
    global $dvm_config_custom4_time;
    global $dvm_config_custom4_limit;
    global $dvm_config_custom4_unit;
    global $dvm_config_custom5_interface;
    global $dvm_config_custom5_mode;
    global $dvm_config_custom5_time;
    global $dvm_config_custom5_limit;
    global $dvm_config_custom5_unit;
    global $dvm_config_custom6_interface;
    global $dvm_config_custom6_mode;
    global $dvm_config_custom6_time;
    global $dvm_config_custom6_limit;
    global $dvm_config_custom6_unit;

    global $dvm_config_vifaces;
    global $dvm_config_match_virts;

    $custom_iface_string = "{$dvm_config_custom1_interface};{$dvm_config_custom2_interface};{$dvm_config_custom3_interface};{$dvm_config_custom4_interface};{$dvm_config_custom5_interface};{$dvm_config_custom6_interface}";
    $custom_iface_array = explode(";", trim($custom_iface_string)) ?? [];

    $virt_iface_matches = false;
    if($dvm_config_vifaces == "enable" && $dvm_config_match_virts == "enable") {
        $virt_iface_matches = dvm_getVirtualInterfaceServiceMatches();
    }

    $returnStr = "";
    $db_ifaces_array = dvm_getInterfaces();

    if($db_ifaces_array) {
        foreach($db_ifaces_array as $db_iface) {
            $xml = dvm_getXMLforInterface($db_iface);

            if($xml) {
                if($db_iface == $dvm_config_primary) {
                    $tmpStr = "";

                    $tmpStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->rx ?? 0) . "</td>";
                    $tmpStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->tx ?? 0) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "h", $dvm_config_hlimit_rx, $dvm_config_hunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->rx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "h", $dvm_config_hlimit_tx, $dvm_config_hunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->tx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "d", $dvm_config_dlimit_rx, $dvm_config_dunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->rx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "d", $dvm_config_dlimit_tx, $dvm_config_dunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->tx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "m", $dvm_config_mlimit_rx, $dvm_config_munit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->rx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "m", $dvm_config_mlimit_tx, $dvm_config_munit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->tx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "y", $dvm_config_ylimit_rx, $dvm_config_yunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->rx ?? 0)) . "</td>";
                    $tmpStr .= "<td>". dvm_checkAgainstLimits($db_iface, "y", $dvm_config_ylimit_tx, $dvm_config_yunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->tx ?? 0)) . "</td>";

                    if(count($db_ifaces_array) > 1) {
                        $returnStr .= "<tr style='border:2px solid;'>";
                    } else {
                        $returnStr .= "<tr>";
                    }

                    if(dvm_isExistingInterface($db_iface)) {
                        $matchedService = "";
                        if($virt_iface_matches) {
                            $matchedService = $virt_iface_matches[$db_iface] ?? false;
                            if($matchedService) {
                                $matchedService = "<span style='font-size:x-small;color:gray;'> {$matchedService}</span>";
                            }
                        }
                        if ( strpos ( $tmpStr , "red-text" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle red-orb' title='Monitored - Limits Exceeded'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        } else if ( strpos ( $tmpStr , "dvm-threshold-error" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-exclamation-triangle' title='Threshold status unavailable'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        } else if ( strpos ( $tmpStr , "green-text" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle green-orb' title='Monitored - Limits Not Exceeded'></i>" . dvm_report_html($db_iface) .  $matchedService . "</td>";
                        } else {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle dvm-gray-orb' title='Monitored - No Limits'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        }
                    } else {
                        $returnStr .= "<td><i class='dvmorbiconactive fa fa-low-vision' title='Removed or Inactive Interface'></i>" . dvm_report_html($db_iface) . "</td>";
                    }
                    $returnStr .= $tmpStr;
                    $returnStr .= "</tr>";
                } else if (in_array($db_iface,$custom_iface_array)) {
                    $tmpStr = "";
                    $tmpStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->rx ?? 0) . "</td>";
                    $tmpStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->tx ?? 0) . "</td>";
                    foreach (['h' => ['hours', 'hour'], 'd' => ['days', 'day'],
                              'm' => ['months', 'month'], 'y' => ['years', 'year']] as $time => $nodes) {
                        foreach (['rx', 'tx'] as $mode) {
                            $value = dvm_humanFileSize($xml->interface[0]->traffic[0]->{$nodes[0]}[0]->{$nodes[1]}[0]->{$mode} ?? 0);
                            $tmpStr .= "<td>".dvm_checkCustomLimits($db_iface, $time, $mode, $value)."</td>";
                        }
                    }

                    $returnStr .= "<tr>";

                    if(dvm_isExistingInterface($db_iface)) {
                        $matchedService = "";
                        if($virt_iface_matches) {
                            $matchedService = $virt_iface_matches[$db_iface] ?? false;
                            if($matchedService) {
                                $matchedService = "<span style='font-size:x-small;color:gray;'> {$matchedService}</span>";
                            }
                        }
                        if ( strpos ( $tmpStr , "red-text" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle red-orb' title='Monitored - Limits Exceeded'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        } else if ( strpos ( $tmpStr , "dvm-threshold-error" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-exclamation-triangle' title='Threshold status unavailable'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        } else if ( strpos ( $tmpStr , "green-text" ) !== false ) {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle green-orb' title='Monitored - Limits Not Exceeded'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        } else {
                            $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle dvm-gray-orb' title='Monitored - No Limits'></i>" . dvm_report_html($db_iface) . $matchedService . "</td>";
                        }
                    } else {
                        $returnStr .= "<td><i class='dvmorbiconactive fa fa-low-vision' title='Removed or Inactive Interface'></i>" . dvm_report_html($db_iface) . "</td>";
                    }
                    $returnStr .= $tmpStr;
                    $returnStr .= "</tr>";
                } else {
                    $returnStr .= "<tr>";

                    if(dvm_isExistingInterface($db_iface)) {
                        $matchedService = "";
                        if($virt_iface_matches) {
                            $matchedService = $virt_iface_matches[$db_iface] ?? false;
                            if($matchedService) {
                                $matchedService = "<span style='font-size:x-small;color:gray;'> {$matchedService}</span>";
                            }
                        }
                        $returnStr .= "<td><i class='dvmorbiconactive fa fa-circle dvm-gray-orb' title='Monitored - No Limits'></i>". dvm_report_html($db_iface) . $matchedService . "</td>";
                    } else {
                        $returnStr .= "<td><i class='dvmorbiconactive fa fa-low-vision' title='Removed or Inactive Interface'></i>" . dvm_report_html($db_iface) . "</td>";
                    }
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->rx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->tx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->rx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->tx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->rx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->tx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->rx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->tx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->rx ?? 0) . "</td>";
                    $returnStr .= "<td>". dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->tx ?? 0) . "</td>";
                    $returnStr .= "</tr>";
                }
            } else {
                $returnStr .= "<tr>";
                $returnStr .= "<td>". dvm_report_html($db_iface) . "</td>";
                $returnStr .= "<td colspan='10'><i class='dvmorbiconactive fa fa-exclamation-circle' title='Removed or Inactive Interface'></i><em>Error Occured While Querying Network Interface</em></td>";
                $returnStr .= "</tr>";
            }
        }
    } else {
        $returnStr .= "<tr>";
        $returnStr .= "<td colspan='11'><em>Error Occured While Querying Network Interfaces</em></td>";
        $returnStr .= "</tr>";
    }
    return $returnStr;
}

function dvm_checkCustomLimits($iface, $time, $mode, $str)
{
    $normal = $str;
    $unknown = null;
    for ($i = 1; $i <= 6; $i++) {
        $prefix = 'dvm_config_custom'.$i.'_';
        if (($GLOBALS[$prefix.'interface'] ?? null) !== $iface
            || ($GLOBALS[$prefix.'time'] ?? null) !== $time
            || ($GLOBALS[$prefix.'mode'] ?? null) !== $mode) {
            continue;
        }
        $result = dvm_checkAgainstLimits($iface, $time, $GLOBALS[$prefix.'limit'], $GLOBALS[$prefix.'unit'], $mode, $str);
        if (strpos($result, 'red-text') !== false) return $result;
        if (strpos($result, 'dvm-threshold-error') !== false) $unknown = $result;
        if (strpos($result, 'green-text') !== false) $normal = $result;
    }
    return $unknown ?? $normal;
}

function dvm_build_dashboard() {
    $returnStr = "";
    $dvm_metrics = [];

    $dvm_5 = [];
    $dvm_h = [];
    $dvm_d = [];
    $dvm_m = [];
    $dvm_y = [];

    $dvm_metrics = dvm_get_primary_metrics();

    if($dvm_metrics) {
        $dvm_5 = $dvm_metrics[0];
        $dvm_h = $dvm_metrics[1];
        $dvm_d = $dvm_metrics[2];
        $dvm_m = $dvm_metrics[3];
        $dvm_y = $dvm_metrics[4];

        $returnStr .= "{$dvm_5[0]};{$dvm_5[1]};{$dvm_h[0]};{$dvm_h[1]};{$dvm_d[0]};{$dvm_d[1]};{$dvm_m[0]};{$dvm_m[1]};{$dvm_y[0]};{$dvm_y[1]}";
    } else {
        $returnStr .= "<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>;<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>";
    }
    return $returnStr;
}

function dvm_build_footer()
{
    global $dvm_config_hlimit_rx;
    global $dvm_config_hunit_rx;
    global $dvm_config_dlimit_rx;
    global $dvm_config_dunit_rx;
    global $dvm_config_mlimit_rx;
    global $dvm_config_munit_rx;
    global $dvm_config_ylimit_rx;
    global $dvm_config_yunit_rx;
    global $dvm_config_hlimit_tx;
    global $dvm_config_hunit_tx;
    global $dvm_config_dlimit_tx;
    global $dvm_config_dunit_tx;
    global $dvm_config_mlimit_tx;
    global $dvm_config_munit_tx;
    global $dvm_config_ylimit_tx;
    global $dvm_config_yunit_tx;
    global $dvm_config_primary;
    global $dvm_config_footerformat;

    $xml = dvm_getXMLforInterface($dvm_config_primary);

    if($xml) {
        switch ($dvm_config_footerformat) {
            case '5':
                $trafficRx = dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->rx ?? 0);
                $trafficTx = dvm_humanFileSize($xml->interface[0]->traffic[0]->fiveminutes[0]->fiveminute[0]->tx ?? 0);
                break;
            case 'h':
                $trafficRx = dvm_checkAgainstLimits($dvm_config_primary, "h", $dvm_config_hlimit_rx, $dvm_config_hunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->rx ?? 0));
                $trafficTx = dvm_checkAgainstLimits($dvm_config_primary, "h", $dvm_config_hlimit_tx, $dvm_config_hunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->hours[0]->hour[0]->tx ?? 0));
                break;
            case 'd':
                $trafficRx = dvm_checkAgainstLimits($dvm_config_primary, "d", $dvm_config_dlimit_rx, $dvm_config_dunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->rx ?? 0));
                $trafficTx = dvm_checkAgainstLimits($dvm_config_primary, "d", $dvm_config_dlimit_tx, $dvm_config_dunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->days[0]->day[0]->tx ?? 0));
                break;
            case 'm':
                $trafficRx = dvm_checkAgainstLimits($dvm_config_primary, "m", $dvm_config_mlimit_rx, $dvm_config_munit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->rx ?? 0));
                $trafficTx = dvm_checkAgainstLimits($dvm_config_primary, "m", $dvm_config_mlimit_tx, $dvm_config_munit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->months[0]->month[0]->tx ?? 0));
                break;
            case 'y':
                $trafficRx = dvm_checkAgainstLimits($dvm_config_primary, "y", $dvm_config_ylimit_rx, $dvm_config_yunit_rx, "rx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->rx ?? 0));
                $trafficTx = dvm_checkAgainstLimits($dvm_config_primary, "y", $dvm_config_ylimit_tx, $dvm_config_yunit_tx, "tx", dvm_humanFileSize($xml->interface[0]->traffic[0]->years[0]->year[0]->tx ?? 0));
                break;
        }
    } else {
        $trafficRx = "<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>";
        $trafficTx = "<i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>";
    }
    return("<i class='fa fa-arrow-down'></i> " . $trafficRx . " <i class='fa fa-arrow-up'></i> " . $trafficTx);
}

function dvm_build_dashboard_mini() {
    global $dvm_config_primary;
    global $dvm_config_footerformat;

    $returnStr = "";
    $dvm_mini_descr = "";

    $dvm_mini = dvm_build_footer();

    if($dvm_mini) {
        switch ($dvm_config_footerformat) {
            case '5':
                $dvm_mini_descr = "Last 5 Minutes:";
                break;
            case 'h':
                $dvm_mini_descr = "Last Hour:";
                break;
            case 'd':
                $dvm_mini_descr = "Last Day:";
                break;
            case 'm':
                $dvm_mini_descr = "Last Month:";
                break;
            case 'y':
                $dvm_mini_descr = "Last Year:";
                break;
        }
        $returnStr .= "$dvm_config_primary / $dvm_mini_descr $dvm_mini";
    } else {
        $returnStr = "$dvm_config_primary / $dvm_mini_descr / <i class='fa fa-times dvm-threshold-error' title='Error Querying Network Interface - Missing or Misspelled Primary Interface?'></i>";
    }
    return $returnStr;
}

if(!empty($_GET["mode"])) {
    try {
        $dvm_retarr = [];
        $dvm_report_data_available = true;
        switch($_GET["mode"]) {
            case "report":
                $dvm_funcout = dvm_build_report();
                if($dvm_funcout) {
                    $dvm_retarr["success"]["response"] = $dvm_funcout;
                } else {
                    $dvm_retarr["error"]["response"] = "Falsy dvm_build_report() function response!";
                }
                break;
            case "lightreport":
                $dvm_funcout = dvm_build_report_light();
                if($dvm_funcout) {
                    $dvm_retarr["success"]["response"] = $dvm_funcout;
                } else {
                    $dvm_retarr["error"]["response"] = "Falsy dvm_build_report_light() function response!";
                }
                break;
            case "footer":
                $dvm_funcout = dvm_build_footer();
                if($dvm_funcout) {
                    $dvm_retarr["success"]["response"] = $dvm_funcout;
                } else {
                    $dvm_retarr["error"]["response"] = "Falsy dvm_build_footer() function response!";
                }
                break;
            case "dashboard":
                $dvm_funcout = dvm_build_dashboard();
                if($dvm_funcout) {
                    $dvm_retarr["success"]["response"] = $dvm_funcout;
                } else {
                    $dvm_retarr["error"]["response"] = "Falsy dvm_build_dashboard() function response!";
                }
                break;
            case "dashboardmini":
                $dvm_funcout = dvm_build_dashboard_mini();
                if($dvm_funcout) {
                    $dvm_retarr["success"]["response"] = $dvm_funcout;
                } else {
                    $dvm_retarr["error"]["response"] = "Falsy dvm_build_dashboard_mini() function response!";
                }
                break;
            default:
                $dvm_retarr["error"]["response"] = "Invalid GET parameters";
                break;
        }
        if (isset($dvm_retarr["success"])) {
            $dvm_retarr["success"]["dataAvailable"] = $dvm_report_data_available;
        }
    }
    catch (\Throwable $t) {
        error_log($t);
        $dvm_retarr = [];
        $dvm_retarr["error"]["response"] = $t->getMessage();
    }
    catch (\Exception $e) {
        error_log($e);
        $dvm_retarr = [];
        $dvm_retarr["error"]["response"] = $e->getMessage();
    }
    echo(json_encode($dvm_retarr));
}
?>
