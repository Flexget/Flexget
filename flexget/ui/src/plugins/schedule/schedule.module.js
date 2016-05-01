(function () {
    'use strict';
    
    var scheduleModule = angular.module('flexget.plugins.schedule', ['schemaForm']);
    registerPlugin(scheduleModule);
    
    scheduleModule.run(function (route, sideNav) {
        route.register('schedule', '/schedule', 'schedule-view');
        sideNav.register('/schedule', 'Schedule', 'fa fa-calendar', 128);
    });
    
})();
