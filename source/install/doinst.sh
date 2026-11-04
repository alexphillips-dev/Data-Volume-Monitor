#!/bin/bash
set -e
#
# Copyright Derek Macias (parts of code from NUT package)
# Copyright macester (parts of code from NUT package)
# Copyright gfjardim (parts of code from NUT package)
# Copyright SimonF (parts of code from NUT package)
# Copyright Mohamed Emad (icon from vnstat-client package)
# Copyright desertwitch
# Modified 2026-11-04: Data Volume Monitor naming and repository transition.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License 2
# as published by the Free Software Foundation.
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
BOOT="/boot/config/plugins/dvm"
DOCROOT="/usr/local/emhttp/plugins/dvm"

# Update file permissions of scripts
chmod 755 $DOCROOT/scripts/*
chmod 755 /etc/rc.d/rc.vnstat
chmod 755 /usr/sbin/dvm-notify

# copy the default GUI configuration
mkdir -p "$BOOT"
cp -n $DOCROOT/default.cfg $BOOT/dvm.cfg >/dev/null 2>&1

# create DVM configuration directory
if [ ! -d /etc/vnstat ]; then
    mkdir /etc/vnstat
fi

# prepare conf backup directory on flash drive, if it does not already exist
if [ ! -d $BOOT/vnstat ]; then
    mkdir $BOOT/vnstat
fi

# copy default conf files to flash drive, if no backups exist there
for config_file in vnstat.conf dvm-custom-alarms.sh dvm-user-actions.sh; do
    cp -n "$DOCROOT/vnstat/$config_file" "$BOOT/vnstat/$config_file"
done

# copy conf files from flash drive to local system, for our services to use
for config_file in "$BOOT"/vnstat/*.conf "$BOOT"/vnstat/*.sh; do
    [ -f "$config_file" ] && [ ! -L "$config_file" ] || continue
    cp -f -- "$config_file" "/etc/vnstat/${config_file##*/}"
done

# link default configuration location to actual configuration location for binaries to use
if [ ! -L /etc/vnstat.conf ]; then
    ln -sf /etc/vnstat/vnstat.conf /etc/vnstat.conf
fi

# remove (legacy) plugin-specific polling tasks
rm -f /etc/cron.daily/dvm-poller >/dev/null 2>&1

# set up permissions
if [ -d /etc/vnstat ]; then
    echo "Updating permissions for DVM..."
    chown root:root /etc/vnstat
    chmod 755 /etc/vnstat
    chown root:root /etc/vnstat/*
    chmod 644 /etc/vnstat/*
    chmod 755 /etc/vnstat/dvm-custom-alarms.sh
    chmod 755 /etc/vnstat/dvm-user-actions.sh
fi
