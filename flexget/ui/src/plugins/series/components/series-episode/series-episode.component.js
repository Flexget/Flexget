(function () {
    'use strict';

    angular
    .module('flexget.plugins.series')
    .component('seriesEpisode', {
        templateUrl: 'plugins/series/components/series-episode/series-episode.tmpl.html',
        controllerAs: 'vm',
        controller: seriesEpisodeController,
        bindings: {
            episode: '<',
            show: '<',
            deleteEpisode: '&',
            resetReleases: '&'
        },
    });

    function seriesEpisodeController($mdDialog, $http, $stateParams, $filter){
        var vm = this;


        vm.showReleases = function () {

            var dialog = {
                template: '<episode-releases show="vm.show" episode="vm.episode" releases="vm.releases"></episode-releases>',
                locals: {
                    show: vm.show,
                    episode: vm.episode,
                    releases: vm.releases
                },
                bindToController: true,
                controllerAs: 'vm',
                controller: function () {}
            }

            $mdDialog.show(dialog);

        }

        //Call from the page, to delete all releases
        vm.deleteReleases = function() {
            var confirm = $mdDialog.confirm()
            .title('Confirm deleting releases.')
            .htmlContent("Are you sure you want to delete all releases for <b>" + vm.episode.episode_identifier + "</b> from show <b>" + vm.show.show_name + "</b>?<br /> This also removes all seen releases for this episode!")
            .ok("Forget")
            .cancel("No");

            $mdDialog.show(confirm).then(function() {
                $http.delete('/api/series/' + vm.show.show_id + '/episodes/' + vm.episode.episode_id + '/releases', { params: { forget: true}})
                .success(function(data) {
                    //Remove all loaded releases from the page and set variables for the accordion
                    vm.releases = undefined;
                })
                .error(function(error) {
                    var errorDialog = $mdDialog.alert()
                    .title("Something went wrong")
                    .htmlContent("Oops, something went wrong when trying to forget <b>" + vm.episode.episode_identifier + "</b> from show " + vm.show.show_name + ":<br />" + error.message)
                    .ok("Ok");

                    $mdDialog.show(errorDialog);
                });
            });
        }

    }
})();
