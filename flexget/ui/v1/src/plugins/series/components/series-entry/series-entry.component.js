/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .component('seriesEntry', {
            templateUrl: 'plugins/series/components/series-entry/series-entry.tmpl.html',
            controllerAs: 'vm',
            controller: seriesEntryController,
            bindings: {
                show: '<',
                forgetShow: '&',
                toggleEpisodes: '&'
            },
            transclude: true
        });

    function seriesEntryController($mdDialog, seriesService) {
        var vm = this;

        vm.$onInit = activate;
        vm.setBegin = setBegin;

        var dialog = {
            template: '<series-begin-dialog begin=\'vm.begin\' show=\'vm.show\'></series-begin>',
            bindToController: true,
            controllerAs: 'vm',
            controller: function () { }
        };

        function activate() {
            loadMetadata();
        }

        function loadMetadata() {
            seriesService.getShowMetadata(vm.show)
                .then(setMetadata)
                .cached(setMetadata);
        }

        function setMetadata(response) {
            vm.show.metadata = response.data;
        }

        function setBegin() {
            dialog.locals = {
                show: vm.show
            };

            $mdDialog.show(dialog).then(function (begin) {
                if (begin) {
                    vm.show['begin_episode']['identifier'] = begin;
                }
            });
        }


        //Dialog for the update possibilities, such as begin and alternate names
       /* function showDialog(params) {
            return $mdDialog.show({
                controller: 'seriesUpdateController',
                controllerAs: 'vm',
                templateUrl: 'plugins/series/components/series-update/series-update.tmpl.html',
                locals: {
                    showId: vm.show.show_id,
                    params: params
                }
            });
        }*/



        /*//Call from the page, to open a dialog with alternate names
        vm.alternateName = function (ev) {
            var params = {
                alternate_names: vm.show.alternate_names
            }

            showDialog(params).then(function (data) {
                if (data) vm.show.alternate_names = data.alternate_names;
            }, function (err) {
                console.log(err);
            });
        }*/
    }
}());