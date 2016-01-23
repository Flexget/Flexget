(function () {
    'use strict';
    angular.module("flexget.plugins.history")
        .controller('historyController', historyController);

    function historyController($scope, $http) {
        $scope.title = 'History';
        $http.get('/api/history').
        success(function (data, status, headers, config) {
            $scope.entries = data['items'];
        }).
        error(function (data, status, headers, config) {
            // log error
        });
    }

})();
