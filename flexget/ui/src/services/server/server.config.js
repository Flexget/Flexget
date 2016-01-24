(function () {
    'use strict';

    angular.module('flexget.services')
        .run(serverConfig);

    function serverConfig(toolBar, server, $mdDialog) {

        var reload = function () {
            var reloadController = function ($mdDialog) {
                var vm = this;

                vm.title = 'Reload Config';
                vm.showCircular = true;
                vm.content = null;
                vm.buttons = [];
                vm.ok = null;

                vm.hide = function () {
                    $mdDialog.hide();
                };

                var done = function (text) {
                    vm.showCircular = false;
                    vm.content = text;
                    vm.ok = 'Close';
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
                templateUrl: 'services/modal/modal.dialog.circular.tmpl.html',
                parent: angular.element(document.body),
                controllerAs: 'vm',
                controller: reloadController
            });
        };

        var doShutdown = function () {
            window.stop(); // Kill any http connection

            var shutdownController = function ($mdDialog) {
                var vm = this;

                vm.title = 'Shutting Down';
                vm.showCircular = true;
                vm.content = null;
                vm.buttons = [];
                vm.ok = null;

                vm.hide = function () {
                    $mdDialog.hide();
                };

                var done = function (text) {
                    vm.title = 'Shutdown';
                    vm.showCircular = false;
                    vm.content = text;
                    vm.ok = 'Close';
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
                templateUrl: 'services/modal/modal.dialog.circular.tmpl.html',
                parent: angular.element(document.body),
                controllerAs: 'vm',
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

        toolBar.registerMenuItem('Manage', 'Reload', 'fa fa-refresh', reload);
        toolBar.registerMenuItem('Manage', 'Shutdown', 'fa fa-power-off', shutdown);

    }

})();
