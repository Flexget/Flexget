(function () {
    'use strict';

    angular
        .module('flexget', [
            'ui.router',
            'ngMaterial',
            'ngCookies',
            'angular-loading-bar',
            'flexget.components'
        ]);

    function bootstrapApplication() {
        /* Bootstrap app after page has loaded which allows plugins to register */
        angular.element(document).ready(function () {
            angular.bootstrap(document, ['flexget']);
        });
        window.loading_screen.finish();
    }

    bootstrapApplication();
})();