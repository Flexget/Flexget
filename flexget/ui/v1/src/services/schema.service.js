/* global angular */
(function () {
    'use strict';

    angular.module('flexget.services')
        .service('schema', schemaService);

    function schemaService($http) {
        this.get = function (path) {
            // TODO: Add cache?

            if (!path.endsWith('/')) {
                path = path + '/';
            }
            return $http.get('/api/schema/' + path)
                .then(
                function (response) {
                    return response.data;
                },
                function (httpError) {
                    throw httpError.status + ' : ' + httpError.data;
                });
        };

        this.config = function (name) {
            return this.get('config/' + name);
        };

        this.plugin = function (name) {
            return this.get('config/' + name);
        };
    }

});