/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .component('executeView', {
            templateUrl: 'plugins/execute/execute.tmpl.html',
            controllerAs: 'vm',
            controller: executeController
        });

    function executeController($interval, executeService) {
        var vm = this;

        vm.$onInit = activate;
        vm.$onDestroy = destroy;
        vm.execute = execute;
        vm.stopStream = stopStream;
        
        vm.streaming = false;
        vm.tasks = [];

        var taskInterval;

        function activate() {
            getRunning();
            getTasks();

            taskInterval = $interval(getRunning, 3000);
        }

        function getRunning() {
            executeService.getQueue().then(function (data) {
                vm.running = data;
            });
        }

        function getTasks() {
            var params = {
                include_config: false
            }

            executeService.getTasks(params)
                .then(setTasks)
                .cached(setTasks);
        }
            
        function setTasks(response) {
            for (var i = 0; i < response.data.length; i++) {
                vm.tasks.push(response.data[i]);
            }
        }

        function execute(options, tasks) {
            options.tasks = tasks;

            vm.options = options;
            vm.streaming = true;
        }

        function stopStream() {
            delete vm.options;
            vm.streaming = false;
        }

        function destroy() {
            $interval.cancel(taskInterval);
        }
    }
}());