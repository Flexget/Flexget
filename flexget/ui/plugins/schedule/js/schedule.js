'use strict';

var scheduleModule = angular.module('scheduleModule', ['schemaForm']);
registerFlexModule(scheduleModule);

register_route('schedule', '/schedule', 'SchedulesCtrl', 'plugin/schedule/static/index.html');
register_menu('/schedule', 'Schedule', 'fa fa-calendar', 128);

scheduleModule.controller('SchedulesCtrl', function($scope, $http) {
  $scope.title = 'Schedules';
  $scope.description = 'Task execution';

  $scope.form = [
    '*',
    {
      type: 'submit',
      title: 'Save'
    }
  ];

  $scope.onSubmit = function(form) {
    // First we broadcast an event so all fields validate themselves
    $scope.$broadcast('schemaFormValidate');

    // Then we check if the form is valid
    if (form.$valid) {
      alert('test');
      // ... do whatever you need to do with your data.
    }
  };

  $http.get('/api/schema/config/schedules').
    success(function(data, status, headers, config) {
      // schema-form doesn't allow forms with an array at root level
      $scope.schema = {type: 'object', 'properties': {'schedules': data}, required: ['schedules']};
    }).
    error(function(data, status, headers, config) {
      // log error
    });
  $http.get('/api/schedules').
    success(function(data, status, headers, config) {
      $scope.models = [data];
    }).
    error(function(data, status, headers, config) {
      // log error
    });
});
