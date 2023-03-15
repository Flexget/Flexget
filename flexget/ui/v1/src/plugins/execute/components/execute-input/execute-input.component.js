/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .component('executeInput', {
            templateUrl: 'plugins/execute/components/execute-input/execute-input.tmpl.html',
            controllerAs: 'vm',
            controller: executeInputController,
            bindings: {
                running: '<',
                execute: '<',
                tasks: '<'
            }
        });

    function executeInputController(executeService) {
        var vm = this;

        vm.searchTask = searchTask;
        vm.startExecute = startExecute;

        vm.searchTerm = '';
        vm.selectedTasks = [];

        var options = [
            {
                name: 'learn',
                value: false,
                help: 'matches are not downloaded but will be skipped in the future',
                display: 'Learn'
            },
            {
                name: 'no_cache',
                value: false,
                help: 'disable caches. works only in plugins that have explicit support',
                display: 'Caching'
            },
            {
                name: 'disable_tracking',
                value: false,
                help: 'disable episode advancement for this run',
                display: 'Tracking'
            },
            {
                name: 'discover_now',
                value: false,
                help: 'immediately try to discover everything',
                display: 'Discover'
            },
            {
                name: 'now',
                value: false,
                help: 'run task(s) even if the interval plugin would normally prevent it',
                display: 'Now'
            }
        ];
        vm.options = options;

        function searchTask() {
            var filter = function () {
                var lowercaseQuery = angular.lowercase(vm.searchTerm);
                return function filterFn(task) {
                    return (angular.lowercase(task).indexOf(lowercaseQuery) > -1);
                };
            };

            var results = vm.searchTerm ? vm.tasks.filter(filter()) : [];
            return results;
        }

        function startExecute() {
            var opts = {};
            vm.options.map(function (option) {
                opts[option.name] = option.value;
            });
            vm.execute(opts, vm.selectedTasks);
        }
    }
}());