/* global angular */
(function () {
    'use strict';

    angular
        .module('components.database')
        .factory('databaseService', databaseService);

    function databaseService($http, $mdSidenav, exception) {
        return {
            toggle: toggle,
            getPlugins: getPlugins,
            cleanup: cleanup,
            vacuum: vacuum,
            resetPlugin: resetPlugin
        };

        function toggle() {
            $mdSidenav('database').toggle();
        }

        function getPlugins() {
            return $http.get('/api/database/plugins/', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function cleanup() {
            return $http.post('/api/database/', {
                operation: 'cleanup'
            })
                .then(callSucceeded)
                .catch(callFailed);
        }

        function vacuum() {
            return $http.post('/api/database/', {
                operation: 'vacuum'
            })
                .then(callSucceeded)
                .catch(callFailed);
        }

        function resetPlugin(params) {
            return $http.post('/api/database/', {
                operation: 'plugin_reset',
                plugin_name: params
            })
                .then(callSucceeded)
                .catch(callFailed);
        }

        function callSucceeded(response) {
            return response.data;
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());
