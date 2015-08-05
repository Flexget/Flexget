'use strict';

var scheduleModule = angular.module("scheduleModule", ['schemaForm']);
registerFlexModule(scheduleModule);

scheduleModule.controller('SchedulesCtrl', function($scope, $http) {
  $scope.title = 'Schedules';
  $scope.description = 'Task execution';
  $scope.type = "interval";
  // TODO: this needs to be per array element instead of global (or have native oneOf support)
  $scope.onTypeChange = function(key, form) {
    $scope.type = key;
  };

  $scope.form = [
    {
      key: "schedules",
      add: "Add New Schedule!",
      type: "array",
      items: [
        "schedules[].tasks",
        {
          type: "select",
          title: "Interval Type",
          onChange: $scope.onTypeChange,
          // TODO: This element should have something selected by default
          titleMap: [
            {name: "Simple", value: "interval"},
            {name: "Cron Style", value: "schedule"}
          ]

        },
        {
          key: "schedules[].interval",
          condition: "type == 'interval'"
          // TODO: Should really be unit and value choice, rather than list all the units (proper oneOf would also do)
        },
        {
          key: "schedules[].schedule",
          condition: "type == 'schedule'"
        }
      ]
    },
    {
      type: "submit",
      title: "Save"
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
