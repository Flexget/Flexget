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
            return $http.get('/api/server/raw_config')
                .then(getRawConfigComplete)
                .catch(callFailed);

            function getRawConfigComplete(response) {
                return response.data;
            }
        }

		function saveRawConfig(encoded) {
			return $http.post('/api/server/raw_config', {
				raw_config: encoded
			})
				.then(saveRawConfigComplete)
				.catch(saveRawConfigFailed);
			
			function saveRawConfigComplete() {
				return;
			}

			function saveRawConfigFailed(response) {
				return $q.reject(response.data);
			}
		}

        function callFailed(error) {
			return exception.catcher(error);
        }
    }
})();