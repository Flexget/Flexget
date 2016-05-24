(function () {
    'use strict';

    var home = angular.module("flexget.home", ['angular.filter']);
    registerPlugin(home);

    home.run(function (route) {
        route.register('home', '/home', 'home');
    });
})();
