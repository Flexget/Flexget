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

		function activate() {
			loadMetadata();
		};

		function loadMetadata() {
            seriesService.getShowMetadata(vm.show)
				.then(function (data) {
					vm.show.metadata = data;
				});
		};


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


        //Cat from the page, to open a dialog to set the begin
       /* vm.setBegin = function (ev) {
            var params = {
                episode_identifier: vm.show.begin_episode.episode_identifier
            }

            showDialog(params).then(function (data) {
                if (data) vm.show.begin_episode = data.begin_episode;
            }, function (err) {
                console.log(err);
            });*/

            /*$mdDialog.show({
            controller: 'seriesBeginController',
            controllerAs: 'vm',
            templateUrl: 'plugins/series/components/series-begin/series-begin.tmpl.html',
            locals: {
            showId: vm.show.show_id
        }
			}).then(function(data) {
			vm.show.begin_episode = data;
		}, function(err) {
		console.log(err);
		});*/
		
	}
})();