'use strict';

var historyModule = angular.module("historyModule", ['angular.filter']);
registerFlexModule(historyModule);

register_route('history', '/history', 'HistoryCtrl', '/ui/plugin/history/index.html');
register_menu('/history', 'History', 'fa fa-history', 128);

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
