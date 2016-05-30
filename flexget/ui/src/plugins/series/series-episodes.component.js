(function () {
    'use strict';

    angular
    .module('flexget.plugins.series')
    .component('seriesEpisodesView', {
        templateUrl: 'plugins/series/series-episodes.tmpl.html',
        controllerAs: 'vm',
        controller: episodesController,
        bindings: {
            show : '<',
        },
        transclude: true
    });

    function episodesController($http, $mdDialog, seriesService) {
        var vm = this;


        var options = {
            page: 1,
            page_size: 10
        }

        //Call from the pagination directive, which triggers other episodes to load
        vm.updateListPage = function(index) {
            options.page = index;

            getEpisodesList();
        }

        //Cal the episodes based on the options
        function getEpisodesList() {
            seriesService.getEpisodes(vm.show, options)
            .then(function(data) {
                //Set the episodes in the vm scope to the loaded episodes
                vm.show.episodes = data.episodes;


                //set vars for the pagination
                vm.currentPage = data.page;
                vm.show.totalEpisodes = data.total_number_of_episodes;
                vm.pageSize = options.page_size;

            })
            .catch(function(error) {
                //TODO: Error handling
                console.log(error);
            });
        }

        //Load initial episodes
        getEpisodesList();

        //action called from the series-episode component
        vm.deleteEpisode = function(episode) {
            var confirm = $mdDialog.confirm()
            .title('Confirm forgetting episode.')
            .htmlContent("Are you sure you want to forget episode <b>" + episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This also removes all downloaded releases for this episode!")
            .ok("Forget")
            .cancel("No");

            $mdDialog.show(confirm).then(function() {
                seriesService.deleteEpisode(vm.show, episode)
                .then(function(data) {
                    //Find the index of the episode in the data
                    var index = vm.show.episodes.indexOf(episode);
                    //Remove the episode from the list, based on the index
                    vm.show.episodes.splice(index, 1);
                }, function(error) {
                    var errorDialog = $mdDialog.alert()
                    .title("Something went wrong")
                    .htmlContent("Oops, something went wrong when trying to forget <b>" + episode.episode_identifier + "</b> from show " + vm.show.show_name + ":\n" + error.message)
                    .ok("Ok");

                    $mdDialog.show(errorDialog);
                });
            });
        }

        //action called from the series-episode components
        vm.resetReleases = function(episode) {
            var confirm = $mdDialog.confirm()
            .title('Confirm resetting releases.')
            .htmlContent("Are you sure you want to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This does not remove seen entries but will clear the quality to be downloaded again.")
            .ok("Forget")
            .cancel("No");

            $mdDialog.show(confirm).then(function() {
                seriesService.resetReleases(vm.show, episode)
                .then(function(data) {
                    //TODO: Handle reset releases, remove them from view if they are showm
                }, function(error) {
                    var errorDialog = $mdDialog.alert()
                    .title("Something went wrong")
                    .htmlContent("Oops, something went wrong when trying to reset downloaded releases for <b>" + episode.episode_identifier + "</b> from show " + vm.show.show_name + ":<br />" + error.message)
                    .ok("Ok");

                    $mdDialog.show(errorDialog);
                });
            });
        }
    }

})();
