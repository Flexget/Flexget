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
            // currently angular-http-etag returns a .cached function, which holds the cached data, so we need to wrap our http method in $q
            // I'm planning on changing the dependency, so that the cached data gets returned in the .then callback, removing the need for $q

            // IMPORTANT!
            // the module currently has a bug, where the cached data gets returned without waiting/validating the server's response
            // This means the shown data is not correct after it has been cached, until this bug gets fixed: https://github.com/shaungrady/angular-http-etag/issues/45
            return $q(function (resolve, reject) {
                $http.get('/api/seen/', { etagCache: true })
                    .then(getSeenComplete)
                    .cached(getCachedComplete)
                    .catch(callFailed);
                
                function getSeenComplete(response) {
                    resolve(response.data);
                }

                function getCachedComplete(data) {
                    resolve(data);
                }
            });
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