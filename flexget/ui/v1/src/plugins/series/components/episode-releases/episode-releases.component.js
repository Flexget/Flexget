/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .component('episodeReleases', {
            templateUrl: 'plugins/series/components/episode-releases/episode-releases.tmpl.html',
            controllerAs: 'vm',
            controller: episodesReleasesController,
            bindings: {
                show: '<',
                episode: '<'
            }
        });

    function episodesReleasesController($http, $filter, $mdDialog, seriesService) {
        var vm = this;

        vm.$onInit = activate;
        vm.cancel = cancel;

        function activate() {
            loadReleases();
        }

        function loadReleases() {
            seriesService.loadReleases(vm.show, vm.episode)
                .then(setReleases)
                .cached(setReleases);
        }
        
        function setReleases(response) {
            vm.releases = response.data;
        }

        function cancel() {
            $mdDialog.cancel();
        }
    }
}());