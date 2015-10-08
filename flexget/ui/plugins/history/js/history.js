(function () {
  'use strict';

  var historyModule = angular.module("historyModule", ['angular.filter']);
  registerModule(historyModule);

  historyModule.config(function(routeProvider, sideNavProvider) {
    routeProvider.register('history', '/history', 'HistoryCtrl', 'plugin/history/static/index.html');
    sideNavProvider.register('/history', 'History', 'fa fa-history', 128);
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