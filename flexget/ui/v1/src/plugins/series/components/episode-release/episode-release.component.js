/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .component('episodeRelease', {
            templateUrl: 'plugins/series/components/episode-release/episode-release.tmpl.html',
            controllerAs: 'vm',
            controller: episodesReleaseController,
            bindings: {
                show: '<',
                episode: '<',
                release: '<'
            }
        });

    function episodesReleaseController($mdDialog, $sce, seriesService) {
        var vm = this;

        vm.cancel = cancel;
        vm.resetRelease = resetRelease;
        vm.forgetRelease = forgetRelease;

        var params = {
            forget: true
        };

        //Call from a release item, to reset the release
        function resetRelease() {
            var confirm = $mdDialog.confirm()
                .title('Confirm resetting a release')
                .htmlContent($sce.trustAsHtml('Are you sure you want to reset the release <b>' + vm.release.title + '</b>?'))
                .ok('reset')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                seriesService.resetRelease(vm.show, vm.episode, vm.release);
            });
        }

        //Call from a release item, to forget the release
        function forgetRelease() {
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting a release')
                .htmlContent($sce.trustAsHtml('Are you sure you want to delete the release <b>' + vm.release.title + '</b>?'))
                .ok('Forget')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                seriesService.forgetRelease(vm.show, vm.episode, vm.release, params);
            });
        }

        function cancel() {
            $mdDialog.cancel();
        }
    }
}());