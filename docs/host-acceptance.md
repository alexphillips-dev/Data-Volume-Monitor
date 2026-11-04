# Host acceptance record

Use this checklist on an Unraid test host for the exact candidate being
considered for release. Automated fixture results are recorded separately.
Nothing in this document runs automatically. Leave an item unchecked until its
expected behavior has been observed on the host.

## Candidate and environment

| Field | Record |
| --- | --- |
| Candidate version and channel | Pending |
| Source commit | Pending |
| Plugin archive SHA-256 | Pending |
| Backend package/version | Pending; expected vnStat 2.14 |
| Unraid version/architecture | Pending |
| Theme/browser/viewport | Pending |
| Primary interface | Pending |
| Effective DatabaseDir/PidFile | Pending |
| Tester/date | Pending |

Keep logs/screenshots sanitized. Do not publish credentials, private server
names, workload details, settings exports, or a traffic database without review.

## Before changing an existing installation

- [ ] Record the current plugin version, channel, backend version, service state,
  settings, and representative traffic-history values.
- [ ] Identify the effective database location. Do not assume the default path
  if the configuration contains a custom `DatabaseDir`.
- [ ] Keep independent verified copies of settings/action files and the stopped
  database outside plugin-owned directories. DVM's own backup location is not
  an independent copy for reset/uninstall testing.
- [ ] Use a test host and disposable workloads for any real-action checks.
  Do not enable automation on valuable targets merely to complete this list.

Read-only diagnostics on the installed Unraid host:

```sh
/etc/rc.d/rc.vnstat status
/etc/rc.d/rc.vnstat database_path
vnstat --config /etc/vnstat/vnstat.conf --iflist
vnstat --config /etc/vnstat/vnstat.conf --dbiflist
vnstat --config /etc/vnstat/vnstat.conf --showconfig
```

## Install/update and channel

- [ ] Install a fresh candidate and check that installation reports success.
  Confirm the new-install service is disabled until deliberately enabled.
- [ ] Upgrade an existing `dvm` installation in place. Confirm settings, custom
  action files, selected interfaces/targets, database location, and historical
  traffic remain intact.
- [ ] Confirm the displayed release version and Stable/Development channel
  match the installed manifest and packaged release metadata.
- [ ] Confirm the backend reports 2.14 and `vnstat`, `vnstatd`, and `vnstati` are
  available where their corresponding host libraries support execution.
- [ ] Confirm update checks retain the chosen channel's canonical URL. A
  development installation must not silently move to `main`, or vice versa.
- [ ] If a newer destination-channel build exists, perform the documented
  in-place channel switch and repeat the retained-data checks. Do not uninstall
  as a channel-switch step. Record a pending result if no newer target exists.

For an in-place switch, use the destination channel's announced canonical
manifest in **Plugins → Install Plugin**. Same/older versions may be refused.
Do not force a downgrade or remove the plugin to bypass that result.

## Collection and reports

- [ ] Enable the service on the intended interface and confirm collection starts.
- [ ] Check the overview, footer, and dashboard against native vnStat output.
  Allow time for a new database to acquire period records.
- [ ] Expand **Detailed Reports** and its individual periods. Confirm text,
  image, and dual outputs. Missing image-library support is a host capability
  result; it must not be reported as a fully passing image test.
- [ ] Confirm the Detailed Reports section starts collapsed and keeps its open
  state through refreshes.
- [ ] Confirm primary/secondary threshold controls stay readable. `-1` shows red
  Disabled, positive whole-number limits show green Enabled, and invalid input
  shows red Invalid. These labels do not enable global action switches.
- [ ] Check the native light/dark theme, desktop/mobile sizing, filtering, and
  retained unavailable selections used by this host.
- [ ] Exercise a safe query/connection failure. Confirm prior valid values are
  marked stale, the last-success time does not advance on failure, and recovery
  produces a fresh sample. Restore the host's normal state afterward.

## Diagnostics, editor, and automation

- [ ] Run **Service Check**. Confirm diagnostics do not execute custom actions,
  send notifications, or change transition/outcome state.
- [ ] Use a temporary supported configuration/action file to check editor load,
  plain-text errors, save/reload persistence, empty contents, and unsaved-change
  prompts. Keep independent copies before editing real configuration.
- [ ] If real actions are part of qualification, deliberately use **Test
  Configured Actions** with disposable Docker/VM targets. Confirm exceeded and
  recovery behavior, and the separate global notification/action switches.
- [ ] For a deliberately failed disposable action, inspect its recorded result.
  Confirm an explicit retry repeats failed components only and rejects stale
  configuration/threshold state. Repeated polling must not retry automatically.
- [ ] Confirm an interrupted or unconfirmed action attempt is visibly distinct
  from success and is not automatically replayed.

Real-action and interruption checks may be left pending when no appropriate
disposable environment exists. Do not equate diagnostic-only output with a
successful real workload action.

## Persistence and normal reboot

- [ ] Confirm persistence is enabled and the managed shutdown hook is present
  without duplicating unrelated host shutdown commands.
- [ ] With data already recorded and an independent backup available, perform a
  normal host reboot at a chosen maintenance time.
- [ ] Confirm the service, effective custom/default database location, settings,
  and traffic history return as expected. Check the current backup's path and
  checksum metadata; record any restoration or syslog warning.
- [ ] Validate retained-generation recovery only on copied data or a disposable
  host. Never corrupt the only live database or backup to test fallback.
- [ ] If persistence is disabled for a separate test, confirm the owned hook is
  removed and document the expected lack of reboot history persistence.

Reset All and uninstall delete data. Their destructive acceptance tests belong
only on a disposable installation after independent backups are verified.

## Outcome

| Item | Result/evidence |
| --- | --- |
| Passed observations | Pending |
| Failed observations | Pending |
| Unrun/pending observations | All items until recorded |
| Sanitized logs/screenshots | Pending |
| Restore/cleanup after testing | Pending |
| Release decision | Pending; a checklist template is not a release approval |
