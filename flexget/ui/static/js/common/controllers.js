'use strict';

app.controller('flexgetCtrl', function($scope, $http, $mdSidenav, $state, $mdDialog) {

  $scope.toggleMenu = function() {
    if ($mdSidenav('left').isLockedOpen()) {
      $scope.menuMini = !$scope.menuMini;
    } else {
      $scope.menuMini = false;
      $mdSidenav('left').toggle();
    }
  };

  /* Shortcut to go a page (route) */
  $scope.go = function(state) {
    $state.go(state);
  };

  /* Reload Flexget config file */
  $scope.reload = function() {
    $mdDialog.show({
      template: '<md-dialog aria-label="Reloading Config">' +
      '  <md-dialog-content>' +
      ' <h2>Reloading Config</h2>' +
      '    <div layout="row" layout-align="center center">' +
      '      <md-progress-circular md-diameter="30" class="md-primary" md-mode="indeterminate"></md-progress-circular>' +
      '     </div>' +
      '  </md-dialog-content>' +
      '</md-dialog>'
    });

    $http.get('/api/server/reload/').
      success(function(data, status, headers, config) {
        $mdDialog.hide();
        var alert = $mdDialog.alert()
          .parent(angular.element(document.body))
          .title('Reload')
          .content('Flexget config file successfully reloaded.')
          .ok('Ok');
        $mdDialog.show(alert);
      }).
      error(function(data, status, headers, config) {
        $mdDialog.hide();
        $mdDialog.show(
          $mdDialog.alert()
            .parent(angular.element(document.body))
            .title('Reload')
            .clickOutsideToClose(true)
            .content('Error reloading ' + data.error)
            .ok('Ok')
        )
      });
  };

  var do_shutdown = function() {
    window.stop(); // Kill any http connection
    $mdDialog.show({
      template: '<md-dialog aria-label="Shutting Down">' +
      '  <md-dialog-content>' +
      ' <h2>Shutting Down</h2>' +
      '    <div layout="row" layout-align="center center">' +
      '      <md-progress-circular md-diameter="30" class="md-primary" md-mode="indeterminate"></md-progress-circular>' +
      '     </div>' +
      '  </md-dialog-content>' +
      '</md-dialog>'
    });

    var shutdownStatus = $mdDialog.alert()
      .parent(angular.element(document.body))
      .title('Shutdown')
      .clickOutsideToClose(true)
      .content('Flexget shutdown')
      .ok('Ok');

    $http.get('/api/server/shutdown/').
      success(function(data, status, headers, config) {
        $mdDialog.hide();
        $mdDialog.show(shutdownStatus);
      }).
      error(function(data, status, headers, config) {
        $mdDialog.hide();
        shutdownStatus.content('Error shutting down ' + data.error)
        $mdDialog.show(shutdownStatus);
      });
  };

  $scope.shutdown = function() {
    var confirm = $mdDialog.confirm()
      .parent(angular.element(document.body))
      .title('Shutdown')
      .content('Are you sure you want to shutdown Flexget?')
      .ok('Shutdown')
      .cancel('Cancel');
    $mdDialog.show(confirm).then(function() {
      do_shutdown();
    });

  };

});
