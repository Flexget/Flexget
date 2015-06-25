'use strict';

var historyModule = angular.module("historyModule", []);
registerFlexModule(historyModule);

historyModule.controller('HistoryCtrl', function($scope, $http) {
  $scope.title = 'History';
  $http.get('/api/history').
    success(function(data, status, headers, config) {
      $scope.entries = data['items'];
    }).
    error(function(data, status, headers, config) {
      // log error
    });
});
