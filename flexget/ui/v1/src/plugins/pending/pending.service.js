/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.pending')
        .factory('pendingService', pendingService);

    function pendingService($http, exception) {
        return {
            getPending: getPending,
            updateEntry: updateEntry,
            deleteEntry: deleteEntry
        };

        function getPending() {
            return $http.get('/api/pending/', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function updateEntry(entryId, operation) {
            return $http.put('/api/pending/' + entryId + '/', {
                operation: operation
            })
                .catch(callFailed);
        }

        function deleteEntry(entryId) {
            return $http.delete('/api/pending/' + entryId + '/')
                .catch(callFailed);
        }
        
        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());