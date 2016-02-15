(function () {
    'use strict';

    var scheduleModule = angular.module('flexget.plugins.schedule', ['schemaForm']);
    registerPlugin(scheduleModule);

    scheduleModule.run(function (route, sideNav) {
        route.register('schedule', '/schedule', 'scheduleController', 'plugins/schedule/schedule.tmpl.html');
        sideNav.register('/schedule', 'Schedule', 'fa fa-calendar', 128);
    });

})();