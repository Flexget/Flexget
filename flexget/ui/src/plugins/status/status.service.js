/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.status')
        .factory('statusService', statusService);

    function statusService($http, exception) {
        return {
            getStatus: getStatus
        };

        function getStatus() {
            return $http.get('/api/status/', { etagCache: true })
                .catch(callFailed);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());