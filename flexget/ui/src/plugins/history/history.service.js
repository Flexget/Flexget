/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.history')
        .factory('historyService', historyService);

    function historyService($http, exception) {
        return {
            getHistory: getHistory
        };

        function getHistory(options) {
            return $http.get('/api/history/', {
                params: options,
                etagCache: true
            })
                .catch(callFailed);
        }
        
        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());