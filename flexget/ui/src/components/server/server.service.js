(function () {
    'use strict';

    angular.module('flexget.components')
        .service('server', serverService);

    function serverService($http) {
        this.reload = function () {
            return $http.get('/api/server/reload/');
        };

        this.shutdown = function () {
            return $http.get('/api/server/shutdown/')
        };
    }

})();


