(function () {
    'use strict';

    angular.module('flexget.services')
        .run(serverConfig);

    function serverConfig(toolBar, server, Dialog) {

        var reload = function () {
            server.reload()
                .success(function() {
                    var options = {
                        title: "Reload success",
                        body: "Your config file has been successfully reloaded.",
                        ok: "Ok"
                    }
                    Dialog.open(options);
                })
                .error(function(data, status, headers, config) {
                    var options = {
                        title: "Reload failed",
                        body: "Oops, something went wrong: " + data.error,
                        ok: "Ok"
                    }
                    Dialog.open(options);
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
