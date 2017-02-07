/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.config')
        .factory('configService', configService);

    function configService($http, exception, $q) {
        return {
            getRawConfig: getRawConfig,
            saveRawConfig: saveRawConfig,
            getVariables: getVariables,
            saveVariables: saveVariables
        };

        function getRawConfig() {
            return $http.get('/api/server/raw_config', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function saveRawConfig(encoded) {
            return $http.post('/api/server/raw_config', {
                'raw_config': encoded
            })
                .catch(saveFailed);
        }

        function getVariables() {
            return $http.get('/api/variables/', {
                etagCache: true
            })
                .catch(callFailed);
        }

        function saveVariables(variables) {
            return $http.put('/api/variables/', variables)
                .catch(saveFailed);
        }

        function saveFailed(response) {
            return $q.reject(response.data);
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());