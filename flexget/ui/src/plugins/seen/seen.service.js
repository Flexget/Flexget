/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.seen')
        .factory('seenService', seenService);

    function seenService($http, exception) {
        return {
            getSeen: getSeen,
            deleteEntryById: deleteEntryById
        };

        function getSeen(options) {
            return $http.get('/api/seen/', {
                params: options,
                etagCache: true
            })
                .catch(callFailed);
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