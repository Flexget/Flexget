/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .factory('historyService', historyService);

    function historyService($http, CacheFactory, exception) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('historyCache')) {
            CacheFactory.createCache('historyCache');
        }

        var historyCache = CacheFactory.get('historyCache');

        return {
            getHistory: getHistory,
            getHistoryForTask: getHistoryForTask
        };

        function getHistory() {
            return $http.get('/api/history/', { cache: historyCache })
                .then(getHistoryComplete)
                .catch(callFailed);

            function getHistoryComplete(response) {
                return response.data;
            }
        }

        function getHistoryForTask(params) {
            return $http.get('/api/history/', { params: params, cache: historyCache })
                .then(getHistoryForTaskComplete)
                .catch(callFailed);
            
            function getHistoryForTaskComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());