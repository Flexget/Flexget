(function () {
    'use strict';

    angular.module('flexget.plugins.series')
        .controller('seriesController', seriesController);

    function seriesController($scope, $http, $state, $mdDialog) {
        var vm = this;

        var options = {
            page: 1,
            page_size: 10,
            in_config: 'all'
        }

        vm.searchTerm = "";

        function getSeriesList() {
            $http.get('/api/series/', { params: options })
                .success(function(data) {
                    vm.series = data.shows;
                    vm.currentPage = data.page;
                    vm.totalPages = data.total_number_of_pages;

                    getMetadata(data.shows[0].show_name);
                });
        }

        function getMetadata(show) {
            $http.get('/api/tvdb/' + vm.series[0].show_name)
                .success(function(data) {
                    vm.series[0].metadata = data;
                })
                .error(function(error) {
                    console.log(error);
                });
        }

        vm.updateListPage = function(index) {
            options.page = index;

            getSeriesList();
        }

        vm.search = function() {
            $http.get('/api/series/search/' + vm.searchTerm, { params: options })
                .success(function(data) {
                    vm.series = data.shows;
                });
        }

        getSeriesList();

        vm.gotoEpisodes = function(id) {
            $state.go('flexget.episodes', { id: id });
        };

        vm.forgetSeries = function(show) {
            var confirm = $mdDialog.confirm()
                .title('Confirm forgetting show.')
                .htmlContent("Are you sure you want to completely forget <b>" + show.show_name + "</b>?")
                .ok("Forget")
                .cancel("No");

            $mdDialog.show(confirm).then(function() {
                $http.delete('/api/series/' + show.show_id)
                    .success(function(data) {
                        var index = vm.series.indexOf(show);
                        vm.series.splice(index, 1);
                    })
                    .error(function(error) {
                        var errorDialog = $mdDialog.alert()
                            .title("Something went wrong")
                            .htmlContent("Oops, something went wrong when trying to forget <b>" + show.show_name + "</b>:\n" + error.message)
                            .ok("Ok");

                        $mdDialog.show(errorDialog);
                    })
            });
        }

        $scope.$watch(function watchScope(scope) {
            return (vm.searchTerm);
        }, function(oldValue, newValue) {
            if(oldValue !== newValue) {
                vm.search();
            }
        });
    }

})();