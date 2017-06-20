/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.server')
        .factory('serverService', serverService);

    function serverService($http, $mdDialog, $window) {
        var dialog = {
            template: '<loading-dialog title=\'vm.title\' action=\'vm.action\'></loading-dialog>',
            bindToController: true,
            controllerAs: 'vm',
            controller: function () { },
            locals: {
                title: 'No title',
                action: null
            }
        };

        return {
            reload: reload,
            shutdown: shutdown
        };

        function reload() {
            dialog.locals.title = 'Config Reloading';
            dialog.locals.action = doReload;
            $mdDialog.show(dialog);
        }

        function shutdown() {
            $mdDialog.show(
                $mdDialog.confirm()
                    .title('Shutdown')
                    .textContent('Are you sure you want to shutdown Flexget?')
                    .ok('Shutdown')
                    .cancel('Cancel')
            ).then(function () {
                dialog.locals.title = 'Shutting Down';
                dialog.locals.action = doShutdown;
                $mdDialog.show(dialog);
            });
        }

        function doReload() {
            return $http.post('/api/server/manage/', {
                operation: 'reload'
            })
                .then(reloadSuccess)
                .catch(reloadFailed);

            function reloadSuccess() {
                var response = {
                    title: 'Reload Success',
                    message: 'Config has been successfully reloaded'
                };
                return response;
            }

            function reloadFailed(error) {
                var response = {
                    title: 'Reload Failed',
                    message: error.data.message
                };
                return response;
            }
        }

        function doShutdown() {
            $window.stop(); //Stop any http connections

            return $http.post('/api/server/manage/', {
                operation: 'shutdown'
            })
                .then(shutdownSuccess)
                .catch(shutdownFailed);

            function shutdownSuccess() {
                var response = {
                    title: 'Shutdown Success',
                    message: 'Flexget has been shutdown'
                };
                return response;
            }

            function shutdownFailed(error) {
                var response = {
                    title: 'Shutdown Failed',
                    message: error.data.message
                };
                return response;
            }
        }
    }
}());
