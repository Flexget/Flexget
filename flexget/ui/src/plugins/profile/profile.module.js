(function () {
    'use strict';

    var profileModule = angular.module('flexget.plugins.profile', ['ngMessages']);
    registerPlugin(profileModule);

    profileModule.run(function (route, toolBar, $state) {
        route.register('profile', '/profile', 'profileController', 'plugins/profile/profile.tmpl.html');
        toolBar.registerMenuItem('Manage', 'Profile', 'fa fa-user', function () {
            $state.go('flexget.profile');
        }, 100);
    });

})();