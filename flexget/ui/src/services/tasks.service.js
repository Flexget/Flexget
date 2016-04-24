(function () {
    'use strict';

    angular.module('flexget.components')
        .service('tasks', tasksService);

    function tasksService($rootScope, $http, $q) {
        // List tasks
        this.list = function () {
            return $http.get('/api/tasks/')
                .then(
                    function (response) {
                        var tasks = [];
                        angular.forEach(response.data.tasks, function (task) {
                            this.push(task.name);
                        }, tasks);
                        return tasks
                    },
                    function (httpError) {
                        throw httpError.status + " : " + httpError.data;
                    });
        };

        // Execute task(s), return stream log etc
        this.execute = function (task_names, options) {
            var deferred = $q.defer();

            console.log(options);

            options.tasks = task_names;
            var on = function (event, pattern, callback) {
                var wrappedCallback = function () {
                    var args = arguments;

                    return $rootScope.$evalAsync(function () {
                        return callback.apply(stream, args);
                    });
                };

                if (pattern) {
                    stream.on(event, pattern, wrappedCallback);
                } else {
                    stream.on(event, wrappedCallback)
                }
            };

            var stream = oboe({
                url: '/api/tasks/execute/',
                body: options,
                method: 'POST'
            }).done(function () {
                deferred.resolve("finished stream");
            }).fail(function (error) {
                deferred.reject(error)
            });

            deferred.promise.log = function (callback) {
                on('node', 'log', callback);
                return deferred.promise;
            };

            deferred.promise.progress = function (callback) {
                on('node', 'progress', callback);
                return deferred.promise;
            };

            deferred.promise.summary = function (callback) {
                on('node', 'summary', callback);
                return deferred.promise;
            };

            deferred.promise.entry_dump = function (callback) {
                on('node', 'entry_dump', callback);
                return deferred.promise;
            };

            deferred.promise.abort = function () {
                return stream.abort();
            };

            return deferred.promise;
        };

        this.queue = function () {
            var defer = $q.defer();

            $http.get('/api/tasks/queue/', {ignoreLoadingBar: true}).then(function (response) {
                defer.resolve(response.data.tasks);
            }, function (response) {
                defer.reject(response);
            });

            return defer.promise;
        };

        // Update task config
        this.update = function () {

        };

        // add task
        this.add = function () {

        };

        // Delete task
        this.delete = function () {

        }
    }
})();