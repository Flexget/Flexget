(function () {
    'use strict';

    angular.module('plugins.seen')
        .factory('seenService', historyService);

    function historyService($http, CacheFactory, exception) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('seenCache')) {
            CacheFactory.createCache('seenCache');
        }

        var seenCache = CacheFactory.get('seenCache');

        return {
            getSeen: getSeen
        }

        function getSeen(params) {
            return $http.get('/api/seen/', { cache: seenCache, params: params })
                .then(getSeenComplete)
                .catch(callFailed);

            function getSeenComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
			return exception.catcher(error);
        }
    }
})();