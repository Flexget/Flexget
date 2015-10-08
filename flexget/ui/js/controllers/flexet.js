(function () {
  'use strict';

  angular.module('flexget').controller('flexgetController', function ($scope, $http, $mdSidenav, $state, $mdMedia, $mdDialog, sideNav) {

    $scope.menuItems = sideNav.items;
    $scope.toggleMenu = function () {
      if ($mdSidenav('left').isLockedOpen()) {
        $scope.menuMini = !$scope.menuMini;
      } else {
        $scope.menuMini = false;
        $mdSidenav('left').toggle();
      }
    };

    $scope.closeNav = function ($event) {
      if (!$mdMedia('gt-lg')) {
        $mdSidenav('left').close();
      }
    };

    /* Shortcut to go a page (route) */
    $scope.go = function (state) {
      $state.go(state);
    };

    /* Reload Flexget config file */
    $scope.reload = function () {
      var reloadController = function ($scope, $mdDialog) {
        $scope.title = 'Reload Config';
        $scope.showCircular = true;
        $scope.content = null;
        $scope.buttons = [];
        $scope.ok = null;

        $scope.hide = function () {
          $mdDialog.hide();
        };

        var done = function (text) {
          $scope.showCircular = false;
          $scope.content = text;
          $scope.ok = 'Close';
        };

        $http.get('/api/server/reload/').
          success(function (data, status, headers, config) {
            done('Reload Success');
          }).
          error(function (data, status, headers, config) {
            done('Reload failed: ' + data.error);
          });
      };

      $mdDialog.show({
        templateUrl: 'static/partials/dialog_circular.html',
        parent: angular.element(document.body),
        controller: reloadController
      });

    };

    var doShutdown = function () {
      window.stop(); // Kill any http connection

      var shutdownController = function ($scope, $mdDialog) {
        $scope.title = 'Shutting Down';
        $scope.showCircular = true;
        $scope.content = null;
        $scope.buttons = [];
        $scope.ok = null;

        $scope.hide = function () {
          $mdDialog.hide();
        };

        var done = function (text) {
          $scope.title = 'Shutdown';
          $scope.showCircular = false;
          $scope.content = text;
          $scope.ok = 'Close';
        };

        $http.get('/api/server/shutdown/').
          success(function (data, status, headers, config) {
            done('Flexget has been shutdown');
          }).
          error(function (data, status, headers, config) {
            done('Flexget failed to shutdown failed: ' + data.error);
          });
      };
      $mdDialog.show({
        templateUrl: 'static/partials/dialog_circular.html',
        parent: angular.element(document.body),
        controller: shutdownController
      });

    };

    $scope.shutdown = function () {
      $mdDialog.show(
        $mdDialog.confirm()
          .parent(angular.element(document.body))
          .title('Shutdown')
          .content('Are you sure you want to shutdown Flexget?')
          .ok('Shutdown')
          .cancel('Cancel')
      ).then(function () {
          doShutdown();
        });

    };

  });
})();