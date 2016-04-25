(function () {
    'use strict';

    angular.module('flexget.services')
        .factory('seriesService', seriesService);

    function seriesService($http, CacheFactory, $mdDialog, errorService) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('seriesCache')) {
            CacheFactory.createCache('seriesCache');
        }

        var seriesCache = CacheFactory.get('seriesCache');

        return {
            getShows: getShows,
            deleteShow: deleteShow,
            searchShows: searchShows
        }

        function getShows(options) {
            return $http.get('/api/series/',
                {
                    cache: seriesCache,
                    params: options
                })
                .then(getShowsComplete)
                .catch(callFailed);

            function getShowsComplete(response) {
                return response.data;
            }
        }

        function deleteShow(show) {
            //TODO: Prob add warning messages again

            return $http.delete('/api/series/' + show.show_id,
                {
                    params: { forget: true }
                })
                .then(deleteShowComplete)
                .catch(callFailed)

            function deleteShowComplete() {
                // remove all shows from cache, since order might have changed
                seriesCache.removeAll();
                return;
            }
        }

        function searchShows(searchTerm) {
            return $http.get('/api/series/search/' + searchTerm)
                .then(searchShowsComplete)
                .catch(callFailed);

            function searchShowsComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
            //TODO: handle error

            console.log(error);

            errorService.showToast(error);
        }
    }
})();
