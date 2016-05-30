(function () {
    'use strict';

    angular.module('flexget.services')
    .factory('seriesService', seriesService);

    function seriesService($http, CacheFactory, exception) {
        // If cache doesn't exist, create it
        if (!CacheFactory.get('seriesCache')) {
            CacheFactory.createCache('seriesCache');
        }

        var seriesCache = CacheFactory.get('seriesCache');

        return {
            getShows: getShows,
            getShowMetadata: getShowMetadata,
            deleteShow: deleteShow,
            searchShows: searchShows,
            getEpisodes: getEpisodes,
            deleteEpisode: deleteEpisode,
            resetReleases: resetReleases,
            forgetRelease: forgetRelease,
            resetRelease: resetRelease,
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


        function getShowMetadata(show) {
            return $http.get('/api/tvdb/series/' + show.show_name + '/', { cache: true })
            .then(getShowMetadataComplete)
            .catch(callFailed);

            function getShowMetadataComplete(res) {
                return res.data;
            }
        }

        function deleteShow(show, params) {

            return $http.delete('/api/series/' + show.show_id + '/',
            {
                params: params
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
            return $http.get('/api/series/search/' + searchTerm + '/')
            .then(searchShowsComplete)
            .catch(callFailed);

            function searchShowsComplete(response) {
                return response.data;
            }
        }

        function getEpisodes(show, params) {
            return $http.get('/api/series/' + show.show_id + '/episodes/', { params: params })
            .then(getEpisodesComplete)
            .catch(callFailed);

            function getEpisodesComplete(res) {
                return res.data;
            }
        }

        function deleteEpisode(show, episode, params) {
            return $http.delete('/api/series/' + show.show_id + '/episodes/' + episode.episode_id + '/', { params: params })
            .then(deleteEpisodeComplete)
            .catch(callFailed)

            function deleteEpisodeComplete(res) {
                return res.data;
            }
        }

        function resetReleases(show, episode) {
            return $http.put('/api/series/' + show.show_id + '/episodes/' + episode.episode_id + '/releases/')
            .then(resetReleasesComplete)
            .catch(callFailed)

            function resetReleasesComplete(res) {
                return res.data;
            }
        }

        function forgetRelease(show, episode, release, params) {
            return $http.delete('/api/series/' + show.show_id + '/episodes/' + episode.episode_id + '/releases/' + release.release_id + '/', { params: params})
            .then(forgetReleaseComplete)
            .catch(callFailed);

            function forgetReleaseComplete(res) {
                return res.data;
            }
        }

        function resetRelease(show, episode, release) {
            return $http.put('/api/series/' + show.show_id + '/episodes/' + episode.episode_id + '/releases/' + release.release_id + '/')
            .then(resetReleaseComplete)
            .catch(callFailed);

            function resetReleaseComplete(data) {
                return data;
            }
        }


        function callFailed(error) {
			return exception.catcher(error);
        }

    }
})();
