/* Copyright 2026 alexphillips-dev. Licensed under GPL-2.0. */
(function (root) {
    'use strict';
    if (root.DVMPoll) return;
    var controllers = {};

    function statusText(state) {
        var updated = state.lastSuccess === null ? null : new Date(state.lastSuccess).toLocaleTimeString();
        if (state.phase === 'stale') return updated ? 'Data is stale. Last updated ' + updated + '.' : 'Data unavailable. No successful update yet.';
        if (updated) return 'Updated ' + updated + '.';
        return 'Loading data...';
    }

    function annotate(target, statusTarget, state, title) {
        var message = statusText(state);
        target.attr('data-dvm-state', state.phase)
            .attr('data-dvm-last-success', state.lastSuccess === null ? '' : String(state.lastSuccess))
            .attr('title', (title ? title + ' — ' : '') + message);
        if (statusTarget) statusTarget.text(message);
    }

    function create(options) {
        if (controllers[options.key]) controllers[options.key].stop();
        var active = false, busy = false, generation = 0, timer = null;
        var handles = [], lastSuccess = null, phase = 'loading';
        var interval = Math.max(1000, Number(options.interval) || 30000);
        var timeout = Math.max(1000, Math.min(Number(options.timeout) || 15000, 60000));

        function state() {
            if (options.onState) options.onState({phase:phase, lastSuccess:lastSuccess, pending:busy});
        }

        function clearTimer() {
            if (timer !== null) root.clearTimeout(timer);
            timer = null;
            if (options.timerStore) delete options.timerStore[options.key];
        }

        function poll() {
            if (!active || busy) return;
            if (options.isActive && !options.isActive()) { stop(); return; }
            clearTimer();
            busy = true;
            var current = ++generation, remaining = options.requests.length;
            var responses = {}, failed = false;
            handles = [];
            state();

            function finish() {
                if (!active || current !== generation || --remaining !== 0) return;
                busy = false;
                handles = [];
                if (!failed) {
                    try {
                        if (options.validate && !options.validate(responses)) throw new Error('Invalid response');
                        options.render(responses);
                        lastSuccess = Date.now();
                        phase = 'fresh';
                    } catch (error) {
                        phase = 'stale';
                    }
                } else {
                    phase = 'stale';
                }
                state();
                timer = root.setTimeout(poll, interval);
                if (options.timerStore) options.timerStore[options.key] = timer;
            }

            options.requests.forEach(function (request) {
                var settled = false;
                var handle = root.$.ajax({
                    url: request.url || '/plugins/dvm/include/dvm_report.php',
                    data: request.data,
                    dataType: 'json',
                    timeout: timeout
                }).done(function (data) {
                    if (!active || current !== generation) return;
                    var valid = request.validate ? request.validate(data) : data && data.success && data.success.dataAvailable === true && typeof data.success.response === 'string' && data.success.response.length > 0;
                    if (valid) responses[request.key] = data;
                    else failed = true;
                }).fail(function () {
                    if (active && current === generation) failed = true;
                }).always(function () {
                    if (settled) return;
                    settled = true;
                    finish();
                });
                handles.push(handle);
            });
        }

        function start() {
            if (active) return;
            active = true;
            poll();
        }

        function stop() {
            active = false;
            busy = false;
            generation++;
            clearTimer();
            var pending = handles;
            handles = [];
            pending.forEach(function (request) { request.abort(); });
        }

        var controller = {start:start, stop:stop};
        controllers[options.key] = controller;
        return controller;
    }

    root.addEventListener('pagehide', function () {
        Object.keys(controllers).forEach(function (key) { controllers[key].stop(); });
    });
    root.addEventListener('pageshow', function (event) {
        if (event.persisted) Object.keys(controllers).forEach(function (key) { controllers[key].start(); });
    });
    root.DVMPoll = {create:create, annotate:annotate, statusText:statusText};
})(window);
