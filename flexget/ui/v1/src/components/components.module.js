/* global angular */
(function () {
    'use strict';

    angular
        .module('flexget.components', [
            'components.404',
            'components.auth',
            'components.core',
            'components.home',
            'components.sidenav',
            'components.toolbar',
            'components.user',
            'components.database'
        ]);
}());