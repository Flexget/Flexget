/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.schedule')
        .factory('schedulesService', schedulesService);

    function schedulesService($http, exception) {
        return {
            getSchedules: getSchedules
        };

        function getSchedules() {
            return $http.get('/api/schedules/', { etagCache: true })
                .then(callComplete)
                .catch(callFailed);
        }

        function callComplete(response) {
            return response.data;
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());