(function () {
  'use strict';

  angular
    .module('flexget.plugins.schedule')
    .component('scheduleView', {
      templateUrl: 'plugins/schedule/schedule.tmpl.html',
      controllerAs: 'vm',
      controller: scheduleController,
    });

  function scheduleController($http) {
    var vm = this;

    vm.title = 'Schedules';
    vm.description = 'Task execution';

    vm.form = [
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
    };

    $http.get('/api/schema/config/schedules/').
      success(function (data, status, headers, config) {
        // schema-form doesn't allow forms with an array at root level
        vm.schema = {type: 'object', 'properties': {'schedules': data}, required: ['schedules']};
      }).
        error(function (data, status, headers, config) {
          // log error
        });
        $http.get('/api/schedules/').
          success(function (data, status, headers, config) {
            vm.models = [data];
          }).
            error(function (data, status, headers, config) {
              // log error
            });
  }

})();
