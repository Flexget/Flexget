(function () {
    'use strict';

    var home = angular.module("home", ['angular.filter']);
    registerPlugin(home);

    home.run(function (route) {
        route.register('home', '/home', null, 'components/home/home.tmpl.html');
    });
})();