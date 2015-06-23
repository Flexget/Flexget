'use strict';

var scheduleModule = angular.module("scheduleModule", ['schemaForm']);

angular.module('flexgetApp').requires.push('scheduleModule');

scheduleModule.controller('SchedulesCtrl', function($scope) {
  $scope.schema = {
    type: "object",
    additionalProperties: false,
    required: [
      "tasks"
    ],
    properties: {
      name: { type: "string", minLength: 2, title: "Name", description: "Name or alias" },
      tasks: {'type': 'array', 'items': {'type': 'string'}}
    }
  };



  $scope.form = [
    "*",
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

  $scope.models = [
    {name: 'test', bah: 'asasa'},
    {}
  ];
});
