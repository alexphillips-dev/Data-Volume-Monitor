# Data Volume Monitor

<img src="plugin/dvm.png" alt="Data Volume Monitor icon" width="32" height="32">

Data Volume Monitor is an Unraid plugin for tracking network data usage with
[vnStat](https://humdi.net/vnstat/). It displays interface traffic in the Unraid
web UI and can send notifications, control selected Docker containers, change
VM network links, or run custom functions when configured limits change state.

Maintained by [alexphillips-dev](https://github.com/alexphillips-dev).

- [Development branch](https://github.com/alexphillips-dev/Data-Volume-Monitor/tree/dev)
- [User and maintainer wiki](https://github.com/alexphillips-dev/Data-Volume-Monitor/wiki)
- [Report an issue](https://github.com/alexphillips-dev/Data-Volume-Monitor/issues)
- [vnStat documentation](https://humdi.net/vnstat/)
- [vnStat source](https://github.com/vergoh/vnstat)

## Contents

- [Features](#features)
- [Requirements and release channels](#requirements-and-release-channels)
- [Installation and updates](#installation-and-updates)
- [Switching release channels](#switching-release-channels)
- [First-time setup](#first-time-setup)
- [Thresholds, notifications, and actions](#thresholds-notifications-and-actions)
- [Displays and filters](#displays-and-filters)
- [Custom scripts and configuration editor](#custom-scripts-and-configuration-editor)
- [Storage, backups, and recovery](#storage-backups-and-recovery)
- [Migration from the original plugin](#migration-from-the-original-plugin)
- [Reset, purge, and uninstall](#reset-purge-and-uninstall)
- [Troubleshooting and support](#troubleshooting-and-support)
- [Development and testing](#development-and-testing)
- [Host acceptance](#host-acceptance)
- [License](#license)

## Features

- Traffic tables for available network interfaces, with inbound and outbound
  figures for five-minute, hourly, daily, monthly, and yearly periods.
- Text, image, or combined reports, plus optional dashboard and footer displays.
- A primary interface with separate RX/TX limits for hour, day, month, and year.
- Six secondary threshold slots, each selecting an interface, period, direction,
  limit, and associated actions. Multiple slots may monitor the same interface.
- Notifications for exceeded limits and transitions back to normal.
- Docker stop/start and VM network disconnect/reconnect actions.
- User-defined functions for threshold transitions and a separately scheduled
  custom alarm script.
- Optional matching of virtual interfaces to Docker containers and VMs.
- Interface/service filters and manual or automatic removal of obsolete
  interface records.
- Optional database persistence across normal reboots, including custom vnStat
  database locations.

Traffic belongs to a network interface. Container and VM matching supplies labels
for those interfaces; it does not create separate per-application accounting.
Virtual interfaces can disappear or change when workloads restart, and traffic
direction can appear reversed at different points in the network stack.

## Requirements and release channels

The manifest declares Unraid **6.8.3 or newer** and the bundled packages target
**x86_64**. The dependency archive contains vnStat **2.14**, including `vnstat`,
`vnstatd`, and `vnstati`. The dependency targets baseline x86_64 and glibc 2.17
or later, links to SQLite's `libsqlite3.so.0`, and requires `libgd.so.3` for image
output. Host libraries are not replaced by this package. These are build/package
requirements, not a claim that every Unraid release has been tested.

The plugin has two release channels: **Stable** (`main`) and **Development**
(`dev`). Both use the same plugin identity, `dvm`, and the same settings and
database locations. The settings page shows the installed version and channel
from packaged release metadata. An older package without that metadata displays
an unknown release rather than guessing its channel.

The first stable release is [2026.11.04.11](https://github.com/alexphillips-dev/Data-Volume-Monitor/releases/tag/2026.11.04.11).
Use Stable for the published release or Development to test subsequent changes.
Development builds may change; keep independent backups before testing them.
Automated coverage includes the bundled vnStat
binary and isolated filesystem/process fixtures. Live Unraid installation,
native page/theme behavior, real Docker/libvirt actions, and reboot restoration
remain separate host-acceptance checks.

Do not install alongside the original Data Volume Monitor identity (`dwdvm`) or
Network Stats. The installer checks those plugins because they share vnStat
service/database ownership. Follow the migration procedure before replacing an
existing installation.

## Installation and updates

In Unraid, open **Plugins → Install Plugin** and enter the manifest for the
chosen channel:

| Channel | Install/update manifest |
| --- | --- |
| Stable | `https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/main/plugin/dvm.plg` |
| Development | `https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/dev/plugin/dvm.plg` |

Stable manifest:

```text
https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/main/plugin/dvm.plg
```

Each manifest downloads its dependency and plugin archive from its own channel
and keeps that channel's URL for future update checks. The installer verifies
declared MD5 checksums. Plugin and backend archives also have SHA-256 sidecars
in the repository. Checksums identify the corresponding file; they are not
digital release signatures.

After installation, open **Data Volume Monitor** from the Unraid settings UI.
The route is `/Settings/DVMsettings`. Use the Unraid Plugins page to check for
updates. A Development installation stays on `dev`; a Stable installation stays
on `main`. Publishing another branch does not silently move an installed plugin
between channels.

Publishing an update to `dev` does not promote it to `main` or create a stable
GitHub release.

## Switching release channels

Change channels **in place**. Do not uninstall DVM to switch channels: the
uninstall routine deletes its persistent settings/backups and active traffic
database. This procedure concerns the `dvm` Stable/Development channels; moving
from the original `dwdvm` identity uses the separate migration procedure below.

1. Record the installed version and channel. Keep an independent, verified copy
   of the settings, action scripts, and stopped traffic database outside
   plugin-owned directories; see [Storage, backups, and recovery](#storage-backups-and-recovery).
2. Check that the destination channel has an announced release with a version
   newer than the installed version. Equal or older versions may be refused by
   Unraid's plugin manager. Wait for a newer destination release rather than
   forcing a downgrade or removing the plugin.
3. Open **Plugins → Install Plugin** and enter that channel's canonical manifest
   URL from the table above. The same `dvm.plg` identity is installed in place.
   An administrator can alternatively use the Unraid terminal, for example:

   ```sh
   plugin install https://raw.githubusercontent.com/alexphillips-dev/Data-Volume-Monitor/main/plugin/dvm.plg
   ```

   Use that command only after a newer stable release is available. Replace
   `/main/` with `/dev/` when deliberately moving to a newer development build.
4. Check the installation result, reopen the settings page, and confirm the new
   version/channel, retained settings/history, service status, and reports.
   **Service Check** is diagnostic-only. Real action tests require a separate,
   deliberate choice.

The package install path retains existing supported configuration files and the
database; the channel itself does not select a new data directory. Configuration
retention during installation is covered by isolated fixtures. A real-host
channel switch must still be recorded in the
[host-acceptance checklist](docs/host-acceptance.md).

## First-time setup

1. Select the physical interface you want to monitor as **Primary Network
   Interface**. The shipped default is `eth0`; choose the interface appropriate
   for your server.
2. Choose whether to persist the database across reboot before starting the
   service. Persistence defaults to enabled; its control is disabled while the
   service is running.
3. Set **Start DVM service** to **Yes** and apply. New installations start with
   the service disabled.
4. Confirm traffic appears before enabling automation. New databases need time
   to collect period records; missing data is not an exceeded limit.
5. Configure limits and notifications. Check interfaces, directions, periods,
   and targets before enabling workload actions.

Other defaults: dashboard and footer enabled; text reporting; daily miniature
view; virtual interfaces shown; matching, automatic purge, notifications,
user actions, and periodic custom alarms disabled. Every threshold starts at `-1`.

## Thresholds, notifications, and actions

### Choosing limits

Enter a **positive whole number** and a unit. Enter **`-1`** to disable a limit.
Zero, other negative numbers, fractions, and malformed input do not represent
valid active limits. The settings UI offers B, KB, MB, GB, and TB.
Thresholds show **Disabled** in red for `-1`, **Enabled** in green for a positive
whole-number limit, and **Invalid** in red for invalid input. These labels
describe the entered limit; notifications and actions use their separate
switches. Threshold, unit, and action controls stay readable and editable;
the label updates as you type.

The primary interface has eight checks: RX and TX for hour, day, month, and year.
Its threshold settings use a table with one row per check and separate columns
for the limit, unit, Docker stop/start, and VM disconnect/reconnect selections,
matching the secondary section. On narrow screens, scroll the primary table
horizontally to reach all action columns.
The six secondary slots each choose one period and one direction. Secondary
slots must not use the primary interface; use its primary controls instead.

The evaluator uses vnStat's native period, unit, and comparison behavior. A limit
is exceeded when usage is **strictly greater** than the limit. The latest vnStat
period record is used; labels do not imply a rolling 24-hour or 30-day window.
Unit interpretation follows vnStat configuration, including `UnitMode`. Report
formatting uses decimal sizes, so do not infer threshold conversion solely from
a displayed rounded figure. Check effective settings when exact byte limits matter.

### State and notification behavior

The notification check runs once per minute when notifications or user actions
are enabled. The UI refresh interval is separate. Rules have four results:

| Result | Behavior |
| --- | --- |
| Disabled | No threshold action is performed. |
| Normal | Recovery behavior can run after a recorded exceeded state. |
| Exceeded | Configured exceeded notifications/actions can run on the transition. |
| Unavailable/error | No threshold action is performed; existing transition state is preserved. |

Reports aggregate matching custom rules. Confirmed exceeded takes precedence over
unavailable, which takes precedence over normal. Unknown does not establish that
traffic is below its limit.

Exceeded and recovery notifications have separate switches. User actions also
have separate exceeded and recovery switches. These global switches govern
eligible primary and secondary rules.

Transition markers suppress repeat actions for an observed state. They are
temporary, are cleared during service lifecycle operations, and do not provide
permanent once-only delivery across restarts. Failed actions are reported but
are not automatically retried on every repeated check.

The service controls show the latest recorded outcome for each rule, including
the attempt time and Docker, VM, custom-function, and notification results.
Records are temporary and kept under `/var/run/dvm/outcomes/`; they contain
bounded status messages rather than custom-script output. An interrupted attempt
is shown as completion unconfirmed and is not replayed automatically.

Use **Retry Failed Actions** for an eligible failed rule after reviewing the
target workloads and syslog. Retry checks the current configuration, custom
script contents, and fresh threshold state, and runs only components that
previously failed. Changed settings, changed threshold state, successful or
incomplete attempts, and unavailable measurements cannot be retried from an old
record. A retry is a real workload operation and requires confirmation.

**Service Check** runs diagnostics without executing actions, sourcing the user
actions script, sending notifications, or changing transition/outcome state. It
is also available while the service is stopped. **Test Configured Actions** is
separate and runs the real notifier after confirmation. It respects normal
transition guards; it does not force previously consumed transitions to repeat.

### Workload actions

- **Docker:** stop a selected container when exceeded; start a selected container
  when the rule returns to normal, if configured.
- **VMs:** bring discovered network links down/up. These operations change VM
  connectivity; they do not shut down or start the guest.
- **User functions:** execute the matching function from `dvm-user-actions.sh`.

A normal transition follows the rule's configured recovery action. The plugin
does not track whether a workload had originally been stopped manually.
Notification runs use a process lock to prevent overlapping cron/manual checks
from duplicating transition actions.

Settings retain saved interface, container, and VM selections when a target is
temporarily unavailable. Such options are labeled unavailable; discovery errors
are shown separately from a successful discovery with no targets. Review the
warning before saving rather than silently replacing a saved selection.

## Displays and filters

The main page offers text metrics, vnStat-generated images, or both. Images
require the host's image-generation support. The traffic overview stays visible;
the **Detailed Reports** section starts collapsed. Expand it, then select a
period's arrow to read the detailed report. Refreshes preserve whether the
section is open or closed. The dashboard summarizes the
primary interface. The footer's miniature period can be five minutes, hour,
day, month, or year.
The bottom-bar download arrow is green and the upload arrow is blue, with extra
spacing between the two traffic values. Threshold colors on the values retain
their normal meaning.

The footer, dashboard, and report refreshes wait for their current requests to
settle before scheduling another batch. Requests time out after 15 seconds;
failed or incomplete measurement queries retain the last valid sample and show
a stale/error indication with the last successful refresh time. A valid sample
with an unavailable threshold remains valid traffic data; the threshold itself
is shown as unknown. Navigating away cancels pending refreshes.

Virtual, removed-interface, and matching settings affect available rows before
filtering. Matching is case-sensitive. Container/VM name matching requires
virtual service matching to be enabled.

| Filter | Meaning |
| --- | --- |
| Empty | Show rows permitted by the other visibility settings. |
| `eth0;Grafana` | Show rows matching either the interface or service name. |
| `Grafana+Prometheus` | Match a row whose service labels include both names. |
| `Grafana!Prometheus` | Include Grafana unless that row also has the excluded label. |

A semicolon separates alternatives. Combined `+`/`!` expressions operate on
matched service labels. Interface mappings are best-effort snapshots; prefer
physical interfaces for important automation.

## Custom scripts and configuration editor

The editor reads direct regular `.conf` and `.sh` files inside `/etc/vnstat`.
Other paths, nested files, unsupported types, and symlinks are rejected. Wait for
the selected file to load before editing/saving.

A successful save updates runtime and persistent copies. Writes are staged,
checked, and replaced individually; handled partial failures trigger rollback.
If rollback retains a recovery copy, its location appears in the save endpoint's
JSON error response and is displayed as plain text in the editor's error
message. Switching files, cancelling, or leaving with unsaved edits prompts for
confirmation. Edits made during a save remain unsaved after that request
completes. RAM and flash cannot be committed as one
power-loss-atomic filesystem transaction.

### Threshold action functions

Edit **`dvm-user-actions.sh`** to add commands inside its existing functions.
Keep commands inside function bodies because the notifier sources this file.
Names cover hour/day/month/year, RX/TX, and reached/normal transitions, such as
`hour_rx_reached` and `hour_rx_normal_again`.

| Argument | Meaning |
| --- | --- |
| `$1` | Alarm ID: `0` for the primary group, `1`–`6` for a secondary slot. |
| `$2` | Monitored interface name. |

### Periodic custom alarms

**`dvm-custom-alarms.sh`** is an independent advanced script. Its schedule is
separate from built-in thresholds and user-action switches. Choose Never, 1, 15,
30, 45, or 60 minutes. The 45-minute runner uses epoch-minute slots to preserve
45-minute spacing across hour boundaries; enabling it does not imply an
immediate run. Other intervals use their configured cron schedules.

Retain the supplied service-running guard. A custom script can perform whatever
commands you place in it, so test its actions deliberately. The supplied
commented example calls the same validated threshold evaluator as the built-in
rules and explicitly handles normal, exceeded, disabled, and error results.
Unavailable measurements must never be interpreted as an exceeded limit.

## Storage, backups, and recovery

| Location | Purpose |
| --- | --- |
| `/boot/config/plugins/dvm/dvm.cfg` | Persistent plugin settings. |
| `/boot/config/plugins/dvm/vnstat/` | Persistent supported configuration/action files. |
| `/etc/vnstat/` | Runtime configuration and action scripts. |
| `/etc/vnstat.conf` | Standard configuration link used by vnStat tools. |
| Effective `DatabaseDir` + `/vnstat.db` | Active SQLite database; default `/var/lib/vnstat/vnstat.db`. |
| `/boot/config/plugins/dvm/vnstat.db` | Database backup when persistence is enabled. |
| `/boot/config/plugins/dvm/vnstat.db.path` | Source path and SHA-256 metadata for new backups. |
| `/boot/config/plugins/dvm/vnstat.previous.tar` | Previous verified database generation and its path/checksum metadata. |
| `/var/run/dvm/outcomes/` | Temporary per-rule automation outcomes; cleared by Reset All and uninstall. |
| `/usr/local/emhttp/plugins/dvm/` | Installed web UI, scripts, and assets. |
| `/etc/rc.d/rc.vnstat` | Service, configuration, and backup entry point. |

### Reboot persistence

When enabled, the service installs and verifies its own marked shutdown hook.
It supports shell-script layouts without relying on a particular host comment,
preserves unrelated host content, and reports an error if the hook cannot be
installed safely. Backup failure is logged without interrupting the host's
remaining shutdown steps.
Disabling persistence or uninstalling removes the exact managed hook (or its
recognized legacy line), leaving unrelated host hooks and commands intact.

The service restores a matching backup when the configured runtime database is missing. Existing runtime data
is retained. Configuration restore excludes database/SQLite companion files,
preventing a stale configuration mirror from replacing current traffic history.

New backups bind their source path to a checksum. Before publishing a new backup,
the previous valid generation is retained as one archive. Restoration tries the
current backup first and then the retained generation; each must match the
configured path and its checksum. An invalid current backup cannot replace a
valid retained generation. A restore is staged and checked before the runtime
database is created, so a failed copy does not leave a partial database there.

Older untagged backups are treated as belonging to the default database location.
Persistence preserves successfully backed-up data; it cannot reconstruct traffic
lost before a successful backup. An older fallback naturally omits traffic
recorded after that generation.

Keep an independent copy before migration, reset, or removal. The plugin's flash
backups, including the retained generation, are deleted during Reset All and uninstall.

### Custom locations and manual backups

Stop the service before editing `DatabaseDir` or `PidFile` in `vnstat.conf`.
The editor checks effective configuration and rejects changes to those paths
while running. Status detection does not assume the default PID filename.

Changing `DatabaseDir` does not move history. With the service stopped, move/copy
the database deliberately, set appropriate ownership/permissions, and verify
configuration before starting. An old-path backup is not silently restored into
a different location. Both resets retain the selected database directory.

On an installed Unraid host, a manual plugin backup uses:

```sh
/etc/rc.d/rc.vnstat backup_db
```

This command **stops the service** and respects the persistence setting. Check
its exit status/output and restart explicitly when ready:

```sh
/etc/rc.d/rc.vnstat start
```

## Migration from the original plugin

The new identity is `dvm`; the original is `dwdvm`. Removing the original without
a verified backup can delete settings and traffic history.

1. Stop the original service. Back up `/boot/config/plugins/dwdvm` outside its
   plugin directory.
2. Copy the newest stopped `vnstat.db` from its effective `DatabaseDir`, normally
   `/var/lib/vnstat`. Preserve custom `/etc/vnstat` files. Verify the copies.
3. Remove the original plugin. Its uninstall routine deletes its settings,
   `/etc/vnstat`, and the default runtime database directory.
4. Install the chosen available channel's manifest above. Leave its service disabled.
5. Restore `dwdvm.cfg` as `/boot/config/plugins/dvm/dvm.cfg`, with
   `SERVICE="disable"` until restoration is complete.
6. Restore supported `.conf`/`.sh` files to `/etc/vnstat` and
   `/boot/config/plugins/dvm/vnstat`. Do not restore `dwdvm.cfg` into these
   directories. Update old plugin paths in custom scripts.
7. Restore the newest database into the restored configuration's `DatabaseDir`
   and retain an independent backup. It may also be copied to
   `/boot/config/plugins/dvm/vnstat.db`; a custom path needs a successful new
   backup before its path/checksum metadata is established.
8. Set restored files to root ownership, database/configuration files to `644`,
   directories to `755`, and the two action scripts to `755`.
9. Enable the service. Verify interfaces, history, thresholds, actions, and
   persistence through a normal reboot.

Keep the independent backup until migration is verified. Do not install both
identities together.

## Reset, purge, and uninstall

| Operation | Effect |
| --- | --- |
| Restart DVM | Stop, apply configuration, and start; prerequisite failures abort the sequence. |
| Reset Config | Reset managed settings/action files; retain traffic and selected database directory. |
| Reset All | Reset settings and clear active database/backup; retain selected database directory. |
| Purge Database | Remove obsolete interface records, excluding the primary interface. Their traffic records are lost. |
| Uninstall | Stop, remove packages, then delete plugin configuration/backups and active database/SQLite companions. |

Automatic purge performs the obsolete-interface cleanup when enabled. Virtual
interface recreation can leave useful historical records, so consider whether
to retain them before enabling removal.

At custom locations, Reset All/uninstall remove known database files while
leaving directories outside plugin-owned configuration folders in place.
Plugin-owned configuration directories are themselves subject to cleanup.
Reset Config retains extra supported files while replacing managed defaults.

Use **Service Check** for diagnostics. Use **Test Configured Actions** only when
ready for real notifications, Docker operations, VM link changes, and user
functions.

## Troubleshooting and support

Start with these read-only commands on the Unraid host:

```sh
/etc/rc.d/rc.vnstat status
/etc/rc.d/rc.vnstat database_path
vnstat --config /etc/vnstat/vnstat.conf --iflist
vnstat --config /etc/vnstat/vnstat.conf --dbiflist
vnstat --config /etc/vnstat/vnstat.conf --showconfig
```

| Symptom | Check |
| --- | --- |
| No traffic rows | Service enabled, correct interface, vnStat records, visibility/filter settings, and time for new data. |
| Threshold unavailable | Invalid input, missing period/interface data, configuration error, or backend failure. |
| Unexpected RX/TX | Observation point: physical NIC, bridge, or virtual peer. |
| Missing workload labels | Matching enabled, discovery succeeds, interface still exists. Virtual names can change. |
| Action did not run | Correct switch, valid limit/target, actual transition, rule outcome, and syslog. Repeated states are not retries. |
| Traffic marked stale | Last successful refresh, service/query errors, and connectivity. The retained value is an older sample. |
| History missing after reboot | Persistence, backup validity/path/checksum, effective DatabaseDir, and shutdown backup execution. |
| Images missing | Try text metrics and check image-generation support. |
| Save failed | Inspect error, runtime/persistent files, flash space, permissions, and recovery copy before retrying. |

Log tags include `dvm-notify`, `dvm-user-actions`, and `dvm-gui`. Transport failures
can leave earlier UI numbers visible; check backend state rather than treating
unchanged numbers as a fresh sample.

Issues should include plugin version/branch, Unraid version, reproduction steps,
expected/actual behavior, relevant settings, and sanitized logs. Remove credentials
and private server/workload details. Review any settings directory or traffic
database before sharing it.

## Development and testing

### Repository layout

| Path | Contents |
| --- | --- |
| `source/` | Slackware package filesystem tree and implementation. |
| `plugin/dvm.plg` | Install/update/remove manifest and changelog. |
| `plugin/dvm.png` | Repository plugin icon. |
| `packages/` | Required vnStat dependency archive. |
| `packages/sources/` | Corresponding vnStat source, signature, and upstream public signing key. |
| `packages/vnstat-2.14-build.json` | Dependency source/toolchain inputs, executable hashes, and ABI metadata. |
| `archive/` | Plugin package and checksum sidecars. |
| `scripts/build_package.py` | Deterministic builder with staged output/recovery. |
| `scripts/build_vnstat.py` | Pinned Linux build for the vnStat dependency. |
| `scripts/validate_repository.py` | Shared local/CI syntax, regression, tracking, and package checks. |
| `scripts/release_channel.py` | Shared channel URL and release-metadata rules. |
| `scripts/prepare_release.py` | Isolated candidate preparation, dry-run reporting, and guarded generated-file updates. |
| `.github/workflows/validate.yml` | Validation for pushes and pull requests targeting `main`. |
| `tests/` | Isolated regressions and bundled-binary integration tests. |

### Review and test

Read affected code and callers before changes. Reproduce bugs, review the fix,
run its regression afterward, and check persistence, errors, and connected
behavior. Commands and coverage for the initial audit and subsequent improvements are documented
in [tests/README.md](tests/README.md).

The full suite needs Linux, Python 3, Bash, `flock`, PHP CLI with SimpleXML, and
Node.js. Native tests currently use `/usr/bin/php8.3`. On Windows, use WSL for
Linux-dependent suites; JavaScript tests can use Windows Node.js. Skipped
platform-specific tests do not validate the skipped behavior.

Tests use temporary paths and mocked workloads. Native vnStat tests extract the
bundled binaries and initialize an isolated database without starting a daemon.
Fixture results do not establish live Unraid acceptance.

After building the candidate package, run the same check used by GitHub Actions:

```sh
python3 scripts/validate_repository.py --channel dev
```

Use `--channel main` for a final Stable candidate. Explicit channel selection
also works in detached checkouts; a branch name alone is not evidence that the
manifest and packaged metadata point to the correct channel. Run validation as
an unprivileged Linux user. It checks PHP/Bash/JavaScript syntax and
ShellCheck warnings, discovers all Python/PHP/JavaScript regressions, rejects
skipped Python tests and tracked ignored files, and verifies manifest downloads,
checksums, archive inventory/bytes/permissions, icon consistency, and a
reproducible rebuild. CI uses Ubuntu 24.04, Python 3.12, PHP 8.3 with SimpleXML,
and Node.js 24. A local pass and the hosted result apply to the tested commit;
live Unraid acceptance remains separate.

### Build

The bundled backend is built from the signed
[upstream 2.14 release](https://github.com/vergoh/vnstat/releases/tag/v2.14).
Its corresponding source and detached signature are included in the repository.
To rebuild it as an unprivileged Linux user, install Python 3.12+, `make`, GnuPG,
and `readelf` (binutils), then run:

```sh
python3 scripts/build_vnstat.py
```

The build verifies the source SHA-256 and pinned upstream signing fingerprint
`23EF1DD76E65248FB055201ADAFE84E63D140114`. It downloads a pinned Zig/LLVM
toolchain and checksum-pinned baseline GD/SQLite headers and link libraries into
`~/.cache/dvm-vnstat-build/` (override with `--cache PATH`). Build inputs remain in
that local cache; host libraries are not shipped. Builds occur in fresh isolated
directories and do not run `make install` or start a service. Executables must
pass x86_64, GLIBC symbol, library dependency, and embedded-path checks before
publication. Package ownership/modes/timestamps are deterministic, and GPL
license, upstream documentation, and manpages are included.

The builder writes the dependency archive, MD5/SHA-256 sidecars, and build
metadata. Update the dependency identity/MD5 in the plugin manifest when
introducing a new backend build. The old 2.12 archive is retained for historical
downloads and isolated database/threshold compatibility tests.

The 2.14 upgrade retains saved configuration and traffic databases. New installs
and resets receive a configuration documenting the new optional settings while
retaining DVM's collection/save intervals and automatic-interface defaults.
Native qualification covers reading a 2.12 database without losing its traffic
history; vnStat updates its own version metadata. Keep an independent backup
when testing upgrades on a real host.

After validation, run from the repository root with Python 3:

```sh
python scripts/build_package.py
```

The builder reads the manifest's package identity, assembles `source` with
deterministic ownership/modes/timestamps and Unix text line endings, creates
`.txz`, `.txz.md5`, and `.txz.sha256`, and updates the manifest MD5. It rejects
missing required payloads, symlinks, and unreadable directories; stages outputs;
and restores previous files on handled replacement failures. Failed rollback
retains recovery files. Multiple outputs are not a power-loss transaction.

Commit matching packages/checksums with source and manifest changes. For a new
distributed build, update the version/package identity rather than replacing
an artifact already installed by users.

### Branch and publication workflow

Completed updates target **`dev`**. Installer/download/update URLs must use `dev`.
Promotion to `main` or a stable release requires an explicit maintainer request.

Release preparation accepts only the `dev` and `main` channels. It renders the
manifest and packaged `release.json` from the same channel/version pair, keeps
the identity `dvm`, and validates all final download/update URLs and package
contents. Installed plugins do not inspect Git repositories to discover their
channel.

Use a newer, consistently zero-padded `YYYY.MM.DD.NN` date/build version, such as
`2026.11.04.10`; do not reuse a published version for changed package bytes.
Preparation checks the calendar date and requires changed release pairs to
order after the current version and every existing plugin archive, both
numerically and in Unraid's version-string comparison. Every preparation mode
requires a new version, including dry-run. A stable promotion should use a fresh
version above the development version being promoted. Use `build_package.py`
to reproduce an existing exact candidate; an identical rebuild is not a new
release and must not replace published bytes with changed content.

To review a candidate without changing the checkout, substitute a new numeric
version in these commands:

```sh
python3 scripts/prepare_release.py --channel main --version NEW_VERSION --dry-run
python3 scripts/prepare_release.py --channel main --version NEW_VERSION --output /tmp/dvm-stable-candidate
python3 /tmp/dvm-stable-candidate/scripts/validate_repository.py --channel main
```

`NEW_VERSION` is a placeholder, not a literal accepted version. Dry-run is also
the default when no output/apply mode is selected. `--dry-run` builds an isolated
candidate, runs its package/tracking checks, and prints its plan. `--output`
prepares a complete candidate outside the repository and refuses to overwrite
an existing destination. Neither mode merges, commits, pushes, or promotes a
branch. Run the separate full validation command against the output candidate;
preparation's package checks do not replace its regression suite.

Use `--notes-file PATH` to supply UTF-8 Markdown bullet notes for the new
manifest changelog. Read and review the generated notes with the package plan.

`--apply` updates generated release files transactionally only from a named
checkout matching the chosen channel. Do not apply a `main` candidate to a
`dev` checkout. For a separately authorized promotion, prepare the approved
main checkout, apply the new main-channel release there, run final validation,
review/commit the exact candidate, and publish it through main's checks. Keep
`dev` metadata on `dev` when synchronizing code back afterward. Preparation is
not authorization to merge or publish `main`.

The maintainer requires `--no-verify` for development commits/pushes. Development
updates do not trigger hosted checks, and development runs are not monitored.
GitHub Actions checks apply to `main` and pull requests targeting `main`, once
the workflow is included in that branch. Run applicable local regressions for
code changes before publishing:

```sh
git switch dev
# Review, test, and verify the package before staging reviewed paths.
git add <reviewed-paths>
git commit --no-verify -m "Describe the change"
git push --no-verify origin dev
```

Track source, tests, documentation, required `.txz` archives, and checksums.
`.gitignore` excludes environments, caches, editor files, credentials, logs,
temporary/recovery files, runtime databases, and local support exports. Required
packages, release archives, shipped assets, and matching checksums remain tracked.

## Host acceptance

[docs/host-acceptance.md](docs/host-acceptance.md) is the manual checklist for
installation/update, in-place channel switching, UI behavior, the 2.14 backend,
and normal-reboot recovery. Record the exact candidate version/channel/checksum,
host Unraid version, and observed results. Unchecked items are pending; passing
fixtures do not mark them complete. The checklist does not automatically run
host commands, reboot a server, or execute workload actions.

## License

This project continues under **GPL version 2 where applicable**; see [LICENSE](LICENSE)
and notices in individual files. Required original copyright and third-party
notices remain intact. vnStat and bundled dependencies retain their respective
licenses.
