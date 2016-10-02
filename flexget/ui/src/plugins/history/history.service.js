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

        function getHistory(options) {
            return $http.get('/api/history/', { params: options, etagCache: true })
                .then(callComplete)
                .catch(callFailed);
        }

        function getHistoryForTask(params) {
            return $http.get('/api/history/', { params: params, etagCache: true })
                .then(callComplete)
                .catch(callFailed);
        }
                
        function callComplete(response, itemCache) {
            var values = {
                data: response.data,
                headers: response.headers()
            }
            return values;
        }
        
        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());