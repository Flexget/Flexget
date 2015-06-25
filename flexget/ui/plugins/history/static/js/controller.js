'use strict';

var historyModule = angular.module("historyModule", ['schemaForm']);
registerFlexModule(historyModule);

historyModule.controller('HistoryCtrl', function($scope, $http) {
  $http.get('/api/history').
    success(function(data, status, headers, config) {
      $scope.entries = data['items'];
    }).
    error(function(data, status, headers, config) {
      // log error
    });
});
