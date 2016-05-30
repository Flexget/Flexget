(function () {

    'use strict';

    angular
        .module('flexget.plugins.series')
        .component('seriesView', {
            templateUrl: 'plugins/series/series.tmpl.html',
            controllerAs: 'vm',
            controller: seriesController,
        });

    function seriesController($http, $mdDialog, seriesService, $timeout, $mdMedia) {
        var vm = this;

        var options = {
            page: 1,
            page_size: 10,
            in_config: 'all',
            sort_by: 'show_name'
        }

        vm.searchTerm = "";

        function getSeriesList() {
            seriesService.getShows(options).then(function (data) {
                vm.series = data.shows;

                vm.currentPage = data.page;
                vm.totalShows = data.total_number_of_shows;
                vm.pageSize = data.page_size;
            });
        }

        vm.forgetShow = function (show) {
			var confirm = $mdDialog.confirm()
                .title('Confirm forgetting show.')
                .htmlContent("Are you sure you want to completely forget <b>" + show.show_name + "</b>?<br /> This will also forget all downloaded releases.")
                .ok("Forget")
                .cancel("No");

			$mdDialog.show(confirm).then(function () {
				seriesService.deleteShow(show).then(function (data) {
					getSeriesList();
				});
			});
		};


        /*vm.forgetShow = function (show) {
            //Construct the confirmation dialog
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting show.')
                .htmlContent("Are you sure you want to completely forget <b>" + show.show_name + "</b>?<br /> This will also forget all downloaded releases.")
                .ok("Forget")
                .cancel("No");

            //Actually show the confirmation dialog and place a call to DELETE when confirmed
            $mdDialog.show(confirm).then(function () {
                $http.delete('/api/series/' + show.show_id, { params: { forget: true } })
                    .success(function (data) {
                        var index = vm.series.indexOf(show);
                        vm.series.splice(index, 1);
                    })
                    .error(function (error) {

                        //Show a dialog when something went wrong, this will change in the future to more generic error handling
                        var errorDialog = $mdDialog.alert()
                            .title("Something went wrong")
                            .htmlContent("Oops, something went wrong when trying to forget <b>" + show.show_name + "</b>:\n" + error.message)
                            .ok("Ok");

                        $mdDialog.show(errorDialog);
                    })
            });
        }*/


        //Call from the pagination to update the page to the selected page
        vm.updateListPage = function (index) {
            options.page = index;

            getSeriesList();
        }


        vm.search = function () {
            if (vm.searchTerm) {
                seriesService.searchShows(vm.searchTerm).then(function (data) {
                    vm.series = data.shows;
                });
            } else {
                options.page = 1;
                getSeriesList();
            }
        }

        vm.showEpisodes = function (show) {
            if (show !== vm.selectedShow) {
                $timeout(function () {
                    vm.selectedShow = show;
                }, 10);
            };
			vm.selectedShow = null;
        }

        vm.hideEpisodes = function () {
            vm.selectedShow = null;
        }

        vm.areEpisodesOnShowRow = function (show, index) {
            if (!show) return false;

            var numberOfColumns = 1;

            if ($mdMedia('gt-md')) numberOfColumns = 2;
            if ($mdMedia('gt-lg')) numberOfColumns = 3;

            var isOnRightRow = true;

            var column = index % numberOfColumns;
            var row = (index - column) / numberOfColumns;


            var showIndex = vm.series.indexOf(show);
            var showColumn = showIndex % numberOfColumns;
            var showRow = (showIndex - showColumn) / numberOfColumns;

            if (row !== showRow) isOnRightRow = false;
            if (column !== numberOfColumns - 1) isOnRightRow = false;
            if (showIndex === index && index === (vm.series.length - 1)) isOnRightRow = true;

            return isOnRightRow;
        }

        //Load initial list of series
        getSeriesList();
    }

})();
