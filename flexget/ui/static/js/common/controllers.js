'use strict';

app.controller('flexgetCtrl', function($scope, $http, $mdSidenav, $state) {

  $scope.toggleMenu = function() {
    if ($mdSidenav('left').isLockedOpen()) {
      $scope.menuMini = !$scope.menuMini;
    } else {
      $scope.menuMini = false;
      $mdSidenav('left').toggle();
    }
  };

  $scope.go = function(state) {
    $state.go(state);
  };

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
    var modal = {
      headerText: 'Shutdown',
      bodyText: 'Are you sure you want to shutdown flexget?',
      size: 'sm',
      okText: 'Shutdown',
      okType: 'danger',
      closeText: 'Cancel'
    };

    modalService.showModal(modal).then(function (result) {
      $http.get('/api/server/shutdown/').
        success(function(data, status, headers, config) {
          modalService.showModal({
              headerText: 'Shutdown',
              size: 'sm',
              closeText: null,
              bodyText: 'Flexget shutdown'}
          )
        }).
        error(function(data, status, headers, config) {
          modalService.showModal({
              headerText: 'Shutdown',
              size: 'sm',
              closeText: null,
              bodyText: 'Error shutting down ' + data.error}
          )
        });
    })
  };
});
