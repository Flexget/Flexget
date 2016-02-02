(function () {
    'use strict';
    angular.module("flexget.plugins.history")
        .controller('historyController', historyController);

    function historyController($http) {
        var vm = this;

        vm.title = 'History';
        $http.get('/api/history').
        success(function (data) {
            vm.entries = data['items'];
        }).
        error(function (data, status, headers, config) {
            // log error
        });
    }

})();
