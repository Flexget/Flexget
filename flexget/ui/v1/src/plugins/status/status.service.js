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

        function getStatus(options) {
            return $http.get('/api/status/', {
                etagCache: true,
                params: options
            })
                .catch(callFailed);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());