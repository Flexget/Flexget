/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.series')
        .component('seriesView', {
            templateUrl: 'plugins/series/series.tmpl.html',
            controllerAs: 'vm',
            controller: seriesController
        });

    function seriesController($mdMedia, $mdDialog, $sce, $timeout, seriesService) {
        var vm = this;

        var options = {
            'per_page': 10,
            'in_config': 'all',
            'sort_by': 'show_name',
            'descending': false
        };

        var params = {
            forget: true
        };

        vm.searchTerm = '';

        vm.$onInit = activate;
        vm.forgetShow = forgetShow;
        vm.search = search;
        vm.toggleEpisodes = toggleEpisodes;
        vm.areEpisodesOnShowRow = areEpisodesOnShowRow;
        vm.getSeries = getSeriesList;

        function activate() {
            getSeriesList(1);
        }

        function getSeriesList(page) {
            options.page = page;
            seriesService.getShows(options)
                .then(setSeries)
                .cached(setSeries)
                .finally(function () {
                    vm.currentPage = options.page;
                });
        }

        function search() {
            vm.searchTerm ? searchShows() : emptySearch();

            function searchShows() {
                seriesService.searchShows(vm.searchTerm)
                    .then(setSeries)
                    .cached(setSeries);
            }

            function emptySearch() {
                options.page = 1;
                getSeriesList(1);
            }
        }

        function setSeries(response) {
            vm.series = response.data;
            vm.linkHeader = response.headers().link;
        }

        function forgetShow(show) {
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting show.')
                .htmlContent($sce.trustAsHtml('Are you sure you want to completely forget <b>' + show.name + '</b>?<br /> This will also forget all downloaded releases.'))
                .ok('Forget')
                .cancel('No');

            $mdDialog.show(confirm).then(function () {
                seriesService.deleteShow(show, params).then(function () {
                    getSeriesList(options.page);
                });
            });
        }

        

        function toggleEpisodes(show) {
            show === vm.selectedShow ? clearShow() : setSelectedShow();

            function clearShow() {
                vm.selectedShow = null;
            }

            function setSelectedShow() {
                vm.selectedShow = null;
                $timeout(function () {
                    vm.selectedShow = show;
                });
            }
        }

        function getNumberOfColumns() {
            if ($mdMedia('gt-lg')) {
                return 3;
            } else if ($mdMedia('gt-md')) {
                return 2;
            }
            return 1;
        }

        function areEpisodesOnShowRow(index) {
            var show = vm.selectedShow;

            if (!show) {
                return false;
            }
            
            var numberOfColumns = getNumberOfColumns();

            var column = index % numberOfColumns;
            var row = (index - column) / numberOfColumns;

            var showIndex = vm.series.indexOf(show);
            var showColumn = showIndex % numberOfColumns;
            var showRow = (showIndex - showColumn) / numberOfColumns;

            if (row !== showRow) {
                return false;
            }

            //Check if not last series, since it doesn't work correctly with the matrix here
            if (index !== vm.series.length - 1 && column !== numberOfColumns - 1) {
                return false;
            }

            return true;
        }
    }
}());
