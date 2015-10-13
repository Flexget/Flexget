(function () {
  'use strict';

  var historyModule = angular.module("historyModule", ['angular.filter']);
  registerModule(historyModule);

  historyModule.run(function(route, sideNav) {
    route.register('history', '/history', 'HistoryCtrl', 'plugin/history/static/index.html');
    sideNav.register('/history', 'History', 'fa fa-history', 128);
  });

  historyModule.controller('HistoryCtrl', function ($scope, $http) {
    $scope.title = 'History';
    $http.get('/api/history').
      success(function (data, status, headers, config) {
        $scope.entries = data['items'];
      }).
      error(function (data, status, headers, config) {
        // log error
      });
  });
})();