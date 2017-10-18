/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.schedule')
        .component('scheduleView', {
            templateUrl: 'plugins/schedule/schedule.tmpl.html',
            controllerAs: 'vm',
            controller: scheduleController
        });

    function scheduleController(schedulesService) {
        var vm = this;

        vm.$onInit = activate;

        /*vm.form = [
            '*',
            {
                type: 'submit',
                title: 'Save'
            }
        ];

        vm.onSubmit = function (form) {
            // First we broadcast an event so all fields validate themselves
            vm.$broadcast('schemaFormValidate');

            // Then we check if the form is valid
            if (form.$valid) {
                alert('test');
                // ... do whatever you need to do with your data.
            }
        };*/

        /*schema.get('config/schedules').then(function (schema) {
            vm.schema = { type: 'object', 'properties': { 'schedules': schema }, required: ['schedules'] };
        });*/

        function activate() {
            getSchedules();
        }

        function getSchedules() {
            schedulesService.getSchedules()
                .then(setSchedule)
                .cached(setSchedule);
        }
        
        function setSchedule(response) {
            vm.models = response.data;
        }
    }
}());