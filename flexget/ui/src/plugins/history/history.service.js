/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .factory('historyService', historyService);

    function historyService($http, $q, exception) {
        return {
            getHistory: getHistory,
            getHistoryForTask: getHistoryForTask
        };

        function getHistory() {
            return $q(function (resolve, reject) {
                $http.get('/api/history/', { etagCache: true })
                    .then(getHistoryComplete)
                    .cached(getCachedComplete)
                    .catch(callFailed);
                
                function getHistoryComplete(response) {
                    resolve(response.data);
                }

                function getCachedComplete(data) {
                    resolve(data);
                }
            });
        }

        function getHistoryForTask(params) {
            return $q(function (resolve, reject) {
                $http.get('/api/history/', { params: params, etagCache: true })
                    .then(getHistoryForTaskComplete)
                    .cached(getCachedComplete)
                    .catch(callFailed);
            
                function getHistoryForTaskComplete(response) {
                    resolve(response.data);
                }

                 function getCachedComplete(data) {
                    resolve(data);
                }
            });
        }
                

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());