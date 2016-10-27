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
            vacuum: vacuum
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
            return $http.get('/api/database/cleanup/')
                .catch(callFailed);;
        }

        function vacuum() {
            return $http.get('/api/database/vacuum/')
                .catch(callFailed);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());