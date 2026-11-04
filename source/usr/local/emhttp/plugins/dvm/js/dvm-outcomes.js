/* Copyright 2026 alexphillips-dev. Licensed under GPL-2.0. */
(function (root) {
    'use strict';
    function create(body, status) {
        var fresh = false, buttons = [];
        function validRule(rule) {
            return typeof rule === 'string' && /^(?:primary-[hdmy]-(?:rx|tx)|secondary-[1-6])$/.test(rule) && rule.indexOf('\n') < 0;
        }
        function allowed(record) {
            return record.status === 'failed' && record.retryable === true && validRule(record.rule);
        }
        function refresh() { poll.stop(); poll.start(); }
        function render(data) {
            fresh = false;
            buttons = [];
            body.empty();
            var outcomes = data.outcomes.outcomes;
            if (!outcomes.length) {
                body.append(root.$('<tr>').append(root.$('<td>').attr('colspan', '6').text('No recorded action attempts.')));
            }
            outcomes.forEach(function (record) {
                var row = root.$('<tr>');
                [record.rule, record.interface, record.state].forEach(function (value) { row.append(root.$('<td>').text(value)); });
                var result = root.$('<td>');
                result.append(root.$('<div>').text(record.status === 'running' ? 'In progress or completion unconfirmed' : record.status));
                ['docker', 'vm', 'custom', 'notification'].forEach(function (name) {
                    var component = record.components && record.components[name];
                    if (component) result.append(root.$('<div>').text(name + ': ' + component.status + (component.reason ? ' — ' + component.reason : '')));
                });
                row.append(result);
                row.append(root.$('<td>').text((record.updated_at || 'Unknown time') + ' (attempt ' + record.attempts + ')'));
                var retry = root.$('<button>').attr('type', 'button').text('Retry failed actions').prop('disabled', true);
                retry.on('click', function () {
                    if (!fresh || !allowed(record)) return;
                    if (!root.confirm('Retry the failed actions for ' + record.rule + '? Real workloads, custom functions, and notifications may run. Completed actions will not be repeated.')) return;
                    fresh = false;
                    buttons.forEach(function (item) { item.button.prop('disabled', true); });
                    root.openBox('/usr/local/emhttp/plugins/dvm/scripts/retry_action ' + record.rule, 'Retry Failed Actions', 600, 600, false);
                });
                buttons.push({button:retry, record:record});
                row.append(root.$('<td>').append(retry));
                body.append(row);
            });
        }
        var poll = root.DVMPoll.create({
            key:'dvmOutcomes', interval:30000,
            requests:[{key:'outcomes', url:'/plugins/dvm/include/dvm_outcomes.php', validate:function (data) {
                return data && data.success === true && Array.isArray(data.outcomes) && data.outcomes.every(function (record) {
                    return record && typeof record.rule === 'string' && typeof record.status === 'string';
                });
            }}],
            render:render,
            onState:function (state) {
                fresh = state.phase === 'fresh';
                root.DVMPoll.annotate(body, status, state);
                buttons.forEach(function (item) { item.button.prop('disabled', !fresh || !allowed(item.record)); });
            }
        });
        poll.start();
        return {refresh:refresh, testActions:function () {
            if (!root.confirm('Test configured actions now? Real workloads, custom functions, and notifications may run for saved threshold settings. Repeated transitions are not forced.')) return;
            root.openBox('/usr/local/emhttp/plugins/dvm/scripts/test_actions', 'Test Configured Actions', 600, 600, false);
        }};
    }
    root.DVMOutcomes = {create:create};
})(window);
