(function () {
    'use strict';

    angular
		.module('plugins.schedule')
        .factory('schedulesService', schedulesService);

    function schedulesService($http, CacheFactory, exception) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('scheduleCache')) {
            CacheFactory.createCache('scheduleCache');
        }

        var scheduleCache = CacheFactory.get('scheduleCache');

        return {
            getSchedules: getSchedules
        }

        function getSchedules() {
            return $http.get('/api/schedules/', { cache: scheduleCache })
                .then(getSchedulesComplete)
                .catch(callFailed);

            function getSchedulesComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
			return exception.catcher(error);
        }
    }
}());