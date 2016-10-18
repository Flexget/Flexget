/* global angular */
(function () {
    'use strict';

    angular
        .module('plugins.config')
        .factory('configService', configService);

    function configService($http, exception, $q) {
        return {
            getRawConfig: getRawConfig,
            saveRawConfig: saveRawConfig
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
                .catch(saveRawConfigFailed);

            function saveRawConfigFailed(response) {
                return $q.reject(response.data);
            }
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());