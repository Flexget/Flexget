/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .component('seriesEpisodesView', {
            templateUrl: 'plugins/series/components/series-episodes/series-episodes.tmpl.html',
            controllerAs: 'vm',
            controller: episodesController,
            bindings: {
                show: '<'
            },
            transclude: true
        });

    function episodesController($mdDialog, $sce, seriesService) {
        var vm = this;

        vm.$onInit = activate;
        vm.deleteEpisode = deleteEpisode;

        var options = {
            page: 1,
            'per_page': 10
        };

        var params = {
            forget: true
        };

        function activate() {
            getEpisodesList();
        }

        //Call from the pagination directive, which triggers other episodes to load
        vm.updateListPage = function (index) {
            options.page = index;

            getEpisodesList();
        };

        //Cal the episodes based on the options
        function getEpisodesList() {
            seriesService.getEpisodes(vm.show, options)
                .then(setEpisodes)
                .cached(setEpisodes);
        }
        
        function setEpisodes(response) {
            //Set the episodes in the vm scope to the loaded episodes
            vm.episodes = response.data;
        }

        //action called from the series-episode component
        function deleteEpisode(episode) {
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting episode.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to forget episode <b>' + episode.identifier + '</b> from show <b>' + vm.show.name + '</b>?<br /> This also removes all downloaded releases for this episode!'))
                .ok('Forget')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                seriesService.deleteEpisode(vm.show, episode, params)
                    .then(function () {
                        getEpisodesList();
                    });
            });
        }
    }
}());