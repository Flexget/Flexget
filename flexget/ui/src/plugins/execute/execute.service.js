/* global angular, oboe */
(function () {
    'use strict';

    angular
        .module('plugins.execute')
        .factory('executeService', executeService);

    function executeService($http, $q, exception) {
        return {
            getTasks: getTasks,
            getQueue: getQueue,
            executeTasks: executeTasks
        };

        function getTasks(params) {
            return $http.get('/api/tasks/', {
                params: params,
                etagCache: true
            })
                .catch(callFailed);
        }

        function getQueue() {
            return $http.get('/api/tasks/queue/', {
                ignoreLoadingBar: true
            })
                .then(callCompleted)
                .catch(callFailed);
            
            function callCompleted(response) {
                return response.data;
            }
        }

        function executeTasks(options) {
            var deferred = $q.defer();

            var stream = oboe({
                url: 'api/tasks/execute/',
                body: options,
                method: 'POST'
            }).done(function () {
                deferred.resolve('finished stream');
            }).fail(function (error) {
                deferred.reject(error);
            });
            
            deferred.promise.tasks = function (callback) {
                stream.on('node', 'tasks', callback);
                return deferred.promise;
            };

            deferred.promise.log = function (callback) {
                stream.on('node', 'log', callback);
                return deferred.promise;
            };

            deferred.promise.progress = function (callback) {
                stream.on('node', 'progress', callback);
                return deferred.promise;
            };

            deferred.promise.summary = function (callback) {
                stream.on('node', 'summary', callback);
                return deferred.promise;
            };

            deferred.promise.entryDump = function (callback) {
                stream.on('node', 'entry_dump', callback);
                return deferred.promise;
            };

            deferred.promise.abort = function () {
                return stream.abort();
            };

            return deferred.promise;
        }

        function callFailed(error) {
            return exception.catcher(error);
        }
    }
}());
