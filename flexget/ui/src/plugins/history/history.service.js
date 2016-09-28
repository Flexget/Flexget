/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .factory('historyService', historyService);

    function historyService($http, exception) {
        return {
            getHistory: getHistory,
            getHistoryForTask: getHistoryForTask
        };

        function getHistory() {
            return $http.get('/api/history/', { etagCache: true })
                .then(callComplete)
                .catch(callFailed);
        }

        function getHistoryForTask(params) {
            return $http.get('/api/history/', { params: params, etagCache: true })
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