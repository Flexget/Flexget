/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.pending')
        .factory('pendingService', pendingService);

    function pendingService($http, exception) {
        return {
            getPending: getPending,
            updatePendingEntry: updatePendingEntry
        };

        function getPending() {
            return $http.get('/api/pending/', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function updatePendingEntry(entryId, operation) {
            return $http.put('/api/pending/' + entryId, {
                operation: operation
            })
                .catch(callFailed);
        }
        
        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());