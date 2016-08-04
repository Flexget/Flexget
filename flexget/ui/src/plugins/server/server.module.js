/* global angular, registerPlugin */
(function () {
    'use strict';

    angular
        .module('plugins.server', [
            'components.toolbar'
        ]);

    registerPlugin('plugins.server');
}());