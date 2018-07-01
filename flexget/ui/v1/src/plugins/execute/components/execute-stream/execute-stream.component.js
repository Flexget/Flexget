/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .component('executeStream', {
            templateUrl: 'plugins/execute/components/execute-stream/execute-stream.tmpl.html',
            controllerAs: 'vm',
            controller: executeStreamController,
            bindings: {
                stopStream: '<',
                options: '<'
            }
        });

    function executeStreamController($filter, $log, executeService) {
        var vm = this;

        vm.$onInit = activate;
        vm.clear = clear;
        vm.streamTasks = [];
        vm.streamProgress = 0;

        var stream;

        function activate() {
            setupTaskProperties();
            startStream();
        }

        function setupTaskProperties() {
            for (var i = 0; i < vm.options.tasks.length; i++) {
                var task = {
                    name: vm.options.tasks[i],
                    percent: 0,
                    entries: [],
                    status: 'pending'
                };

                vm.streamTasks.push(task);
            }
        }

        function sortStreamTasks(taskData) {
            var notOrdered = angular.copy(vm.streamTasks);
            vm.streamTasks = [];

            for (var i = 0; i < taskData.length; i++) {
                var emptyTask = $filter('filter')(notOrdered, { name: taskData[i].name });
                vm.streamTasks.push(emptyTask[0]);
            }
        }

        function startStream() {
            vm.options.progress = true;
            vm.options.summary = true;
            //vm.options['loglevel'] = 'info';
            vm.options['entry_dump'] = true;

            stream = executeService.executeTasks(vm.options);

            stream.log(logNode)
                .progress(progressNode)
                .summary(summaryNode)
                .entryDump(entryDumpNode)
                .tasks(setTasks);
            
            function setTasks(taskData) {
                sortStreamTasks(taskData);
            }

            function progressNode(progress) {
                var filtered = $filter('filter')(vm.streamTasks, { status: '!complete' });
                angular.extend(filtered[0], progress);
                updateProgress();
            }

            function summaryNode(summary) {
                var filtered = $filter('filter')(vm.streamTasks, { status: 'complete' });
                angular.extend(filtered[filtered.length - 1], summary);
                updateProgress();
            }

            function entryDumpNode(entries) {
                var filtered = $filter('filter')(vm.streamTasks, { status: 'complete' });
                angular.extend(filtered[filtered.length - 1], { entries: entries });
            }

            function logNode(log) {
                $log.log(log);
            }
        }

        function clear() {
            if (stream) {
                stream.abort();
            }
            vm.stopStream();
        }

        function updateProgress() {
            var totalPercent = 0;
            for (var i = 0; i < vm.streamTasks.length; i++) {
                totalPercent = totalPercent + vm.streamTasks[i].percent;
            }
            vm.streamProgress = totalPercent / vm.streamTasks.length;
        }
    }
}());