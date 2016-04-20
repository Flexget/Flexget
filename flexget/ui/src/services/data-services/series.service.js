(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('seriesService', seriesService);

    function seriesService($http, CacheFactory) {
        //CacheFactory('series');

        return {
            getSeries: getSeries
        }

        function getSeries(options) {
            return $http.get('/api/series/', 
                {
                    cache: CacheFactory.get('series'), 
                    params: options
                })
                .then(getSeriesComplete)
                .catch(getSeriesFailed);

            function getSeriesComplete(response) {
                return response.data;
            }

            function getSeriesFailed(error) {
                //TODO: Log error
            }
        }
    }
})();