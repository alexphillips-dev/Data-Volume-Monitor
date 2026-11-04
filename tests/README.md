# Regression tests

These tests exercise the fixes from the initial Data Volume Monitor audit.
They use temporary files and mocked service/workload commands. The native
vnStat suite extracts the bundled binaries into a temporary directory, creates
an isolated SQLite database with `--initdb`, and exits without starting a daemon.
Do not run installation, removal, or reset scripts directly to test them.

## Requirements and commands

The complete suite needs Linux, Python 3.12+, Bash, `flock`, PHP 8.3 CLI with
SimpleXML, Node.js, GnuPG, binutils (`readelf`), `libsqlite3.so.0`, and
`libgd.so.3`. The native tests use `/usr/bin/php8.3` explicitly.
From the repository root:

```sh
python3 scripts/validate_repository.py --channel dev
```

This is the complete local/CI entry point. Run it after building the candidate
archive. It discovers every Python test module, top-level PHP fixture, and
JavaScript fixture, and fails on skipped Python tests. It also validates syntax,
ShellCheck warnings, ignored/tracked files, manifest URLs/checksums, exact package
contents and permissions, icons, and deterministic rebuilding in a temporary
copy. GitHub Actions runs it on pushes and pull requests targeting `main`.
Development commits and pushes use `--no-verify`; hosted development runs are
not triggered or monitored. Local regression testing remains available for
verifying code changes.

Use `--channel main` when checking the exact final stable candidate. Main CI
supplies its expected channel explicitly; this also covers detached PR
checkouts. Merely naming a checkout `main` does not establish that its manifest,
downloads, installed release metadata, and package agree on `main`.

To run regressions separately while developing:

```sh
python3 -m unittest discover -s tests -p 'test_*.py' -v
/usr/bin/php8.3 tests/editor_paths.php
/usr/bin/php8.3 tests/editor_save.php
/usr/bin/php8.3 tests/report_custom_thresholds.php
/usr/bin/php8.3 tests/report_threshold_errors.php
/usr/bin/php8.3 tests/test_threshold.php
/usr/bin/php8.3 tests/test_config_guard.php
node tests/editor-races.mjs
node tests/filters.mjs
node tests/dashboard-status.mjs
```

The individual list above covers the initial audit; the shared validator also
discovers all newer PHP and JavaScript fixtures listed below. To select a
validation phase, use `--checks tracked syntax`, `--checks tests`, or
`--checks package`. WSL can use Windows Node.js automatically; hosted CI uses
native Node.js. PHP can be selected with `DVM_PHP_BIN` when necessary.

On Windows, run the Python and PHP commands in WSL for real Linux locks,
symlinks, and file permissions. Node tests can run with Windows Node.js.
Some tests support Windows Python/Git Bash as additional coverage, but those
runs do not replace Linux verification. A skipped native or permission test
is not a pass for that behavior.

## Coverage by audit finding

| Finding | Regression coverage |
| --- | --- |
| 1. Editor path access | `editor_paths.php`: valid files, traversal, sibling paths, types, symlinks |
| 2. Query errors triggering actions | `test_threshold.php`, `test_notifier.py`, `report_threshold_errors.php`, `dashboard-status.mjs`, `test_vnstat_binary.py` |
| 3. Editor request races | `editor-races.mjs`: stale responses, pending/failed loads, save identity and pending saves |
| 4. Partial/empty saves | `editor_save.php`: persistence failure, rollback, empty files, modes and paired contents |
| 5. Service failure propagation | `test_lifecycle.py`: start/stop/status, wrappers, resets and installer gates |
| 6. Concurrent notification actions | `test_notifier.py`: real Linux lock, overlap and lock failure |
| 7. VM operation results | `test_notifier.py`: failed lookup/link, empty/missing interfaces and valid actions |
| 8. Multiple custom rules | `report_custom_thresholds.php`: all six rules, same-cell aggregation and disabled rules |
| 9. Filtering | `filters.mjs`: combined matches, exclusions and PHP-to-JavaScript encoding |
| 10. Interface matching | `test_match_virts.py`: VM spaces, exact peer indexes and bridge controls |
| 11. 45-minute interval | `test_custom_interval.py`: generated schedule across hour boundaries |
| 12. Custom vnStat paths | `test_storage_paths.py`, `test_config_guard.php`, `test_vnstat_binary.py`: persistence, resets and effective settings |
| 13. Failed builds | `test_build_package.py`: invalid manifests, source/read failures, replacement rollback, recovery copies and platform-independent mixed-case entry order |

## Subsequent improvements

Each behavior change was inspected in source and exercised against an isolated
regression before and after its correction. Connected suites are rerun after
integration.

| Improvement | Regression coverage |
| --- | --- |
| Refresh settlement, timeouts and stale data | `polling.mjs`, `report_availability.php`, `ui-asset-cache.php`: pending batches, errors, last valid values, stale responses, page lifecycle, actual backend availability, recovery, content-based asset cache invalidation |
| Verified shutdown hooks and retained backups | `test_shutdown_hook.py`, `test_storage_paths.py`: host layout variants, idempotence, validation/publication failures, corrupt/interrupted backups, matching previous generation, reset/removal |
| Retained unavailable selections | `inventory-options.php`: saved targets missing, discovery failure versus empty results, encoding and successful discovery |
| Safe report text and generated image names | `report_escaping.php`: service/interface/text markup, entities, UTF-8, trusted filter spans, image paths and dashboard protocol |
| Editor errors and unsaved changes | `editor-races.mjs`: plain-text backend errors, switch/Cancel/leave protection, edits during saves and original request-race regressions |
| Diagnostic-only check and safe custom example | `test_notifier.py` diagnostic group, `outcomes-ui.mjs`: no real actions, no sourced custom code, unchanged markers/outcomes, explicit real-action controls |
| Recorded action outcomes and explicit retries | `test_notifier.py` outcomes group, `test_outcomes.php`, `outcomes-ui.mjs`: failed-component retry, stale state/config/script rejection, interrupted attempts, ledger write faults, safe status text and fixed rule tokens |
| Automated package and regression gates | `test_validation.py`: matching candidate, stale source, corrupt dependencies/sidecars, version mismatch, ignored tracked files and packaged local secrets |
| Release channels and preparation | `test_channels.py` and `test_prepare_release.py` cover canonical main/dev URLs, wrong/mixed channels, installed metadata, detached context, version ordering and isolated candidate preparation; `release_metadata.php` covers strict installed metadata and safe display. |
| Primary threshold table | `primary-threshold-table.php` renders the production fragment with the real configuration mappings, checks all eight rows and 48 field identities, preserves saved/missing workload selections through simulated Apply/reload, and checks disabled defaults and units. `threshold-status.mjs` runs the production status function for all primary and secondary fields, including color transitions, uint64 boundaries, and accessible descriptions. |

Native vnStat tests select the active dependency from the manifest. They compare
the shared structured evaluator, the 2.14 command's alert result, and the legacy
2.12 binary over 72 combinations of periods, directions, all three unit modes,
and threshold boundaries. They also cover invalid input, missing data, overflow,
default/custom effective paths, and DVM's non-default collection/save settings.

The backend upgrade fixtures exercise all three executables, all six PNG output
modes, JSON/XML escaping, and every PHP report mode in text/image/dual format.
`fixtures/native_reports.php` runs the actual PHP report/evaluator functions with
backend commands redirected to temporary binaries/configuration/images. A
database created by 2.12 is queried/initialized by 2.14; all traffic/schema/alias
content is retained while vnStat's version metadata is updated. No daemon is
left running. `test_backend_package.py` verifies the source signature, license
and documentation bytes, executable hashes, runtime libraries, x86_64 loader,
and glibc ceiling. Package guard regressions reject stale/corrupt backend
provenance and missing license files, even with recalculated archive checksums.

## Limits

Fixtures do not establish acceptance on a live Unraid host. Native web UI
integration, authenticated endpoint access, real workload operations, and
shutdown/reboot persistence still require host verification. Individual file
replacements are atomic; paired saves across RAM and flash and multi-file build
publication are not power-loss transactions.

Use [the host-acceptance record](../docs/host-acceptance.md) to qualify real
installation/update, in-place channel switching, native themes/reports, the
2.14 backend, and normal reboot persistence. Record exact candidate and host
details. Every checkbox starts pending; no fixture or prepared document marks
an unrun host observation as passed.
