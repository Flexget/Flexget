(function () {
  'use strict';

  angular.module('flexget.services')
    .service('server', function($http) {
      this.reload = function() {
        return $http.get('/api/server/reload/');
      };

      this.shutdown = function() {
        return $http.get('/api/server/shutdown/')
      };
    });

  var serverPlugin = angular.module("serverPlugin", []);
  registerModule(serverPlugin);

  serverPlugin.run(function(toolBar, server, $mdDialog) {

    var reload = function () {
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

        server.reload()
          .success(function () {
            done('Reload Success');
          })
          . error(function (data, status, headers, config) {
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

        server.shutdown().
          success(function () {
            done('Flexget has been shutdown');
          }).
          error(function (error) {
            done('Flexget failed to shutdown failed: ' + error.message);
          });
      };
      $mdDialog.show({
        templateUrl: 'static/partials/dialog_circular.html',
        parent: angular.element(document.body),
        controller: shutdownController
      });

    };

    var shutdown = function () {
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

    toolBar.registerButton('Reload', 'fa fa-refresh', reload);
    toolBar.registerButton('Shutdown', 'fa fa-power-off', shutdown);

  });
})();


