'use strict';

app.controller('flexgetCtrl', ['$scope', '$http', 'modalService', function($scope, $http, modalService) {
  $scope.reload = function() {
    var modalOptions = {
      headerText: 'Reload',
      bodyText: 'Flexget config file successfully reloaded',
      size: 'sm',
      closeText: null
    };

    $http.get('/api/server/reload/').
      success(function(data, status, headers, config) {
        modalService.showModal(modalOptions)
      }).
      error(function(data, status, headers, config) {
        modalOptions.bodyText = 'Error reloading ' + data.error;
        modalService.showModal(modalOptions)
      });
  };

  $scope.shutdown = function() {
    var modalOptions = {
      headerText: 'Shutdown',
      bodyText: 'Flexget shutting down',
      size: 'sm',
      closeText: null
    };

    $http.get('/api/server/shutdown/').
      success(function(data, status, headers, config) {
        modalService.showModal(modalOptions)
      }).
      error(function(data, status, headers, config) {
        modalOptions.bodyText = 'Error shutting down ' + data.error;
        modalService.showModal(modalOptions)
      });
  };
}]);
