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
        this.executeStream = function (tasks) {
            var stream = oboe({
                url: '/api/execution/execute/stream/?progress=true&log=true&summary=true&entry_dump=true',
                method: 'POST',
                body: {tasks: tasks}
            });

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

                return executeWrapper;
            };

            var executeWrapper = {
                start: function (callback) {
                    return on('start', null, callback);
                },
                tasks: function (callback) {
                    return on('node', 'tasks', callback);
                },
                log: function (callback) {
                    return on('node', 'log', callback);
                },
                progress: function (callback) {
                    var wrappedCallback = function (data) {
                        var taskId = Object.keys(data)[0];
                        return callback(taskId, data[taskId])
                    };
                    return on('node', 'progress', wrappedCallback);
                },
                summary: function (callback) {
                    var wrappedCallback = function (data) {
                        var taskId = Object.keys(data)[0];
                        return callback(taskId, data[taskId])
                    };
                    return on('node', 'summary', wrappedCallback);
                },
                entry_dump: function (callback) {
                    var wrappedCallback = function (data) {
                        var taskId = Object.keys(data)[0];
                        return callback(taskId, data[taskId])
                    };
                    return on('node', 'entry_dump', wrappedCallback);
                },
                done: function (callback) {
                    return on('done', null, callback);
                },
                error: function (callback) {
                    return on('fail', null, callback);
                },
                abort: function () {
                    stream.abort()
                }
            };
            return executeWrapper;
        };

        this.queue = function () {
            var defer = $q.defer();

            $http.get('/api/execution/queue/').then(function (response) {
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