(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('seriesService', seriesService);

    function seriesService($http, CacheFactory) {
        return {
            getSeries: getSeries
        }

        function getSeries() {
//TODO: Implement caching complete with clearing handling if operations are performed
            var cache = CacheFactory('testing');

            return $http.get('/api/series/', {cache: cache, params: {
      page: 1,
      page_size: 10,
      in_config: 'all',
      lookup: 'tvdb',
      sort_by: 'show_name'
    }})
                .then(getSeriesComplete)
                .catch(getSeriesFailed);

            function getSeriesComplete(response) {
                console.log(response);

                console.log(CacheFactory.get('testing').keys());
                return response.data;
            }

            function getSeriesFailed(error) {
                //TODO: Log error
            }
        }
    }
})();