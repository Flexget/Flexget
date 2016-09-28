/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.seen')
        .factory('seenService', seenService);

    function seenService($http, $q, exception) {
        return {
            getSeen: getSeen,
            deleteEntryById: deleteEntryById
        };

        function getSeen() {
            return $http.get('/api/seen/', { etagCache: true })
                .then(getSeenComplete)
                .catch(callFailed);
                
            function getSeenComplete(response) {
                return response.data;
            }
        }

        function deleteEntryById(id) {
            return $http.delete('/api/seen/' + id + '/')
                .catch(callFailed);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());