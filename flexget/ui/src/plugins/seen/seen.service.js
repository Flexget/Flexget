(function () {
    'use strict';

    angular
		.module('plugins.seen')
        .factory('seenService', seenService);

    function seenService($http, CacheFactory, exception) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('seenCache')) {
            CacheFactory.createCache('seenCache');
        }

        var seenCache = CacheFactory.get('seenCache');

        return {
            getSeen: getSeen
        }

        function getSeen() {
            return $http.get('/api/seen/', { cache: seenCache })
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