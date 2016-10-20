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
                .catch(handleDisabledSchedules);
            
            function handleDisabledSchedules(response) {
                return response.status === 409 ? {} : callFailed(response);
            }
        }

        function callComplete(response) {
            return response.data;
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());