(function () {
    'use strict';

    angular.module('plugins.config')
        .factory('configService', configService);

    function configService($http, exception) {
        return {
            getRawConfig: getRawConfig
        }

        function getRawConfig() {
            return $http.get('/api/server/raw_config')
                .then(getRawConfigComplete)
                .catch(callFailed);

            function getRawConfigComplete(response) {
                return response.data;
            }
        }

        function callFailed(error) {
			return exception.catcher(error);
        }
    }
})();