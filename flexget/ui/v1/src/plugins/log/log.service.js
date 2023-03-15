/* global angular, oboe */
(function () {
    'use strict';

    angular
        .module('plugins.log')
        .factory('logService', logService);

    function logService($q) {
        return {
            startLogStream: startLogStream
        };

        function startLogStream(query) {
            var deferred = $q.defer();

            var stream = oboe({
                url: 'api/server/log/' + query,
                method: 'GET'
            }).done(function () {
                deferred.resolve('finished stream');
            }).fail(function (error) {
                deferred.reject(error);
            });

            deferred.promise.start = function (callback) {
                stream.on('start', callback);
                return deferred.promise;
            };

            deferred.promise.message = function (callback) {
                stream.on('node', '{message}', callback);
                return deferred.promise;
            };

            deferred.promise.abort = function () {
                return stream.abort();
            };

            return deferred.promise;
        }
    }
}());